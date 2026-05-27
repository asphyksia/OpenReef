from pydantic import BaseModel


class CheckoutSessionRequest(BaseModel):
    amount_usd: float  # amount to add as credits


class DevAddCreditsRequest(BaseModel):
    amount: float


class BalanceResponse(BaseModel):
    balance: float
    currency: str = "USD"
