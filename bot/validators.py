class InvalidSymbolError(ValueError):
    pass


class SymbolValidator:
    DEFAULT_SUFFIX = "USDT"
    ALLOWED_SUFFIXES = {"USDT", "USDC", "BUSD", "FDUSD"}

    @staticmethod
    def auto_complete(symbol: str) -> str:
        """Добавляет суффикс по умолчанию, если его нет"""
        sym = symbol.upper().strip()
        if any(sym.endswith(s) for s in SymbolValidator.ALLOWED_SUFFIXES):
            return sym
        return f"{sym}{SymbolValidator.DEFAULT_SUFFIX}"

    @staticmethod
    def validate(symbol: str) -> str:
        sym = SymbolValidator.auto_complete(symbol)
        if len(sym) > 12 or not sym.replace("/", "").isalnum():
            raise InvalidSymbolError(f"Invalid format: {symbol}")
        if not any(sym.endswith(s) for s in SymbolValidator.ALLOWED_SUFFIXES):
            raise InvalidSymbolError(f"Unsupported pair: {symbol}")
        return sym
