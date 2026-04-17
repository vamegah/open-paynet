from datetime import datetime, timedelta, timezone
import hmac

from fastapi import FastAPI, Header, HTTPException
from jose import jwt
from pydantic import BaseModel, Field
from shared.config import env_flag, env_int, env_text, load_json_config, load_secret, parse_api_keys, parse_scopes


class Settings:
    JWT_SECRET = load_secret("JWT_SECRET", default="supersecret")
    TOKEN_ISSUER_ADMIN_KEY = load_secret("TOKEN_ISSUER_ADMIN_KEY", default="issuer-admin-key")
    JWT_ISSUER = env_text("JWT_ISSUER", "openpaynet-auth")
    JWT_AUDIENCE = env_text("JWT_AUDIENCE", "openpaynet-api")
    DEFAULT_SUBJECT_ROLE = env_text("DEFAULT_SUBJECT_ROLE", "payment_initiator")
    DEFAULT_SUBJECT_SCOPES = parse_scopes(env_text("DEFAULT_SUBJECT_SCOPES", "payments:write ledger:read"))
    SUBJECT_POLICIES = load_json_config("SUBJECT_POLICIES_JSON", default={})
    MERCHANT_CREDENTIALS = load_json_config("MERCHANT_CREDENTIALS_JSON", default={})
    LEGACY_MERCHANT_API_KEYS = env_text("MERCHANT_API_KEYS", "")
    MAX_TOKEN_TTL_SECONDS = env_int("MAX_TOKEN_TTL_SECONDS", 3600)

    @classmethod
    def merchant_credentials(cls) -> dict[str, dict]:
        credentials = dict(cls.MERCHANT_CREDENTIALS)
        if not credentials and cls.LEGACY_MERCHANT_API_KEYS:
            credentials = parse_api_keys(cls.LEGACY_MERCHANT_API_KEYS)
        return credentials

    @classmethod
    def subject_policy(cls, subject: str) -> dict | None:
        raw_policy = cls.SUBJECT_POLICIES.get(subject) or cls.SUBJECT_POLICIES.get("*")
        if raw_policy is None:
            if env_flag("ALLOW_INSECURE_DEFAULT_SECRETS"):
                raw_policy = {}
            else:
                return None
        return {
            "role": raw_policy.get("role", cls.DEFAULT_SUBJECT_ROLE),
            "scopes": parse_scopes(raw_policy.get("scopes", cls.DEFAULT_SUBJECT_SCOPES)),
            "allowed_roles": parse_scopes(raw_policy.get("allowed_roles", [raw_policy.get("role", cls.DEFAULT_SUBJECT_ROLE)])),
        }


settings = Settings()


class TokenRequest(BaseModel):
    subject: str
    expires_in_seconds: int = 3600
    requested_scopes: list[str] = Field(default_factory=list)
    requested_role: str | None = None


class ApiKeyValidationRequest(BaseModel):
    api_key: str


app = FastAPI(title="OpenPayNet Auth Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/token")
async def issue_token(
    payload: TokenRequest,
    x_token_issuer_key: str | None = Header(default=None),
) -> dict[str, str | list[str]]:
    if not x_token_issuer_key or not hmac.compare_digest(x_token_issuer_key, settings.TOKEN_ISSUER_ADMIN_KEY):
        raise HTTPException(status_code=401, detail="Token issuer authentication required")

    if payload.expires_in_seconds <= 0 or payload.expires_in_seconds > settings.MAX_TOKEN_TTL_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"expires_in_seconds must be between 1 and {settings.MAX_TOKEN_TTL_SECONDS}",
        )

    policy = settings.subject_policy(payload.subject)
    if policy is None:
        raise HTTPException(status_code=403, detail="Subject is not permitted to receive tokens")

    allowed_scopes = set(policy["scopes"])
    requested_scopes = set(payload.requested_scopes or policy["scopes"])

    if not requested_scopes.issubset(allowed_scopes):
        raise HTTPException(status_code=400, detail="Requested scopes exceed subject policy")

    role = payload.requested_role or policy["role"]
    if role not in set(policy["allowed_roles"]):
        raise HTTPException(status_code=400, detail="Requested role is not permitted for subject")

    now = datetime.now(timezone.utc)
    scopes = sorted(requested_scopes)
    token = jwt.encode(
        {
            "sub": payload.subject,
            "role": role,
            "scopes": scopes,
            "scope": " ".join(scopes),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=payload.expires_in_seconds)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer", "role": role, "scopes": scopes}


@app.post("/v1/validate-api-key")
async def validate_api_key(payload: ApiKeyValidationRequest) -> dict[str, str | list[str]]:
    for merchant_id, credentials in settings.merchant_credentials().items():
        if payload.api_key == credentials.get("api_key"):
            return {
                "merchant_id": merchant_id,
                "status": "valid",
                "role": credentials.get("role", "merchant"),
                "scopes": parse_scopes(credentials.get("scopes")),
            }
    raise HTTPException(status_code=401, detail="Invalid API key")
