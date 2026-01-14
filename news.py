import os
import aiohttp
import asyncio
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("CRYPTO_PANIC_KEY")

async def get_crypto_news(ticker):
    # Формируем ссылку на RSS-ленту (она работает стабильнее API)
    # Используем API ключ, если он есть, чтобы видеть больше новостей
    clean_key = API_KEY.strip().replace("'", "").replace('"', "") if API_KEY else ""
    
    url = f"https://cryptopanic.com/news/rss/?currency={ticker}&filter=important&public=true"
    if clean_key:
        url += f"&auth_token={clean_key}"

    # Простая маскировка, без фанатизма
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                
                if response.status != 200:
                    return f"⚠️ Сайт недоступен (код {response.status}). Попробуй позже."

                # Получаем текст ответа (XML)
                xml_data = await response.text()
                
                # Проверяем, не подсунули ли нам страницу защиты Cloudflare
                if "<!DOCTYPE html>" in xml_data or "Cloudflare" in xml_data:
                    return "🛡️ Защита Cloudflare блокирует новости. Попробуй через 5 минут."

                try:
                    # Разбираем XML (RSS формат) встроенными средствами
                    root = ET.fromstring(xml_data)
                    
                    # Ищем новости (элементы item)
                    items = root.findall(".//item")[:5]
                    
                    if not items:
                        return f"📭 Новостей по {ticker} сейчас нет."

                    text = f"📰 <b>Свежее по {ticker}:</b>\n\n"
                    
                    for item in items:
                        # Достаем заголовок и ссылку
                        title = item.find("title").text
                        link = item.find("link").text
                        
                        # Чистим заголовок от лишних символов
                        if title:
                            title = title.replace("<", "").replace(">", "")
                            if len(title) > 120: 
                                title = title[:120] + "..."
                        
                        text += f"🔹 <a href='{link}'>{title}</a>\n\n"
                        
                    return text

                except Exception as parse_error:
                    return f"⚠️ Ошибка чтения ленты: {parse_error}"

    except Exception as e:
        return f"⚠️ Ошибка соединения: {str(e)}"