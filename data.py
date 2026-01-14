import aiohttp

# Простой словарь для перевода Тикера в ID (для теста)
COIN_MAPPING = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "TON": "the-open-network",
    "DOGE": "dogecoin"
}

async def get_crypto_price(ticker):
    """
    Получает цену монеты с CoinGecko.
    """
    # 1. Приводим тикер к верхнему регистру (sol -> SOL)
    ticker = ticker.upper()
    
    # 2. Ищем ID монеты (если нет в списке — возвращаем None)
    coin_id = COIN_MAPPING.get(ticker)
    if not coin_id:
        return None, "Пока я знаю только BTC, ETH, SOL, TON, DOGE. Скоро выучу все!"

    # 3. Делаем запрос к API CoinGecko
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # Ответ приходит в виде {"bitcoin": {"usd": 42000}}
                    price = data.get(coin_id, {}).get("usd")
                    return price, None
                else:
                    return None, "Ошибка подключения к бирже."
        except Exception as e:
            return None, f"Ошибка: {str(e)}"