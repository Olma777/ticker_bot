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

    # ВОЗВРАЩАЕМ МАСКИРОВКУ, КОТОРАЯ РАБОТАЛА
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Важно: просим как браузер, а не как робот (application/json)
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        # САМОЕ ГЛАВНОЕ: Убрали 'br', оставили только gzip
        "Accept-Encoding": "gzip, deflate", 
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
                
                # Если ошибка - читаем текст, чтобы понять причину!
                if response.status != 200:
                    try:
                        error_text = await response.text()
                        # Обрезаем, чтобы не засорять чат
                        debug_info = error_text[:200] 
                        return f"⚠️ Ошибка сервера: {response.status}\n📝 Ответ: {debug_info}"
                    except:
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
                    # Пробуем достать домен источника
                    domain = news.get('domain', 'cryptopanic.com')
                    
                    link = f"https://cryptopanic.com/news/{news_id}/{slug}"
                    
                    if len(title) > 120:
                        title = title[:120] + "..."

                    text += f"🔹 <a href='{link}'>{title}</a>\nSource: {domain}\n\n"
                
                return text

        except Exception as e:
            return f"⚠️ Ошибка кода: {str(e)}"