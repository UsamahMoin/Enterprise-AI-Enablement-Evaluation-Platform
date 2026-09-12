from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    job_role: str
    system_role: str
    department_id: str | None = None
    department_name: str | None = None

    model_config = {"from_attributes": True}


TokenResponse.model_rebuild()
