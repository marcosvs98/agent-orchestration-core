from __future__ import annotations

import asyncio
import socket
import threading
import time
from types import TracebackType
from typing import Any, Dict, Final, Iterator, List, Literal, Optional, TypeAlias
from uuid import uuid4

import uvicorn
from fastapi import Body, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

Currency: TypeAlias = Literal["USD", "EUR", "GBP"]
PaymentMethod: TypeAlias = Literal["card", "bank_transfer", "wallet", "direct_debit"]
PaymentStatus: TypeAlias = Literal[
    "authorized", "captured", "declined", "refunded", "partially_refunded"
]
RefundReason: TypeAlias = Literal[
    "requested_by_customer", "duplicate", "fraudulent", "product_unavailable"
]
FailureMode: TypeAlias = Literal["hangup", "timeout", "status_502"]

DECLINE_THRESHOLD_MINOR: Final[int] = 100_000
DEFAULT_TIMEOUT_SLEEP_SECONDS: Final[float] = 15.0
STARTUP_TIMEOUT_SECONDS: Final[float] = 10.0
SHUTDOWN_TIMEOUT_SECONDS: Final[float] = 5.0


class CreatePaymentRequest(BaseModel):
    amount_minor: int = Field(
        gt=0,
        description="Charge amount in the smallest currency unit. 4990 means USD 49.90.",
    )
    currency: Currency = Field(description="ISO 4217 currency code of the charge.")
    payment_method: PaymentMethod = Field(description="How the customer is paying.")
    customer_reference: str = Field(
        min_length=1,
        description="Merchant-side identifier of the customer being charged.",
    )
    description: str = Field(
        min_length=1,
        description="What the customer is being charged for.",
    )
    statement_descriptor: Optional[str] = Field(
        default=None,
        description="Text shown on the customer bank statement, up to 22 characters.",
    )
    capture: bool = Field(
        default=True,
        description="Capture immediately. False authorizes the amount and captures later.",
    )


class CapturePaymentRequest(BaseModel):
    payment_id: str = Field(min_length=1, description="Identifier of the authorized payment.")
    amount_minor: Optional[int] = Field(
        default=None,
        gt=0,
        description="Amount to capture in minor units. Defaults to the authorized amount.",
    )


class CreateRefundRequest(BaseModel):
    payment_id: str = Field(min_length=1, description="Identifier of the payment to refund.")
    amount_minor: Optional[int] = Field(
        default=None,
        gt=0,
        description="Amount to refund in minor units. Defaults to the full captured amount.",
    )
    reason: RefundReason = Field(
        default="requested_by_customer",
        description="Why the refund is being issued.",
    )


class CreatePayoutRequest(BaseModel):
    amount_minor: int = Field(gt=0, description="Payout amount in the smallest currency unit.")
    currency: Currency = Field(description="ISO 4217 currency code of the payout.")
    destination_account: str = Field(
        min_length=1,
        description="Identifier of the bank account receiving the funds.",
    )
    description: str = Field(min_length=1, description="Why the payout is being sent.")


class Payment(BaseModel):
    payment_id: str
    status: PaymentStatus
    amount_minor: int
    amount_captured_minor: int
    amount_refunded_minor: int
    currency: Currency
    payment_method: PaymentMethod
    customer_reference: str
    description: str
    decline_code: Optional[str] = None
    created_at: str


class PaymentPage(BaseModel):
    payments: List[Payment]
    total_count: int


class Refund(BaseModel):
    refund_id: str
    payment_id: str
    status: Literal["succeeded"]
    amount_minor: int
    currency: Currency
    reason: RefundReason
    created_at: str


class Payout(BaseModel):
    payout_id: str
    status: Literal["pending", "paid"]
    amount_minor: int
    currency: Currency
    destination_account: str
    description: str
    created_at: str


class Balance(BaseModel):
    currency: Currency
    available_minor: int
    pending_minor: int
    as_of: str


class RecordedCall(BaseModel):
    method: str
    path: str
    query: Dict[str, str]
    body: Dict[str, Any]
    authorization: Optional[str]
    idempotency_key: Optional[str]


