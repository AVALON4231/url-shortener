import aiohttp
import database


class LinkService:
    """
    Сервисный слой для работы со ссылками.
    Отвечает за создание короткой ссылки и асинхронное
    получение заголовка страницы — чтобы main.py не занимался этим сам.
    """

    async def create_short_link(self, url: str, user_id: int) -> str:
        # Сначала сохраняем ссылку в БД — получаем short_code
        short_code = database.create_short_link(url, user_id)

        # Затем асинхронно идём за заголовком страницы
        title = await self._fetch_title(url)
        database.update_link_title(short_code, title)

        return short_code

    async def _fetch_title(self, url: str) -> str:
        """
        Пытается получить <title> страницы.
        Если не вышло (таймаут, ошибка, нет тега) — возвращает URL как заголовок.
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "ShortURL Bot/1.0"}
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=2),
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        start = html.lower().find('<title>')
                        end = html.lower().find('</title>', start)
                        if start != -1 and end != -1:
                            return html[start + 7:end].strip()[:200]
        except Exception:
            pass
        return url


# Синглтон — импортируется один раз, используется везде
link_service = LinkService()
