class InvalidSymbolError(ValueError):
    pass


class SymbolNormalizer:
    """
    Universal symbol normalizer for any ticker.
    Handles: APE, APEUSDT, APE/USDT, ape-usdt
    Output: Normalized formats for Binance (CCXT), Display, and Internal Logic.
    """
    DEFAULT_QUOTE = "USDT"
    ALLOWED_QUOTES = {"USDT", "USDC", "BUSD", "FDUSD", "DAI", "EUR"}

    @staticmethod
    def normalize(symbol: str) -> dict:
        """
        Normalize input symbol into standard components.
        Returns:
            {
                "base": "BTC",
                "quote": "USDT",
                "ccxt": "BTC/USDT",  # For CCXT calls
                "binance": "BTCUSDT", # For raw Binance API
                "display": "BTC/USDT" # For UI
            }
        """
        if not symbol:
            raise InvalidSymbolError("Empty symbol")

        s = symbol.upper().strip().replace("_", "").replace("-", "")
        
        # 1. Handle "BTC/USDT" format
        if "/" in s:
            parts = s.split("/")
            if len(parts) != 2:
                raise InvalidSymbolError(f"Invalid format: {symbol}")
            base, quote = parts[0], parts[1]
        
        # 2. Handle "BTC" or "BTCUSDT" format
        else:
            # Check if ends with known quote
            found_quote = None
            for q in SymbolNormalizer.ALLOWED_QUOTES:
                if s.endswith(q) and len(s) > len(q):
                    found_quote = q
                    break
            
            if found_quote:
                base = s[:-len(found_quote)]
                quote = found_quote
            else:
                # Assume it's just the base, append default quote
                base = s
                quote = SymbolNormalizer.DEFAULT_QUOTE
        
        # Validation
        if len(base) < 2 or len(base) > 10:
             raise InvalidSymbolError(f"Invalid base symbol length: {base}")
             
        return {
            "base": base,
            "quote": quote,
            "ccxt": f"{base}/{quote}",
            "binance": f"{base}{quote}",
            "display": f"{base}/{quote}"
        }

# Legacy Alias for gradual migration (if needed, but we will replace usages)
class SymbolValidator:
     @staticmethod
     def validate(symbol: str) -> str:
         # Adapter to match old behavior: returns "BTCUSDT" (or with suffix)
         try:
             norm = SymbolNormalizer.normalize(symbol)
             return norm['binance'] # Old validator returned "APEUSDT"
         except InvalidSymbolError as e:
             raise e

