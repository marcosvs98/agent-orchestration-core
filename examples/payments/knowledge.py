from __future__ import annotations

from typing import Final, Sequence

from examples.api.provisioning import KnowledgeDocument, ToolAliasCluster

APPROVED_OPERATION_IDS: Final[Sequence[str]] = (
    "payments_create_payment",
    "payments_create_refund",
    "payments_list_payments",
    "payments_get_payment",
    "payments_get_balance",
)

WITHHELD_OPERATION_IDS: Final[Sequence[str]] = (
    "payments_capture_payment",
    "payments_create_payout",
)

AGENT_SYSTEM_PROMPT: Final[str] = (
    "You are a payments operations assistant for an online merchant. You help the team charge "
    "customers, issue refunds, look payments up and read the account balance through the Acme "
    "Payments API. Work only from data present in the conversation or returned by a tool; never "
    "invent an amount, a payment identifier or a customer reference. Amounts are always integers "
    "in minor units, so state them back to the user in the readable form: 4990 is 49.90. When a "
    "payment is declined, say so plainly and give the decline code. Answer in English, in two or "
    "three sentences, in a precise and professional tone."
)

KNOWLEDGE_DOCUMENTS: Final[Sequence[KnowledgeDocument]] = (
    KnowledgeDocument(
        doc_type="identity_and_scope",
        content=(
            "Identity and scope. This assistant operates the Acme Payments API on behalf of the "
            "merchant's payments team. It can charge a customer, refund a captured payment, list "
            "and look up payments, and report the account balance. It does not give financial, "
            "tax or legal advice, it does not negotiate with customers, and it never changes "
            "pricing. Tone of voice: precise, calm and professional."
        ),
        metadata={"topic": "identity", "audience": "operator"},
    ),
    KnowledgeDocument(
        doc_type="policy_amounts_and_currency",
        content=(
            "Amounts and currency. Every amount exchanged with the payments API is an integer in "
            "the smallest unit of the currency, so 4990 means 49.90 and 250000 means 2500.00. "
            "The supported currencies are USD, EUR and GBP. A charge must always carry an "
            "explicit currency; the assistant never guesses one from the customer's location. "
            "When a user speaks in decimal amounts, convert to minor units before calling a tool "
            "and convert back to decimals when reporting the result."
        ),
        metadata={"topic": "amounts", "audience": "operator"},
    ),
    KnowledgeDocument(
        doc_type="policy_refunds",
        content=(
            "Refund policy. A payment can only be refunded once it has been captured, and never "
            "for more than the captured amount minus what was already refunded. Refunds are "
            "issued for one of four reasons: requested_by_customer, duplicate, fraudulent or "
            "product_unavailable. A partial refund leaves the payment in partially_refunded; a "
            "full refund moves it to refunded. Refunds settle back to the original payment "
            "method and cannot be redirected to a different card or account."
        ),
        metadata={"topic": "refunds", "audience": "operator"},
    ),
    KnowledgeDocument(
        doc_type="policy_declines",
        content=(
            "Declines. A declined charge is not an error: the API answers normally and the "
            "payment comes back with status declined and a decline_code such as "
            "insufficient_funds. No money moves and no refund is possible. The assistant reports "
            "the decline and its code, and suggests either retrying with a different payment "
            "method or contacting the customer. It never retries the same card automatically, "
            "because repeated declines on one card raise the issuer's fraud score."
        ),
        metadata={"topic": "declines", "audience": "operator"},
    ),
    KnowledgeDocument(
        doc_type="policy_authorization_and_capture",
        content=(
            "Authorization and capture. Charging with capture set to false authorizes the funds "
            "without taking them, which is the right shape for physical goods that ship later. "
            "The separate capture step is a back-office operation and is not exposed to this "
            "assistant: capture requests are handled by the fulfilment team once the order "
            "actually ships. Authorizations that are never captured expire on the issuer's own "
            "schedule, typically within seven days."
        ),
        metadata={"topic": "capture", "audience": "operator"},
    ),
    KnowledgeDocument(
        doc_type="policy_payouts",
        content=(
            "Payouts. Moving settled balance out to the merchant's own bank account is a payout. "
            "Payouts are deliberately outside this assistant's reach: they move money out of the "
            "business and require dual approval in the finance system. If a user asks for a "
            "payout or a withdrawal, the assistant explains that the operation needs finance "
            "approval and offers to report the available balance instead."
        ),
        metadata={"topic": "payouts", "audience": "operator"},
    ),
    KnowledgeDocument(
        doc_type="policy_idempotency",
        content=(
            "Idempotency and duplicate charges. Charge requests carry an idempotency key so that "
            "a retried request replays the original payment instead of taking the money twice. "
            "If a user is unsure whether a charge went through, the assistant looks the payment "
            "up or lists the customer's recent payments before charging again. Creating a second "
            "charge to 'make sure' is never the correct move."
        ),
        metadata={"topic": "idempotency", "audience": "operator"},
    ),
    KnowledgeDocument(
        doc_type="faq_common_requests",
        content=(
            "Frequently asked. Question: how do I charge a customer? Answer: give the amount, "
            "the currency, the customer reference and what the charge is for. Question: how do I "
            "refund? Answer: give the payment identifier, and the amount if the refund is only "
            "partial. Question: how do I know what a customer has paid? Answer: list payments "
            "filtered by that customer reference. Question: how much money is available? Answer: "
            "read the balance for the currency you care about."
        ),
        metadata={"topic": "faq", "audience": "operator"},
    ),
)

