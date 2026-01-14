import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("CRYPTO_PANIC_KEY")

async def get_crypto_news(ticker):
    if not API_KEY:
        return "⚠️ Ошибка: Не найден ключ API новостей."

    # Чистим ключ от возможных пробелов и 'кавычек'
    clean_key = API_KEY.strip().replace("'", "").replace('"', "")
    
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={clean_key}&currencies={ticker}&kind=news&filter=important"

    # Притворяемся обычным браузером (Chrome)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession() as session:
        try:
            # Передаем headers, чтобы нас не блокировали
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return f"⚠️ Ошибка API: {response.status}"

                data = await response.json()
                
                if not data.get("results"):
                    return f"📭 Свежих важных новостей по {ticker} не найдено."

                news_list = data["results"][:5]
                text = f"📰 <b>Главные новости по {ticker}:</b>\n\n"

                for news in news_list:
                    title = news["title"]
                    # Формируем короткую ссылку
                    slug = news.get('slug', 'news')
                    news_id = news.get('id')
                    link = f"https://cryptopanic.com/news/{news_id}/{slug}"
                    
                    text += f"🔹 <a href='{link}'>{title}</a>\n\n"
                
                return text

        except Exception as e:
            return f"⚠️ Ошибка получения новостей: {str(e)}"