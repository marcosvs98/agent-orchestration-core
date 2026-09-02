from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

DEFAULT_CURRENCY = "BRL"

_EXPENSES: list[dict[str, Any]] = [
    {
        "expense_id": "exp_0001",
        "status": "recorded",
        "amount": 35.0,
        "currency": DEFAULT_CURRENCY,
        "description": "almoco no restaurante",
        "category": "food",
        "occurred_on": "2026-08-16",
        "payment_method": "card",
        "account_label": "Santander PF",
    },
    {
        "expense_id": "exp_0002",
        "status": "recorded",
        "amount": 18.5,
        "currency": DEFAULT_CURRENCY,
        "description": "corrida de aplicativo",
        "category": "transport",
        "occurred_on": "2026-08-17",
        "payment_method": "PIX",
        "account_label": "Nubank",
    },
    {
        "expense_id": "exp_0003",
        "status": "recorded",
        "amount": 82.3,
        "currency": DEFAULT_CURRENCY,
        "description": "compras no mercado",
        "category": "food",
        "occurred_on": "2026-08-17",
        "payment_method": "card",
        "account_label": "Santander PF",
    },
]


class ExpenseCreate(BaseModel):
    amount: float
    description: str
    currency: str | None = None
    category: str | None = None
    occurred_on: date | None = None
    payment_method: str | None = None
    account_label: str | None = Field(default=None)


app = FastAPI(
    title="Demo Expenses API",
    version="1.0.0",
    description="Sample domain for the demo tenant: record, list and summarise expenses.",
)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "healthy", "expenses": len(_EXPENSES)}


@app.post("/expenses", status_code=201)
async def create_expense(payload: ExpenseCreate) -> JSONResponse:
    recorded = {
        "expense_id": f"exp_{len(_EXPENSES) + 1:04d}",
        "status": "recorded",
        "amount": payload.amount,
        "currency": payload.currency or DEFAULT_CURRENCY,
        "description": payload.description,
        "category": payload.category or "uncategorised",
        "occurred_on": (payload.occurred_on or datetime.now(UTC).date()).isoformat(),
        "payment_method": payload.payment_method or "unspecified",
        "account_label": payload.account_label or "unspecified",
    }
    _EXPENSES.append(recorded)
    return JSONResponse(content=recorded, status_code=201)


@app.get("/expenses")
async def list_expenses(
    category: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    items = [e for e in _EXPENSES if category is None or e["category"] == category]
    selected = items[-limit:]
    return {"items": selected, "count": len(selected), "currency": DEFAULT_CURRENCY}


@app.get("/expenses/summary")
async def get_expense_summary(
    group_by: str = Query(default="category"),
) -> dict[str, Any]:
    key = group_by if group_by in ("category", "payment_method") else "category"
    totals: dict[str, float] = {}
    for expense in _EXPENSES:
        bucket = str(expense.get(key) or "unspecified")
        totals[bucket] = round(totals.get(bucket, 0.0) + float(expense["amount"]), 2)
    return {
        "group_by": key,
        "currency": DEFAULT_CURRENCY,
        "totals": [{key: k, "total": v} for k, v in sorted(totals.items())],
    }
