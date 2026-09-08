from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    userId: str
    userName: str
    email: str
    role: str

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str = Field(description="Email used as username in the Vue demo")
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserPublic
