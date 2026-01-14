import os
import aiohttp
import asyncio
from dotenv import load_dotenv

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

    # ЧИСТЫЕ ЗАГОЛОВКИ (Без лишнего мусора, который вызывает 502)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json", 
        "Referer": "https://cryptopanic.com/",
        "Origin": "https://cryptopanic.com"
    }

    timeout = aiohttp.ClientTimeout(total=10)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Мы не указываем Accept-Encoding вручную! aiohttp сама подставит gzip/brotli
            async with session.get(url, params=params, headers=headers) as response:
                
                if response.status != 200:
                    return f"⚠️ Ошибка доступа к сайту: {response.status}"

                data = await response.json()
                
                if not data.get("results"):
                    return f"📭 Новостей по {ticker} пока нет."

                news_list = data["results"][:5]
                text = f"📰 <b>Срочно по {ticker}:</b>\n\n"

                for news in news_list:
                    title = news["title"]
                    # Очистка заголовка от спецсимволов HTML
                    title = title.replace("<", "").replace(">", "")
                    
                    slug = news.get('slug', 'news')
                    news_id = news.get('id', '0')
                    domain = news.get('domain', 'cryptopanic.com')
                    
                    link = f"https://cryptopanic.com/news/{news_id}/{slug}"
                    
                    if len(title) > 120:
                        title = title[:120] + "..."

                    text += f"🔹 <a href='{link}'>{title}</a>\nSource: {domain}\n\n"
                
                return text

    except asyncio.TimeoutError:
        return "⚠️ Сайт новостей долго не отвечает."
    except Exception as e:
        return f"⚠️ Внутренняя ошибка: {str(e)}"