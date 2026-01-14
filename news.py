import os
import aiohttp
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
        "Accept": "application/json",  # Просим JSON явно
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate", # <--- УБРАЛИ 'br' (Brotli)
        "Connection": "keep-alive"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, headers=headers) as response:
                
                if response.status != 200:
                    try:
                        text_response = await response.text()
                        if "Cloudflare" in text_response:
                            return "⚠️ Защита Cloudflare. Попробуй через 5 минут."
                    except:
                        pass
                    return f"⚠️ Ошибка сервера: {response.status}"

                data = await response.json()
                
                if not data.get("results"):
                    return f"📭 Новостей по {ticker} пока нет."

                news_list = data["results"][:5]
                text = f"📰 <b>Срочно по {ticker}:</b>\n\n"

                for news in news_list:
                    title = news["title"]
                    slug = news.get('slug', 'news')
                    news_id = news.get('id', '0')
                    # Ссылка сразу на источник (domain), если есть, или на cryptopanic
                    domain = news.get('domain', 'cryptopanic.com')
                    link = f"https://cryptopanic.com/news/{news_id}/{slug}"
                    
                    if len(title) > 120:
                        title = title[:120] + "..."

                    text += f"🔹 <a href='{link}'>{title}</a>\n(Источник: {domain})\n\n"
                
                return text

        except Exception as e:
            return f"⚠️ Ошибка кода: {str(e)}"