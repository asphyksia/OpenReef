import uuid
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_verified: bool
    balance: float

    model_config = {"from_attributes": True}