TOOL_ALIAS_CLUSTERS: Final[Sequence[ToolAliasCluster]] = (
    ToolAliasCluster(
        operation_id="payments_create_payment",
        cluster="direct_verbs",
        content=(
            "payments_create_payment semantic aliases. Direct verbs that mean taking money from "
            "a customer: charge, bill, collect, take payment, run a payment, process a payment, "
            "put through a charge, charge the card, debit the customer, take the money, capture "
            "payment from the customer, invoice and collect now. IMPORTANT: this is the tool for "
            "CREATING a new charge. Do NOT use it to look up or list existing payments."
        ),
    ),
    ToolAliasCluster(
        operation_id="payments_create_payment",
        cluster="amount_phrasings",
        content=(
            "payments_create_payment semantic aliases. Amount and customer phrasings that signal "
            "a new charge: charge 49.90 to the customer, bill them 120 dollars, take 2500 euros "
            "off the card, collect 75 pounds for the invoice, run 199 on their card, charge "
            "customer cus_10428 for the annual plan, bill the account for last month's usage. "
            "The amount is stated in decimals by people and must be converted to minor units."
        ),
    ),
    ToolAliasCluster(
        operation_id="payments_create_refund",
        cluster="direct_verbs",
        content=(
            "payments_create_refund semantic aliases. Direct verbs that mean returning money to "
            "a customer: refund, issue a refund, give the money back, pay them back, return the "
            "payment, reverse the charge, reimburse, credit the customer back, cancel the charge "
            "and return the funds, send back part of what they paid. IMPORTANT: use this only "
            "when money is going BACK to the customer, never for a new charge."
        ),
    ),
    ToolAliasCluster(
        operation_id="payments_create_refund",
        cluster="reasons",
        content=(
            "payments_create_refund semantic aliases. Reason phrasings that accompany a refund: "
            "the customer asked for their money back, they were charged twice, this was a "
            "duplicate, the transaction was fraudulent, we could not ship the product, the item "
            "is out of stock, they cancelled the order, partial refund for the damaged item."
        ),
    ),
    ToolAliasCluster(
        operation_id="payments_list_payments",
        cluster="browse_verbs",
        content=(
            "payments_list_payments semantic aliases. Read-only verbs for browsing many "
            "payments: list payments, show me the payments, what has this customer paid, recent "
            "charges, show the last transactions, which payments are declined, pull up the "
            "payments for this customer, what did we collect, show me everything from cus_10428. "
            "IMPORTANT: this tool only READS. Do NOT use it to charge, refund or move money."
        ),
    ),
    ToolAliasCluster(
        operation_id="payments_get_payment",
        cluster="single_lookup",
        content=(
            "payments_get_payment semantic aliases. Read-only phrasings for one specific "
            "payment: look up payment pay_5f2c1b9a41d0, what is the status of this payment, show "
            "me that charge, did that payment go through, how much of it was refunded, open that "
            "transaction, check this payment id. Use this when the user already has a payment "
            "identifier and wants the state of exactly that one payment."
        ),
    ),
    ToolAliasCluster(
        operation_id="payments_get_balance",
        cluster="balance_questions",
        content=(
            "payments_get_balance semantic aliases. Read-only phrasings about money on the "
            "account: what is our balance, how much money do we have, what is available, how "
            "much is pending, what is ready to pay out, current balance in euros, how much has "
            "settled. This reports the merchant's own balance, not a customer's."
        ),
    ),
    ToolAliasCluster(
        operation_id="payments_create_payout",
        cluster="withdrawal_verbs",
        content=(
            "payments_create_payout semantic aliases. Phrasings that mean sending settled money "
            "to the merchant's own bank account: pay out, payout, withdraw, transfer to our bank "
            "account, move the balance to our account, settle to the bank, send the funds to "
            "ba_9921ff, take the money out, cash out the balance. IMPORTANT: this moves money "
            "out of the business, not to or from a customer."
        ),
    ),
    ToolAliasCluster(
        operation_id="payments_capture_payment",
        cluster="capture_verbs",
        content=(
            "payments_capture_payment semantic aliases. Phrasings that mean taking funds that "
            "were already authorized: capture the authorization, settle the authorized payment, "
            "finalize the hold, take the money we reserved, complete the capture now that it "
            "shipped, capture pay_5f2c1b9a41d0."
        ),
    ),
)
