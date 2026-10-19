from pydantic import BaseModel, Field

class LoginIn(BaseModel):
    ins: str = Field(max_length=32)
    password: str = Field(max_length=128)