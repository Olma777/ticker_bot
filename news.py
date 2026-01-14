import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("CRYPTO_PANIC_KEY")

async def get_crypto_news(ticker):
    """
    Получает свежие новости по тикеру через CryptoPanic API.
    """
    if not API_KEY:
        return "⚠️ Ошибка: Не найден ключ API новостей."

    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={API_KEY}&currencies={ticker}&kind=news&filter=important"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                data = await response.json()
                
                if not data.get("results"):
                    return f"📭 Свежих важных новостей по {ticker} не найдено."

                # Берем топ-5 новостей
                news_list = data["results"][:5]
                text = f"📰 <b>Главные новости по {ticker}:</b>\n\n"

                for news in news_list:
                    title = news["title"]
                    # Ссылка на саму новость (иногда она в source)
                    link = f"https://cryptopanic.com/news/{news['id']}/click/"
                    
                    # Формируем строку
                    text += f"🔹 <a href='{link}'>{title}</a>\n\n"
                
                return text

        except Exception as e:
            return f"⚠️ Ошибка получения новостей: {str(e)}"