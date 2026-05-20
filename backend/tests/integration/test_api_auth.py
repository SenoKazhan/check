# backend/tests/integration/test_api_auth.py
import pytest
from httpx import AsyncClient

@pytest.mark.usefixtures("setup_test_database")
class TestAuthAPI:
    
    @pytest.mark.asyncio
    async def test_login_success(self, client, db_session, test_user_data):
        # Сначала создаём пользователя в БД
        from app.db.models.user import User
        from app.auth.manager import AuthManager
        
        user = User(
            login=test_user_data["login"],
            password_hash=AuthManager.hash_password(test_user_data["password"]),
            role=test_user_data["role"]
        )
        db_session.add(user)
        await db_session.commit()
        
        # Тест логина
        response = client.post("/auth/login", json={
            "login": test_user_data["login"],
            "password": test_user_data["password"]
        })
        assert response.status_code == 200
        assert "access_token" in response.cookies
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client):
        response = client.post("/auth/login", json={
            "login": "wrong",
            "password": "wrong"
        })
        assert response.status_code == 401
    
    def test_login_validation_error(self, client):
        response = client.post("/auth/login", json={
            "login": "a",  # слишком короткий (min_length=3)
            "password": "123"  # слишком короткий (min_length=6)
        })
        assert response.status_code == 422