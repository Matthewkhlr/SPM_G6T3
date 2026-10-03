from pydantic import BaseModel, ConfigDict, Field


class UserPublic(BaseModel):
    userId: str = Field(description="ConnectSphere user id, e.g. `u1`.")
    userName: str = Field(description="Display name.")
    email: str
    role: str = Field(
        description="One of `organiser`, `coordinator`, `venue`, `techsupport`, `attendee`."
    )
    organisationId: str | None = Field(
        default=None, description="Set for event organisers; otherwise null."
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "userId": "u1",
                "userName": "Alice Tan",
                "email": "organiser@connectsphere.com",
                "role": "organiser",
                "organisationId": "org-1",
            }
        },
    )
