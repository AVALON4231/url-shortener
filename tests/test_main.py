import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

os.environ["SECRET_KEY"] = "test-secret-key-for-tests"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test"

import database
from main import app, get_current_user

client = TestClient(app)


# -----------------------------------------------------------
# Тесты для /register (JSON-тело)
# -----------------------------------------------------------
def test_register_success(mocker):
    mocker.patch("database.create_user", return_value=True)
    response = client.post("/register", json={"email": "test@example.com", "password": "secret"})
    assert response.status_code == 200
    assert response.json() == {"message": "User created"}


def test_register_duplicate(mocker):
    mocker.patch("database.create_user", return_value=False)
    response = client.post("/register", json={"email": "duplicate@example.com", "password": "123456"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already exists"


def test_register_missing_params():
    # нет password
    response = client.post("/register", json={"email": "test@example.com"})
    assert response.status_code == 422
    # нет email
    response = client.post("/register", json={"password": "secret"})
    assert response.status_code == 422


# -----------------------------------------------------------
# Тесты для /login
# -----------------------------------------------------------
def test_login_success(mocker):
    fake_user = {"id": 1, "email": "test@example.com", "hashed_password": "hashed"}
    mocker.patch("database.get_user_by_email", return_value=fake_user)
    mocker.patch("database.verify_password", return_value=True)
    response = client.post("/login", data={"username": "test@example.com", "password": "secret"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    # Проверяем, что токен не пустой
    assert len(data["access_token"]) > 0


def test_login_invalid_credentials(mocker):
    fake_user = {"id": 1, "email": "test@example.com", "hashed_password": "hashed"}
    mocker.patch("database.get_user_by_email", return_value=fake_user)
    mocker.patch("database.verify_password", return_value=False)
    response = client.post("/login", data={"username": "test@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_login_user_not_found(mocker):
    mocker.patch("database.get_user_by_email", return_value=None)
    response = client.post("/login", data={"username": "unknown@example.com", "password": "secret"})
    assert response.status_code == 401


# -----------------------------------------------------------
# Тесты для /shorten (POST + сервисный слой + замоканный DNS)
# -----------------------------------------------------------
def test_shorten_unauthorized():
    response = client.post("/shorten", json={"url": "https://example.com"})
    assert response.status_code == 401


def test_shorten_success(mocker):
    fake_user = {"id": 1, "email": "test@example.com"}
    async def fake_get_current_user():
        return fake_user

    # Мокаем DNS-запрос, чтобы сработала проверка is_safe_host
    mocker.patch("socket.gethostbyname", return_value="93.184.216.34")  # example.com

    # Мокаем сервисный слой
    mocker.patch(
        "services.link_service.create_short_link",
        new_callable=AsyncMock,
        return_value="abc123"
    )

    app.dependency_overrides[get_current_user] = fake_get_current_user
    try:
        response = client.post("/shorten", json={"url": "https://example.com/long-url"})
        assert response.status_code == 200
        data = response.json()
        assert data["short_code"] == "abc123"
        assert data["short_url"] == "http://testserver/abc123"
        from services import link_service
        link_service.create_short_link.assert_called_once_with(
            "https://example.com/long-url", 1
        )
    finally:
        app.dependency_overrides.clear()


def test_shorten_missing_url(mocker):
    fake_user = {"id": 1, "email": "test@example.com"}
    async def fake_get_current_user():
        return fake_user
    app.dependency_overrides[get_current_user] = fake_get_current_user
    try:
        response = client.post("/shorten", json={})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


# -----------------------------------------------------------
# Тесты для /stats
# -----------------------------------------------------------
def test_stats_unauthorized():
    response = client.get("/stats/abc123")
    assert response.status_code == 401


def test_stats_success(mocker):
    fake_user = {"id": 1, "email": "test@example.com"}
    async def fake_get_current_user():
        return fake_user
    app.dependency_overrides[get_current_user] = fake_get_current_user
    fake_stats = {
        "original_url": "https://example.com",
        "short_code": "abc123",
        "clicks": 10,
        "created_at": "2026-05-11T14:00:00"
    }
    mocker.patch("database.get_stats", return_value=fake_stats)
    try:
        response = client.get("/stats/abc123")
        assert response.status_code == 200
        assert response.json() == fake_stats
        database.get_stats.assert_called_once_with("abc123", 1)
    finally:
        app.dependency_overrides.clear()


def test_stats_not_found_or_foreign(mocker):
    fake_user = {"id": 1, "email": "test@example.com"}
    async def fake_get_current_user():
        return fake_user
    app.dependency_overrides[get_current_user] = fake_get_current_user
    mocker.patch("database.get_stats", return_value=None)
    try:
        response = client.get("/stats/xyz789")
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"
    finally:
        app.dependency_overrides.clear()