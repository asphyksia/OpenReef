from pydantic import BaseModel, Field


class CheckoutSessionRequest(BaseModel):
    amount_usd: float = Field(gt=0, le=10000, description="Amount in USD to add as credits")


class DevAddCreditsRequest(BaseModel):
    amount: float = Field(gt=0, le=1000, description="Amount in USD to add as dev credits")


class BalanceResponse(BaseModel):
    balance: float
    currency: str = "USD"
