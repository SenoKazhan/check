# tests/test_schemas.py
import pytest
from app.schemas.auth import LoginRequest, UserResponse
from app.schemas.packing import Item, Placement, PackResult
from pydantic import ValidationError

def test_login_request_valid():
    req = LoginRequest(login="alice", password="secret123")
    assert req.login == "alice"
    assert req.password == "secret123"

def test_login_request_invalid():
    with pytest.raises(ValidationError):
        LoginRequest(login="ab", password="123")  # слишком короткие

def test_user_response():
    resp = UserResponse(id=1, login="bob", role="worker")
    assert resp.model_dump() == {"id": 1, "login": "bob", "role": "worker"}

def test_packing_item():
    item = Item(product_id=5, length_mm=100, width_mm=80, height_mm=60, quantity=2)
    assert item.quantity == 2

def test_placement():
    place = Placement(item_id=5, x_mm=10, y_mm=20, z_mm=30, rotated=False)
    assert place.rotated is False