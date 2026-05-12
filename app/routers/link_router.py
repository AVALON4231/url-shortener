from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from app.controllers.link_controller import (
    shorten_controller, my_links_controller, delete_link_controller,
    stats_controller, redirect_controller
)
from app.dependencies import get_current_user, limiter, ShortenRequest
import socket
from urllib.parse import urlparse

router = APIRouter()


def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def is_safe_host(hostname: str) -> bool:
    try:
        ip = socket.gethostbyname(hostname)
        return not ip.startswith(("127.", "10.", "192.168.", "172."))
    except Exception:
        return False


@router.post("/shorten")
@limiter.limit("10/minute")
async def shorten(request: Request, data: ShortenRequest, current_user: dict = Depends(get_current_user)):
    url = data.url
    if not url or len(url) > 2048:
        raise HTTPException(400, "Invalid URL length")
    if not is_valid_url(url):
        raise HTTPException(400, "Invalid URL. Only http:// and https:// are allowed")
    parsed = urlparse(url)
    if not is_safe_host(parsed.hostname):
        raise HTTPException(400, "Unsafe host")
    return await shorten_controller(url, request, current_user)


@router.get("/my-links")
async def my_links(request: Request, current_user: dict = Depends(get_current_user)):
    return await my_links_controller(request, current_user)


@router.delete("/my-links/{short_code}")
async def delete_link(short_code: str, current_user: dict = Depends(get_current_user)):
    return await delete_link_controller(short_code, current_user)


@router.get("/stats/{short_code}")
async def stats(short_code: str, current_user: dict = Depends(get_current_user)):
    return await stats_controller(short_code, current_user)


@router.get("/{short_code}")
async def redirect(short_code: str, request: Request):
    original = await redirect_controller(short_code)
    return RedirectResponse(original)