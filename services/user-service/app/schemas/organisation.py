from pydantic import BaseModel, ConfigDict


class OrganisationPublic(BaseModel):
    organisationId: str
    name: str

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {"organisationId": "org-1", "name": "Apex Partners"}
        },
    )
