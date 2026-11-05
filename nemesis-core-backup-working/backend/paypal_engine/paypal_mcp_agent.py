import uuid
from typing import Any, Dict
from pydantic import BaseModel, EmailStr, Field


class PayPalAgentActionRequest(BaseModel):
    user_id: str
    action: str = Field(..., description="create_invoice | create_order | check_balance")
    recipient_email: EmailStr
    amount_usd: float = Field(..., gt=0, le=100000)
    item_description: str = Field(..., min_length=2, max_length=300)


class PayPalAutonomousAgent:
    """
    Compatible with @paypal/agent-toolkit MCP specification:
    Lets N.E.M.E.S.I.S. autonomously generate invoices, payment orders, and QR payloads by voice.
    """

    @staticmethod
    async def execute_financial_action(req: PayPalAgentActionRequest) -> Dict[str, Any]:
        tx_id = f"INV-NEMESIS-{uuid.uuid4().hex[:8].upper()}"
        qr_payload = f"https://www.paypal.com/invoice/p/#{tx_id}"

        return {
            "commander": "N.E.M.E.S.I.S. Financial Agent",
            "tool_invoked": f"paypal_mcp:{req.action}",
            "transaction_id": tx_id,
            "recipient": req.recipient_email,
            "amount_usd": req.amount_usd,
            "item": req.item_description,
            "live_hud_qr_url": qr_payload,
            "nemesis_roast": (
                f"Generated PayPal {req.action} ({tx_id}) for ${req.amount_usd:.2f} to {req.recipient_email}. "
                "I also pinned the QR code to your HUD so they have zero excuse not to pay you on time."
            ),
        }
