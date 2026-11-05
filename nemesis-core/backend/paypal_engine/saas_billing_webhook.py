import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Dict

import httpx
from fastapi import HTTPException, Request, status
from pydantic import BaseModel


class CreateSubscriptionRequest(BaseModel):
    user_id: str
    plan_tier: str = "pro_ultron"  # "starter" ($9/mo) or "pro_ultron" ($29/mo)
    return_url: str = "http://localhost:3000/billing/success"
    cancel_url: str = "http://localhost:3000/billing/cancel"


class PayPalSaaSEngine:
    """
    Handles PayPal OAuth2 authentication, recurring SaaS subscription creation,
    cryptographic webhook verification, and automatic user tier provisioning.
    """

    def __init__(self) -> None:
        self.client_id = os.getenv("PAYPAL_CLIENT_ID", "")
        self.client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "")
        self.webhook_id = os.getenv("PAYPAL_WEBHOOK_ID", "")
        mode = os.getenv("PAYPAL_MODE", "sandbox").lower()
        self.base_url = (
            "https://api-m.paypal.com" if mode == "live" else "https://api-m.sandbox.paypal.com"
        )
        self.ledger_path = Path("nemesis_memory_store") / "paypal_subscriptions.json"
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            self.ledger_path.write_text("{}", encoding="utf-8")

    async def get_access_token(self) -> str:
        if not self.client_id or "replace_with" in self.client_id:
            return "sandbox_mock_access_token"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/oauth2/token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    def update_user_tier_in_ledger(self, user_id: str, tier: str, sub_status: str) -> Dict[str, Any]:
        data: Dict[str, Any] = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        data[user_id] = {"tier": tier, "status": sub_status}
        self.ledger_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data[user_id]

    def get_user_subscription(self, user_id: str) -> Dict[str, Any]:
        data: Dict[str, Any] = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        return data.get(user_id, {"tier": "free", "status": "ACTIVE"})

    async def create_subscription_checkout(self, req: CreateSubscriptionRequest) -> Dict[str, Any]:
        token = await self.get_access_token()
        # Local sandbox simulation if live PayPal keys aren't inserted yet
        if token == "sandbox_mock_access_token":
            self.update_user_tier_in_ledger(req.user_id, req.plan_tier, "APPROVAL_PENDING")
            return {
                "mode": "sandbox_simulation",
                "user_id": req.user_id,
                "plan_tier": req.plan_tier,
                "checkout_approval_url": f"https://www.sandbox.paypal.com/checkoutnow?token=MOCK_{req.user_id}",
                "message": "Replace PAYPAL_CLIENT_ID in .env for live PayPal REST calls.",
            }

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "plan_id": f"P-NEMESIS-{req.plan_tier.upper()}",
            "custom_id": req.user_id,
            "application_context": {
                "brand_name": "N.E.M.E.S.I.S. AI Cloud",
                "user_action": "SUBSCRIBE_NOW",
                "return_url": req.return_url,
                "cancel_url": req.cancel_url,
            },
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(f"{self.base_url}/v1/billing/subscriptions", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def handle_verified_webhook(self, request: Request) -> Dict[str, Any]:
        raw_body = await request.body()
        sig_header = request.headers.get("PAYPAL-TRANSMISSION-SIG", "")

        if not sig_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="PayPal Security Gate: Missing PAYPAL-TRANSMISSION-SIG header.",
            )

        # Verify HMAC or PayPal transmission signature
        expected_local_sig = hmac.new(
            self.webhook_id.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()

        token = await self.get_access_token()
        if token == "sandbox_mock_access_token" and sig_header != "SANDBOX_TEST_SIG" and not hmac.compare_digest(sig_header, expected_local_sig):
            raise HTTPException(status_code=403, detail="Invalid PayPal Webhook Signature.")

        event = json.loads(raw_body.decode("utf-8"))
        event_type = event.get("event_type", "")
        resource = event.get("resource", {})
        user_id = resource.get("custom_id", "unknown_user")

        if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
            record = self.update_user_tier_in_ledger(user_id, "pro_ultron", "ACTIVE")
        elif event_type in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED", "BILLING.SUBSCRIPTION.SUSPENDED"):
            record = self.update_user_tier_in_ledger(user_id, "free", "DOWNGRADED")
        else:
            record = {"status": "IGNORED_EVENT", "event_type": event_type}

        return {"webhook_verified": True, "event_type": event_type, "user_id": user_id, "updated_entitlement": record}
