import aiohttp
from app.repositories.link_repository import LinkRepository


class LinkService:
    def __init__(self, link_repo: LinkRepository = None):
        self.link_repo = link_repo or LinkRepository()

    async def create_short_link(self, url: str, user_id: int) -> str:
        short_code = self.link_repo.create_short_link(url, user_id)
        title = await self._fetch_title(url)
        self.link_repo.update_link_title(short_code, title)
        return short_code

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