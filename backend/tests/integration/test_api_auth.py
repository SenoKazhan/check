# backend/tests/integration/test_api_auth.py
import pytest
import time
from app.db.models.user import User
from app.auth.manager import AuthManager

@pytest.mark.anyio
async def test_login_success(async_client, db_session):
    unique_login = f"test_user_{int(time.time())}"
    password = "testpass123"
    
    user = User(
        login=unique_login,
        password_hash=AuthManager.hash_password(password),
        role="worker"
    )
    db_session.add(user)
    await db_session.commit()
    
    response = await async_client.post("/auth/login", json={
        "login": unique_login,
        "password": password
    })
    assert response.status_code == 200
    assert "access_token" in response.cookies



@pytest.mark.anyio
async def test_login_validation_error(async_client):
    response = await async_client.post("/auth/login", json={
        "login": "ab",
        "password": "123"
    })
    assert response.status_code == 422