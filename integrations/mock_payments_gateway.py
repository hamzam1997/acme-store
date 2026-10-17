class MockPaymentsGateway:
    def __init__(self, *args, **kwargs):
        self.refund_calls = []
        self.charge_calls = []

    @property
    def configured(self) -> bool:
        return True

    def charge(self, amount_cents: int, description: str = "") -> dict:
        self.charge_calls.append({"amount_cents": amount_cents, "description": description})
        return {
            "reference": "mock_pay_123",
            "amount_cents": amount_cents,
            "description": description,
            "status": "captured",
        }

    def refund(self, provider_ref: str) -> dict:
        self.refund_calls.append({"provider_ref": provider_ref})
        return {
            "reference": provider_ref,
            "status": "refund_pending",
        }
