class MockAuthService:
    def __init__(self):
        self.calls = []

    def validate_token(self, token: str) -> dict:
        self.calls.append({"method": "validate_token", "token": token})
        if token == "valid-token":
            return {"valid": True, "user_id": 1}
        return {"valid": False}
