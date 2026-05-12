from fastapi import HTTPException, Request
from app.services.link_service import LinkService
from app.repositories.link_repository import LinkRepository

link_service = LinkService()
link_repo = LinkRepository()


async def shorten_controller(url: str, request: Request, current_user):
    short_code = await link_service.create_short_link(url, current_user["id"])
    base = request.headers.get("x-forwarded-proto", request.url.scheme) + "://"
    base += request.headers.get("x-forwarded-host", request.headers.get("host", "127.0.0.1:8000"))
    return {
        "short_url": f"{base}/{short_code}",
        "short_code": short_code
    }


async def my_links_controller(request: Request, current_user):
    links = link_repo.get_user_links(current_user["id"])
    base = request.headers.get("x-forwarded-proto", request.url.scheme) + "://"
    base += request.headers.get("x-forwarded-host", request.headers.get("host", "127.0.0.1:8000"))
    for link in links:
        link["short_url"] = f"{base}/{link['short_code']}"
    return links


async def delete_link_controller(short_code: str, current_user):
    deleted = link_repo.delete_link(short_code, current_user["id"])
    if not deleted:
        raise HTTPException(404, "Not found")
    link_service.invalidate_url_cache(short_code)
    return {"message": "Deleted"}


async def stats_controller(short_code: str, current_user):
    stats = link_repo.get_stats(short_code, current_user["id"])
    if not stats:
        raise HTTPException(404, "Not found")
    return stats


def redirect_controller(short_code: str):
    original = link_service.get_original_url_cached(short_code)
    if not original:
        raise HTTPException(404, "Not found")
    link_repo.increment_clicks(short_code)
    return original