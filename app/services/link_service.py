import time
import aiohttp
from app.repositories.link_repository import LinkRepository


class LinkService:
    def __init__(self, link_repo: LinkRepository = None):
        self.link_repo = link_repo or LinkRepository()
        self._url_cache: dict[str, tuple[str, float]] = {}
        self._title_cache: dict[str, tuple[str, float]] = {}

    def _cache_get(self, cache: dict, key: str):
        entry = cache.get(key)
        if entry and entry[1] > time.time():
            return entry[0]
        return None

    def _cache_set(self, cache: dict, key: str, value: str, ttl: int = 300):
        cache[key] = (value, time.time() + ttl)

    def get_original_url_cached(self, short_code: str) -> str | None:
        cached = self._cache_get(self._url_cache, short_code)
        if cached:
            return cached
        url = self.link_repo.get_original_url(short_code)
        if url:
            self._cache_set(self._url_cache, short_code, url)
        return url

    def invalidate_url_cache(self, short_code: str):
        self._url_cache.pop(short_code, None)

    async def create_short_link(self, url: str, user_id: int) -> str:
        short_code = self.link_repo.create_short_link(url, user_id)
        title = await self._fetch_title_cached(url)
        self.link_repo.update_link_title(short_code, title)
        return short_code

    async def _fetch_title_cached(self, url: str) -> str:
        cached = self._cache_get(self._title_cache, url)
        if cached:
            return cached
        title = await self._fetch_title(url)
        self._cache_set(self._title_cache, url, title)
        return title

    async def _fetch_title(self, url: str) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "ShortURL Bot/1.0"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=2), headers=headers) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        start = html.lower().find('<title>')
                        end = html.lower().find('</title>', start)
                        if start != -1 and end != -1:
                            return html[start + 7:end].strip()[:200]
        except Exception:
            pass
        return url