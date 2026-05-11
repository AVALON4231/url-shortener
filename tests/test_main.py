import os
import pytest
from fastapi.testclient import TestClient

os.environ["SECRET_KEY"] = "test-secret-key-for-tests"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test"

import database
from main import app, get_current_user

client = TestClient(app)


# -----------------------------------------------------------
# Тесты для /register
# -----------------------------------------------------------
def test_register_success(mocker):
    mocker.patch("database.create_user", return_value=True)
    response = client.post("/register?email=test@example.com&password=secret")
    assert response.status_code == 200
    assert response.json() == {"message": "User created successfully"}


def test_register_duplicate(mocker):
    mocker.patch("database.create_user", return_value=False)
    response = client.post("/register?email=duplicate@example.com&password=123456")
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_register_missing_params():
    response = client.post("/register?email=test@example.com")  # нет password
    assert response.status_code == 422
    response = client.post("/register?password=secret")  # нет email
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
    assert data["token_type"] == "bearer"


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
# Тесты для /shorten
# -----------------------------------------------------------
def test_shorten_unauthorized():
    response = client.get("/shorten?url=https://example.com")
    assert response.status_code == 401


def test_shorten_success(mocker):
    fake_user = {"id": 1, "email": "test@example.com"}
    async def fake_get_current_user():
        return fake_user
    # Мокаем aiohttp, чтобы избежать реальных HTTP-запросов
    mocker.patch("aiohttp.ClientSession")
    # Мокаем обновление заголовка, чтобы не лезть в реальную базу
    mocker.patch("database.update_link_title")
    app.dependency_overrides[get_current_user] = fake_get_current_user
    mocker.patch("database.create_short_link", return_value="abc123")
    try:
        response = client.get("/shorten?url=https://example.com/long-url")
        assert response.status_code == 200
        data = response.json()
        assert data["original_url"] == "https://example.com/long-url"
        assert data["short_code"] == "abc123"
        assert data["short_url"] == "http://testserver/abc123"
        database.create_short_link.assert_called_once_with("https://example.com/long-url", 1)
    finally:
        app.dependency_overrides.clear()


def test_shorten_missing_url(mocker):
    fake_user = {"id": 1, "email": "test@example.com"}
    async def fake_get_current_user():
        return fake_user
    app.dependency_overrides[get_current_user] = fake_get_current_user
    try:
        response = client.get("/shorten")  # без ?url=
        # FastAPI сам возвращает 422, т.к. url обязателен
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
        assert response.json()["detail"] == "Short link not found or not yours"
    finally:
        app.dependency_overrides.clear()