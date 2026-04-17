from dataclasses import dataclass

from fastapi import Header, HTTPException
from jose import JWTError, jwt

from .config import parse_scopes, settings


@dataclass
class AuthContext:
    subject: str
    role: str
    scopes: set[str]
    auth_type: str
    merchant_id: str | None = None


def _ensure_scopes(context: AuthContext, required_scopes: set[str]) -> None:
    if required_scopes and not required_scopes.issubset(context.scopes):
        raise HTTPException(status_code=403, detail="Insufficient scope")


def _ensure_role(context: AuthContext, allowed_roles: set[str] | None) -> None:
    if allowed_roles and context.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Role not permitted")


def require_auth(
    *,
    required_scopes: set[str] | None = None,
    allowed_roles: set[str] | None = None,
):
    async def dependency(
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ) -> AuthContext:
        if authorization:
            if not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Invalid token")
            token = authorization.split(" ", 1)[1]
            try:
                payload = jwt.decode(
                    token,
                    settings.JWT_SECRET,
                    algorithms=["HS256"],
                    issuer=settings.JWT_ISSUER,
                    audience=settings.JWT_AUDIENCE,
                )
            except JWTError as exc:
                raise HTTPException(status_code=401, detail="Invalid token") from exc

            subject = payload.get("sub")
            if not subject:
                raise HTTPException(status_code=401, detail="Invalid token subject")

            context = AuthContext(
                subject=subject,
                role=payload.get("role", "user"),
                scopes=set(parse_scopes(payload.get("scopes") or payload.get("scope"))),
                auth_type="jwt",
            )
            _ensure_scopes(context, required_scopes or set())
            _ensure_role(context, allowed_roles)
            return context

        if x_api_key:
            for merchant_id, credentials in settings.merchant_credentials().items():
                if x_api_key == credentials.get("api_key"):
                    context = AuthContext(
                        subject=merchant_id,
                        merchant_id=merchant_id,
                        role=credentials.get("role", "merchant"),
                        scopes=set(parse_scopes(credentials.get("scopes"))),
                        auth_type="api_key",
                    )
                    _ensure_scopes(context, required_scopes or set())
                    _ensure_role(context, allowed_roles)
                    return context
            raise HTTPException(status_code=401, detail="Invalid API key")

        raise HTTPException(status_code=401, detail="Authentication required")

    return dependency


get_current_user = require_auth()
