from pydantic import BaseModel, Field

from clerk.schemas.staff import StaffRole, StaffUserOut


class TokenOut(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    username: str
    role: StaffRole = "staff"
    mfa_required: bool = False
    mfa_token: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=512)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class DemoStatusOut(BaseModel):
    available: bool


class MfaLoginRequest(BaseModel):
    mfa_token: str = Field(min_length=16, max_length=512)
    code: str = Field(min_length=6, max_length=32)


class MessageOut(BaseModel):
    message: str
    dev_reset_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    password: str = Field(min_length=8, max_length=128)


class UpdateEmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class MeOut(BaseModel):
    user: StaffUserOut
    mfa_enabled: bool = False
    demo_desk: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class MfaSetupRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class MfaSetupOut(BaseModel):
    secret: str
    otpauth_uri: str
    qr_data_uri: str


class MfaCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class MfaConfirmOut(BaseModel):
    recovery_codes: list[str]


class MfaDisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=32)
