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

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json", # Строго просим JSON
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br", # Мы установили brotli, так что можно!
        "Connection": "keep-alive"
    }

    timeout = aiohttp.ClientTimeout(total=10)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params, headers=headers) as response:
                
                # 1. Если статус не 200 (ОК)
                if response.status != 200:
                    return f"⚠️ Ошибка доступа к сайту: {response.status}"

                # 2. Пытаемся прочитать JSON
                try:
                    data = await response.json()
                except:
                    # Если сайт прислал HTML вместо JSON - это защита Cloudflare
                    return "⚠️ Сайт включил защиту (Cloudflare). Новости временно недоступны."
                
                # 3. Если в JSON пусто
                if not data.get("results"):
                    return f"📭 Новостей по {ticker} пока нет."

                news_list = data["results"][:5]
                text = f"📰 <b>Срочно по {ticker}:</b>\n\n"

                for news in news_list:
                    title = news["title"]
                    # Чистим заголовок от угловых скобок, чтобы не ломать HTML телеграма
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