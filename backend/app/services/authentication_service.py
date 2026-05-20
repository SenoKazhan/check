# backend/app/services/authentication_service.py
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError, JWTClaimsError
from app.core.config import ApplicationSettings
from app.domain.exceptions import DomainException


class AuthenticationService:
    def __init__(self, settings: ApplicationSettings):
        self._settings = settings

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt(rounds=self._settings.bcrypt_cost)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

    def create_access_token(self, subject: str, role: str, expires_delta: timedelta | None = None) -> str:
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(
            minutes=self._settings.access_token_expire_minutes))
        payload = {
            "sub": str(subject),
            "role": role,
            "exp": int(expire.timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp())
        }
        return jwt.encode(payload, self._settings.jwt_secret_key, algorithm=self._settings.jwt_algorithm)

    def decode_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._settings.jwt_secret_key, algorithms=[self._settings.jwt_algorithm])
        except ExpiredSignatureError:
            raise DomainException("Token expired")
        except (JWTClaimsError, JWTError):
            raise DomainException("Invalid token")
