from pydantic import BaseModel


class UserPublic(BaseModel):
    userId: str
    userName: str
    email: str
    role: str

    class Config:
        from_attributes = True
