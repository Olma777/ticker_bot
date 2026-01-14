import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("CRYPTO_PANIC_KEY")

async def get_crypto_news(ticker):
    if not API_KEY:
        return "⚠️ Ошибка: Не найден ключ API новостей."

    # Чистим ключ
    clean_key = API_KEY.strip().replace("'", "").replace('"', "")
    
    # Ссылка API
    url = "https://cryptopanic.com/api/v1/posts/"

    # Параметры
    params = {
        "auth_token": clean_key,
        "currencies": ticker,
        "kind": "news",
        "filter": "important",
        "public": "true"
    }

    # МОЩНАЯ МАСКИРОВКА ПОД БРАУЗЕР
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, headers=headers) as response:
                
                # Если сервер всё равно ругается
                if response.status != 200:
                    # Пытаемся прочитать, что он ответил (первые 100 символов)
                    try:
                        text_response = await response.text()
                        if "Cloudflare" in text_response:
                            return "⚠️ Защита Cloudflare блокирует запрос. Попробуй позже."
                    except:
                        pass
                    return f"⚠️ Ошибка сервера: {response.status}"

                data = await response.json()
                
                if not data.get("results"):
                    return f"📭 Новостей по {ticker} пока нет (или тикер указан неверно)."

                news_list = data["results"][:5]
                text = f"📰 <b>Срочно по {ticker}:</b>\n\n"

                for news in news_list:
                    title = news["title"]
                    # Формируем красивую ссылку
                    slug = news.get('slug', 'news')
                    news_id = news.get('id', '0')
                    link = f"https://cryptopanic.com/news/{news_id}/{slug}"
                    
                    # Обрезаем слишком длинные заголовки
                    if len(title) > 120:
                        title = title[:120] + "..."

                    text += f"🔥 <a href='{link}'>{title}</a>\n\n"
                
                return text

        except Exception as e:
            return f"⚠️ Ошибка кода: {str(e)}"