class PaymentsLedger:
    def __init__(self) -> None:
        self.calls: List[RecordedCall] = []
        self.payments: Dict[str, Payment] = {}
        self.refunds: Dict[str, Refund] = {}
        self.payouts: Dict[str, Payout] = {}
        self.by_idempotency_key: Dict[str, str] = {}
        self.fail_next: int = 0
        self.fail_mode: FailureMode = "hangup"
        self.timeout_sleep_seconds: float = DEFAULT_TIMEOUT_SLEEP_SECONDS

    def record(self, call: RecordedCall) -> None:
        self.calls.append(call)

    def calls_to(self, path: str) -> List[RecordedCall]:
        return [call for call in self.calls if call.path.rstrip("/") == path.rstrip("/")]

    def consume_failure(self) -> Optional[FailureMode]:
        if self.fail_next <= 0:
            return None
        self.fail_next -= 1
        return self.fail_mode

    def reset(self) -> None:
        self.calls.clear()
        self.payments.clear()
        self.refunds.clear()
        self.payouts.clear()
        self.by_idempotency_key.clear()
        self.fail_next = 0


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _truncated_body() -> Iterator[bytes]:
    yield b'{"payment_id": "pay_'
    raise RuntimeError("simulated upstream connection drop")


async def _apply_failure(ledger: PaymentsLedger) -> Optional[Any]:
    mode = ledger.consume_failure()
    if mode is None:
        return None
    if mode == "status_502":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "upstream_unavailable"},
        )
    if mode == "timeout":
        await asyncio.sleep(ledger.timeout_sleep_seconds)
        return None
    return StreamingResponse(_truncated_body(), media_type="application/json")


def _require_authorization(authorization: Optional[str]) -> str:
    if not authorization or not authorization.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "authorization_header_missing"},
        )
    return authorization


def _find_payment(ledger: PaymentsLedger, payment_id: str) -> Payment:
    payment = ledger.payments.get(payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "payment_not_found", "payment_id": payment_id},
        )
    return payment


CREATE_PAYMENT_EXAMPLES: Final[Dict[str, Dict[str, Any]]] = {
    "card_charge": {
        "summary": "Charge a card immediately",
        "value": {
            "amount_minor": 4990,
            "currency": "USD",
            "payment_method": "card",
            "customer_reference": "cus_10428",
            "description": "Annual subscription renewal",
            "statement_descriptor": "ACME ANNUAL",
            "capture": True,
        },
    },
    "authorize_only": {
        "summary": "Authorize now and capture on shipment",
        "value": {
            "amount_minor": 129900,
            "currency": "EUR",
            "payment_method": "card",
            "customer_reference": "cus_77310",
            "description": "Hardware order 4471",
            "capture": False,
        },
    },
    "bank_transfer": {
        "summary": "Collect an invoice by bank transfer",
        "value": {
            "amount_minor": 250000,
            "currency": "GBP",
            "payment_method": "bank_transfer",
            "customer_reference": "cus_55021",
            "description": "Invoice INV-2211",
        },
    },
}

CAPTURE_PAYMENT_EXAMPLES: Final[Dict[str, Dict[str, Any]]] = {
    "full_capture": {
        "summary": "Capture the full authorized amount",
        "value": {"payment_id": "pay_5f2c1b9a41d0"},
    },
    "partial_capture": {
        "summary": "Capture part of the authorization",
        "value": {"payment_id": "pay_5f2c1b9a41d0", "amount_minor": 89900},
    },
}

CREATE_REFUND_EXAMPLES: Final[Dict[str, Dict[str, Any]]] = {
    "full_refund": {
        "summary": "Refund the whole payment",
        "value": {"payment_id": "pay_5f2c1b9a41d0", "reason": "requested_by_customer"},
    },
    "partial_refund": {
        "summary": "Refund part of the payment",
        "value": {
            "payment_id": "pay_5f2c1b9a41d0",
            "amount_minor": 1500,
            "reason": "product_unavailable",
        },
    },
}

CREATE_PAYOUT_EXAMPLES: Final[Dict[str, Dict[str, Any]]] = {
    "settlement": {
        "summary": "Send settled funds to the merchant bank account",
        "value": {
            "amount_minor": 480000,
            "currency": "USD",
            "destination_account": "ba_9921ff",
            "description": "Weekly settlement",
        },
    },
}


