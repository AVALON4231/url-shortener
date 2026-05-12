import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["SECRET_KEY"] = "test-secret-key-for-tests"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test"

from main import app
from app.dependencies import get_current_user
from app.services.user_service import UserService
from app.services.link_service import LinkService

client = TestClient(app)


# -----------------------------------------------------------
# Тесты для /register
# -----------------------------------------------------------
def test_register_success(mocker):
    mocker.patch.object(UserService, 'register', return_value=True)
    response = client.post("/register", json={"email": "test@example.com", "password": "secret"})
    assert response.status_code == 200
    assert response.json() == {"message": "User created"}


def test_register_duplicate(mocker):
    mocker.patch.object(UserService, 'register', return_value=False)
    response = client.post("/register", json={"email": "duplicate@example.com", "password": "123456"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already exists"


def test_register_missing_params():
    response = client.post("/register", json={"email": "test@example.com"})
    assert response.status_code == 422
    response = client.post("/register", json={"password": "secret"})
    assert response.status_code == 422


# -----------------------------------------------------------
# Тесты для /login
# -----------------------------------------------------------
def test_login_success(mocker):
    fake_user = {"id": 1, "email": "test@example.com", "hashed_password": "hashed"}
    mocker.patch.object(UserService, 'authenticate', return_value=fake_user)
    response = client.post("/login", data={"username": "test@example.com", "password": "secret"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert len(data["access_token"]) > 0


def test_login_invalid_credentials(mocker):
    mocker.patch.object(UserService, 'authenticate', return_value=None)
    response = client.post("/login", data={"username": "test@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_login_user_not_found(mocker):
    mocker.patch.object(UserService, 'authenticate', return_value=None)
    response = client.post("/login", data={"username": "unknown@example.com", "password": "secret"})
    assert response.status_code == 401


# -----------------------------------------------------------
# Тесты для /shorten
# -----------------------------------------------------------
def test_shorten_unauthorized():
    response = client.post("/shorten", json={"url": "https://example.com"})
    assert response.status_code == 401


def test_shorten_success(mocker):
    fake_user = {"id": 1, "email": "test@example.com"}
    async def fake_get_current_user():
        return fake_user

    mocker.patch("socket.gethostbyname", return_value="93.184.216.34")
    mocker.patch.object(
        LinkService,
        'create_short_link',
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
    mocker.patch("app.repositories.link_repository.LinkRepository.get_stats", return_value=fake_stats)
    try:
        response = client.get("/stats/abc123")
        assert response.status_code == 200
        assert response.json() == fake_stats
    finally:
        app.dependency_overrides.clear()


def test_stats_not_found_or_foreign(mocker):
    fake_user = {"id": 1, "email": "test@example.com"}
    async def fake_get_current_user():
        return fake_user
    app.dependency_overrides[get_current_user] = fake_get_current_user
    mocker.patch("app.repositories.link_repository.LinkRepository.get_stats", return_value=None)
    try:
        response = client.get("/stats/xyz789")
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"
    finally:
        app.dependency_overrides.clear()

# -----------------------------------------------------------
# Тест кэша напрямую через LinkService (модульный)
# -----------------------------------------------------------
def test_link_service_cache(mocker):
    from app.services.link_service import LinkService
    from app.repositories.link_repository import LinkRepository

    # Создаём экземпляр сервиса с замоканным репозиторием
    mock_repo = mocker.Mock(wraps=LinkRepository())
    mock_repo.get_original_url = mocker.Mock(return_value="https://example.com")
    service = LinkService(link_repo=mock_repo)

    # Первый вызов — репозиторий должен быть вызван
    url1 = service.get_original_url_cached("abc123")
    assert url1 == "https://example.com"
    assert mock_repo.get_original_url.call_count == 1

    # Второй вызов — должен взять из кэша, репозиторий не вызывается
    url2 = service.get_original_url_cached("abc123")
    assert url2 == "https://example.com"
    assert mock_repo.get_original_url.call_count == 1  # не изменилось

    # Инвалидируем кэш и вызываем снова — репозиторий должен быть вызван повторно
    service.invalidate_url_cache("abc123")
    url3 = service.get_original_url_cached("abc123")
    assert url3 == "https://example.com"
    assert mock_repo.get_original_url.call_count == 2