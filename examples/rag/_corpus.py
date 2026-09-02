from __future__ import annotations

from typing import Any, Dict, Final, List

HANDBOOK: Final[str] = """Expense reimbursement policy.

Every corporate expense needs a legible tax receipt attached within seven calendar days
of the purchase date. Receipts submitted after that deadline go into the exception
queue and depend on approval from the direct manager.

Limits by category.

Meals while travelling are capped at one hundred and twenty dollars per person per day.
Urban transport has no fixed limit, but any trip above eighty dollars requires a written
justification. Lodging follows the regional table published every quarter by the finance
team.

Corporate card.

The corporate card is personal and non-transferable. Purchases split into instalments
are only allowed for equipment approved in advance. The statement closes on the
twenty-fifth and the accounting close runs on the last business day of the month.

Mileage reimbursement.

Trips taken in a personal vehicle are reimbursed per mile driven according to the
current table. You must state the origin, the destination and the purpose of the trip.
Trips between home and the office are not reimbursable.

Payment cycles.

Reimbursements approved by the twentieth are paid in the current month's cycle. Later
approvals move to the following cycle. Payments are made only into a checking account
held by the employee themselves.
"""

PAGES: Final[List[str]] = [
    "Page 1. Reimbursement policy: tax receipt within seven calendar days.",
    "Page 2. Limits: meals one hundred and twenty dollars per day; transport needs a "
    "justification above eighty dollars.",
    "Page 3. Corporate card: personal and non-transferable, statement closes on the twenty-fifth.",
    "Page 4. Mileage: state origin, destination and purpose; home to office does not count.",
    "Page 5. Payment: approved by the twentieth go into the current month's cycle.",
]

KNOWLEDGE_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "doc_type": "policy_reimbursement",
        "content": (
            "Expense reimbursement: every tax receipt must be submitted within seven calendar "
            "days of the purchase. After that deadline, the request needs manager approval."
        ),
        "metadata": {"topic": "reimbursement", "audience": "employee"},
    },
    {
        "doc_type": "policy_limits",
        "content": (
            "Limits by category: meals while travelling are capped at one hundred and twenty "
            "dollars per person per day. Urban transport above eighty dollars requires a "
            "written justification."
        ),
        "metadata": {"topic": "limits", "audience": "employee"},
    },
    {
        "doc_type": "policy_card",
        "content": (
            "The corporate card is personal and non-transferable. The statement closes on the "
            "twenty-fifth and purchases split into instalments require prior approval."
        ),
        "metadata": {"topic": "card", "audience": "employee"},
    },
    {
        "doc_type": "manual_vacation",
        "content": (
            "Vacation must be requested thirty days in advance. The minimum period is five "
            "calendar days and it depends on approval from the direct manager."
        ),
        "metadata": {"topic": "vacation", "audience": "manager"},
    },
]


def token_estimate(text: str) -> int:
    import tiktoken

    return len(tiktoken.get_encoding("cl100k_base").encode(text))