def create_app(ledger: PaymentsLedger, public_base_url: str) -> FastAPI:
    app = FastAPI(
        title="Acme Payments API",
        version="2024-11-01",
        description=(
            "A market-standard payments API: charge a customer, capture an authorization, "
            "refund a payment, look payments up, pay out settled funds and read the balance. "
            "Amounts are always integers in the smallest unit of the currency."
        ),
        servers=[{"url": public_base_url}],
        openapi_url="/openapi.json",
        docs_url=None,
        redoc_url=None,
    )

    @app.post(
        "/v1/payments",
        operation_id="payments_create_payment",
        summary="Charge a customer",
        description=(
            "Creates and captures a payment against a customer's payment method. Use this when "
            "the user wants to charge, bill, collect or take money from a customer. Amounts are "
            "in minor units, so 4990 means 49.90."
        ),
        response_model=Payment,
        status_code=status.HTTP_201_CREATED,
        responses={402: {"description": "The payment was declined by the issuer."}},
    )
    async def create_payment(
        payload: CreatePaymentRequest = Body(openapi_examples=CREATE_PAYMENT_EXAMPLES),
        authorization: Optional[str] = Header(default=None),
        idempotency_key: Optional[str] = Header(default=None),
    ) -> Any:
        _require_authorization(authorization)
        ledger.record(
            RecordedCall(
                method="POST",
                path="/v1/payments",
                query={},
                body=payload.model_dump(mode="json"),
                authorization=authorization,
                idempotency_key=idempotency_key,
            )
        )
        failure = await _apply_failure(ledger)
        if failure is not None:
            return failure

        if idempotency_key:
            replayed_id = ledger.by_idempotency_key.get(idempotency_key)
            if replayed_id is not None:
                return ledger.payments[replayed_id]

        declined = (
            payload.payment_method == "card" and payload.amount_minor >= DECLINE_THRESHOLD_MINOR
        )
        captured = payload.amount_minor if (payload.capture and not declined) else 0
        payment = Payment(
            payment_id=f"pay_{uuid4().hex[:12]}",
            status="declined" if declined else ("captured" if payload.capture else "authorized"),
            amount_minor=payload.amount_minor,
            amount_captured_minor=captured,
            amount_refunded_minor=0,
            currency=payload.currency,
            payment_method=payload.payment_method,
            customer_reference=payload.customer_reference,
            description=payload.description,
            decline_code="insufficient_funds" if declined else None,
            created_at=_now(),
        )
        ledger.payments[payment.payment_id] = payment
        if idempotency_key:
            ledger.by_idempotency_key[idempotency_key] = payment.payment_id
        return payment

    @app.post(
        "/v1/payments/capture",
        operation_id="payments_capture_payment",
        summary="Capture an authorized payment",
        description=(
            "Captures funds that were previously authorized but not yet taken. Use this when the "
            "user wants to settle, capture or finalize an authorization."
        ),
        response_model=Payment,
    )
    async def capture_payment(
        payload: CapturePaymentRequest = Body(openapi_examples=CAPTURE_PAYMENT_EXAMPLES),
        authorization: Optional[str] = Header(default=None),
    ) -> Any:
        _require_authorization(authorization)
        ledger.record(
            RecordedCall(
                method="POST",
                path="/v1/payments/capture",
                query={},
                body=payload.model_dump(mode="json"),
                authorization=authorization,
                idempotency_key=None,
            )
        )
        failure = await _apply_failure(ledger)
        if failure is not None:
            return failure

        payment = _find_payment(ledger, payload.payment_id)
        if payment.status != "authorized":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "payment_not_capturable", "status": payment.status},
            )
        amount = payload.amount_minor or payment.amount_minor
        if amount > payment.amount_minor:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "capture_exceeds_authorization"},
            )
        captured = payment.model_copy(
            update={"status": "captured", "amount_captured_minor": amount}
        )
        ledger.payments[captured.payment_id] = captured
        return captured

    @app.post(
        "/v1/refunds",
        operation_id="payments_create_refund",
        summary="Refund a payment",
        description=(
            "Returns money to the customer for a captured payment, in full or in part. Use this "
            "when the user wants to refund, reimburse, give money back or reverse a charge."
        ),
        response_model=Refund,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_refund(
        payload: CreateRefundRequest = Body(openapi_examples=CREATE_REFUND_EXAMPLES),
        authorization: Optional[str] = Header(default=None),
    ) -> Any:
        _require_authorization(authorization)
        ledger.record(
            RecordedCall(
                method="POST",
                path="/v1/refunds",
                query={},
                body=payload.model_dump(mode="json"),
                authorization=authorization,
                idempotency_key=None,
            )
        )
        failure = await _apply_failure(ledger)
        if failure is not None:
            return failure

        payment = _find_payment(ledger, payload.payment_id)
        refundable = payment.amount_captured_minor - payment.amount_refunded_minor
        if refundable <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "payment_not_refundable", "status": payment.status},
            )
        amount = payload.amount_minor or refundable
        if amount > refundable:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "refund_exceeds_captured_amount", "refundable_minor": refundable},
            )
        refunded_total = payment.amount_refunded_minor + amount
        ledger.payments[payment.payment_id] = payment.model_copy(
            update={
                "amount_refunded_minor": refunded_total,
                "status": (
                    "refunded"
                    if refunded_total >= payment.amount_captured_minor
                    else "partially_refunded"
                ),
            }
        )
        refund = Refund(
            refund_id=f"re_{uuid4().hex[:12]}",
            payment_id=payment.payment_id,
            status="succeeded",
            amount_minor=amount,
            currency=payment.currency,
            reason=payload.reason,
            created_at=_now(),
        )
        ledger.refunds[refund.refund_id] = refund
        return refund

    @app.get(
        "/v1/payments",
        operation_id="payments_list_payments",
        summary="List payments",
        description=(
            "Lists recent payments, optionally narrowed to one customer or one status. Use this "
            "when the user wants to see, list, review or search existing payments. This is a "
            "read-only operation and never moves money."
        ),
        response_model=PaymentPage,
    )
    async def list_payments(
        customer_reference: Optional[str] = Query(
            default=None,
            description="Only return payments belonging to this customer.",
        ),
        payment_status: Optional[PaymentStatus] = Query(
            default=None,
            alias="status",
            description="Only return payments currently in this status.",
        ),
        limit: int = Query(default=10, ge=1, le=100, description="Maximum payments to return."),
        authorization: Optional[str] = Header(default=None),
    ) -> Any:
        _require_authorization(authorization)
        ledger.record(
            RecordedCall(
                method="GET",
                path="/v1/payments",
                query={
                    "customer_reference": str(customer_reference),
                    "payment_status": str(payment_status),
                    "limit": str(limit),
                },
                body={},
                authorization=authorization,
                idempotency_key=None,
            )
        )
        failure = await _apply_failure(ledger)
        if failure is not None:
            return failure

        matches = [
            payment
            for payment in ledger.payments.values()
            if (customer_reference is None or payment.customer_reference == customer_reference)
            and (payment_status is None or payment.status == payment_status)
        ]
        ordered = sorted(matches, key=lambda payment: payment.created_at, reverse=True)
        return PaymentPage(payments=ordered[:limit], total_count=len(matches))

    @app.get(
        "/v1/payments/lookup",
        operation_id="payments_get_payment",
        summary="Look up one payment",
        description=(
            "Returns the current state of a single payment, including how much of it was "
            "captured and refunded. Read-only."
        ),
        response_model=Payment,
    )
    async def get_payment(
        payment_id: str = Query(description="Identifier returned when the payment was created."),
        authorization: Optional[str] = Header(default=None),
    ) -> Any:
        _require_authorization(authorization)
        ledger.record(
            RecordedCall(
                method="GET",
                path="/v1/payments/lookup",
                query={"payment_id": payment_id},
                body={},
                authorization=authorization,
                idempotency_key=None,
            )
        )
        failure = await _apply_failure(ledger)
        if failure is not None:
            return failure
        return _find_payment(ledger, payment_id)

    @app.post(
        "/v1/payouts",
        operation_id="payments_create_payout",
        summary="Pay out settled funds",
        description=(
            "Sends settled balance to a merchant bank account. Use this when the user wants to "
            "withdraw, transfer out or settle funds to their own account."
        ),
        response_model=Payout,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_payout(
        payload: CreatePayoutRequest = Body(openapi_examples=CREATE_PAYOUT_EXAMPLES),
        authorization: Optional[str] = Header(default=None),
    ) -> Any:
        _require_authorization(authorization)
        ledger.record(
            RecordedCall(
                method="POST",
                path="/v1/payouts",
                query={},
                body=payload.model_dump(mode="json"),
                authorization=authorization,
                idempotency_key=None,
            )
        )
        failure = await _apply_failure(ledger)
        if failure is not None:
            return failure

        payout = Payout(
            payout_id=f"po_{uuid4().hex[:12]}",
            status="pending",
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            destination_account=payload.destination_account,
            description=payload.description,
            created_at=_now(),
        )
        ledger.payouts[payout.payout_id] = payout
        return payout

    @app.get(
        "/v1/balance",
        operation_id="payments_get_balance",
        summary="Read the account balance",
        description=(
            "Returns available and pending balance for one currency. Use this when the user asks "
            "how much money they have, what their balance is or what is ready to pay out."
        ),
        response_model=Balance,
    )
    async def get_balance(
        currency: Currency = Query(default="USD", description="Currency to report on."),
        authorization: Optional[str] = Header(default=None),
    ) -> Any:
        _require_authorization(authorization)
        ledger.record(
            RecordedCall(
                method="GET",
                path="/v1/balance",
                query={"currency": currency},
                body={},
                authorization=authorization,
                idempotency_key=None,
            )
        )
        failure = await _apply_failure(ledger)
        if failure is not None:
            return failure

        captured = sum(
            payment.amount_captured_minor - payment.amount_refunded_minor
            for payment in ledger.payments.values()
            if payment.currency == currency
        )
        paid_out = sum(
            payout.amount_minor for payout in ledger.payouts.values() if payout.currency == currency
        )
        return Balance(
            currency=currency,
            available_minor=max(0, captured - paid_out),
            pending_minor=paid_out,
            as_of=_now(),
        )

    @app.get("/health", include_in_schema=False)
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    return app


class PaymentsApiStub:
    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.host = host
        self.requested_port = port
        self.ledger = PaymentsLedger()
        self.port: Optional[int] = None
        self.server: Optional[uvicorn.Server] = None
        self.thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        if self.port is None:
            raise RuntimeError("the payments stub is not started")
        return f"http://{self.host}:{self.port}"

    @property
    def openapi_url(self) -> str:
        return f"{self.base_url}/openapi.json"

    @property
    def calls(self) -> List[RecordedCall]:
        return list(self.ledger.calls)

    def calls_to(self, path: str) -> List[RecordedCall]:
        return self.ledger.calls_to(path)

    def payments(self) -> List[Payment]:
        return list(self.ledger.payments.values())

    def refunds(self) -> List[Refund]:
        return list(self.ledger.refunds.values())

    def fail_next_calls(self, count: int, mode: FailureMode = "hangup") -> None:
        self.ledger.fail_next = count
        self.ledger.fail_mode = mode

    def reset(self) -> None:
        self.ledger.reset()

    def start(self) -> "PaymentsApiStub":
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, self.requested_port))
        listener.listen(64)
        self.port = int(listener.getsockname()[1])

        app = create_app(self.ledger, self.base_url)
        config = uvicorn.Config(
            app,
            log_level="critical",
            access_log=False,
            lifespan="off",
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(
            target=self.server.run,
            kwargs={"sockets": [listener]},
            daemon=True,
        )
        self.thread.start()

        deadline = time.time() + STARTUP_TIMEOUT_SECONDS
        while time.time() < deadline:
            if self.server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError(f"the payments stub did not start within {STARTUP_TIMEOUT_SECONDS}s")

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.thread is not None:
            self.thread.join(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        self.server = None
        self.thread = None
        self.port = None

    def __enter__(self) -> "PaymentsApiStub":
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        self.stop()
        return False
