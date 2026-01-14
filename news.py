import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("CRYPTO_PANIC_KEY")

async def get_crypto_news(ticker):
    if not API_KEY:
        return "⚠️ Ошибка: Не найден ключ API новостей."

    # Очищаем ключ от мусора
    clean_key = API_KEY.strip().replace("'", "").replace('"', "")
    
    # Базовая ссылка (без параметров)
    url = "https://cryptopanic.com/api/v1/posts/"

    # Параметры запроса (библиотека сама соберет их в правильную ссылку)
    params = {
        "auth_token": clean_key,
        "currencies": ticker,
        "kind": "news",
        "filter": "important",
        "public": "true"
    }

    # Маскировка под браузер
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession() as session:
        try:
            # Передаем params отдельно!
            async with session.get(url, params=params, headers=headers) as response:
                
                # Если 404 или другая ошибка - пробуем понять почему
                if response.status != 200:
                    # Попробуем прочитать ответ сервера, вдруг там подсказка
                    try:
                        error_text = await response.text()
                        print(f"DEBUG Error: {error_text}") # Это упадет в логи Railway
                    except:
                        pass
                    return f"⚠️ Ошибка API: {response.status} (Проверь ключ или тикер)"

                data = await response.json()
                
                if not data.get("results"):
                    return f"📭 Свежих важных новостей по {ticker} не найдено."

                news_list = data["results"][:5]
                text = f"📰 <b>Главные новости по {ticker}:</b>\n\n"

                for news in news_list:
                    title = news["title"]
                    # Безопасное получение ссылки
                    slug = news.get('slug', 'news')
                    news_id = news.get('id', '0')
                    # Ссылка на новость
                    link = f"https://cryptopanic.com/news/{news_id}/{slug}"
                    
                    # Иногда title слишком длинный, обрезаем
                    if len(title) > 100:
                        title = title[:100] + "..."

                    text += f"🔹 <a href='{link}'>{title}</a>\n\n"
                
                return text

        except Exception as e:
            return f"⚠️ Ошибка кода: {str(e)}"