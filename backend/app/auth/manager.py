"""Менеджер аутентификации: хэширование паролей, JWT."""
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthManager:
    @staticmethod
    def hash_password(password: str) -> str:
        """Хэширует пароль через bcrypt."""
        salt = bcrypt.gensalt(rounds=settings.bcrypt_cost)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        """Проверяет пароль против хэша."""
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
        to_encode = data.copy()

        # ✅ КРИТИЧНО: python-jose требует str в поле sub
        to_encode["sub"] = str(to_encode.get("sub"))

        expire = datetime.now(
            timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
        to_encode.update({"exp": int(expire.timestamp()), "iat": int(
            datetime.now(timezone.utc).timestamp())})

        return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def decode_token(token: str) -> dict | None:
        """Декодирует и верифицирует JWT-токен."""
        try:
            logger.debug(
                f"🔐 Decoding with key={settings.jwt_secret_key[:10]}..., alg={settings.jwt_algorithm}")

            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": True}  # Явно включаем проверку exp
            )

            logger.debug(f"✅ Decoded payload: {payload}")
            return payload

        except ExpiredSignatureError:
            logger.warning("⏰ Token expired")
            return None
        except JWTClaimsError as e:
            logger.error(f"📋 Claims error: {e}")
            return None
        except JWTError as e:
            logger.error(f"❌ JWTError: {type(e).__name__}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"❌ Unexpected error: {type(e).__name__}: {e}", exc_info=True)
            return None
        except JWTError as e:
            # Выводим детали для отладки
            import base64
            import json
            try:
                parts = token.split('.')
                if len(parts) == 3:
                    header = json.loads(
                        base64.urlsafe_b64decode(parts[0] + '=='))
                    payload_raw = json.loads(
                        base64.urlsafe_b64decode(parts[1] + '=='))
                    logger.error(f"🔍 Token header: {header}")
                    logger.error(f"🔍 Token payload (raw): {payload_raw}")
            except Exception:
                pass
            logger.error(f"❌ JWTError: {type(e).__name__}: {e}")
            return None
