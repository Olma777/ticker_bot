class InvalidSymbolError(ValueError):
    pass


class SymbolValidator:
    ALLOWED_SUFFIXES = {"USDT", "USDC", "BUSD", "FDUSD"}

    @staticmethod
    def validate(symbol: str) -> str:
        sym = symbol.upper().strip().replace(" ", "")
        if len(sym) > 12 or not sym.replace("/", "").isalnum():
            raise InvalidSymbolError(f"Invalid format: {symbol}")
        if not any(sym.endswith(s) for s in SymbolValidator.ALLOWED_SUFFIXES):
            raise InvalidSymbolError(f"Unsupported pair: {symbol}")
        return sym
