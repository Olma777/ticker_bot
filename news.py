import os
import aiohttp
import asyncio
from dotenv import load_dotenv

# Пытаемся проверить, установился ли Brotli
try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False

load_dotenv()
API_KEY = os.getenv("CRYPTO_PANIC_KEY")

async def get_crypto_news(ticker):
    if not API_KEY:
        return "⚠️ Ошибка: Не найден ключ API новостей."

    clean_key = API_KEY.strip().replace("'", "").replace('"', "")
    url = "https://cryptopanic.com/api/v1/posts/"
    
    params = {
        "auth_token": clean_key,
        "currencies": ticker,
        "kind": "news",
        "filter": "important",
        "public": "true"
    }

    # Формируем список форматов, которые мы понимаем
    # Если Brotli установлен - просим его. Если нет - только gzip.
    encoding = "gzip, deflate, br" if HAS_BROTLI else "gzip, deflate"

    # ТЕ САМЫЕ ЗАГОЛОВКИ, КОТОРЫЕ РАБОТАЛИ (Chrome)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": encoding, 
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }

    timeout = aiohttp.ClientTimeout(total=10)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params, headers=headers) as response:
                
                # Если сайт снова блокирует (404/502/403)
                if response.status != 200:
                    return f"⚠️ Ошибка доступа к сайту: {response.status} (Попробуй другой тикер)"

                try:
                    data = await response.json()
                except Exception as e:
                    # Если пришел HTML или мусор
                    return f"⚠️ Ошибка чтения данных. Brotli установлен: {HAS_BROTLI}. Ошибка: {e}"
                
                if not data.get("results"):
                    return f"📭 Новостей по {ticker} пока нет."

                news_list = data["results"][:5]
                text = f"📰 <b>Новости {ticker}:</b>\n\n"

                for news in news_list:
                    title = news["title"].replace("<", "").replace(">", "")
                    slug = news.get('slug', 'news')
                    news_id = news.get('id', '0')
                    domain = news.get('domain', 'cryptopanic.com')
                    link = f"https://cryptopanic.com/news/{news_id}/{slug}"
                    
                    if len(title) > 120:
                        title = title[:120] + "..."

                    text += f"🔹 <a href='{link}'>{title}</a>\nSource: {domain}\n\n"
                
                return text

    except asyncio.TimeoutError:
        return "⚠️ Сайт долго не отвечает."
    except Exception as e:
        return f"⚠️ Критическая ошибка: {str(e)}"