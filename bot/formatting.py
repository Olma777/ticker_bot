"""
Centralized formatting module for Market Lens Bot.
Ensures consistent price display across all assets (BTC, SHIB, etc.).
"""

def get_price_precision(price: float) -> int:
    """
    Determine price precision based on magnitude.
    Universal for any ticker.
    """
    if price is None or price == 0:
        return 2
        
    abs_price = abs(price)
    
    if abs_price >= 10000:      # BTC, YFI
        return 0
    elif abs_price >= 1000:     # ETH ($3000) -> 2 decimals
        return 2
    elif abs_price >= 1:        # $1 - $1000 -> 3 decimals (User Request)
        return 3
    elif abs_price >= 0.1:      # HBAR, VET -> $0.1234
        return 4
    elif abs_price >= 0.01:     # APE, CRO -> $0.0543
        return 4
    elif abs_price >= 0.001:    # PEPE (early) -> $0.001234
        return 6
    elif abs_price >= 0.000001: # SHIB -> $0.00001234
        return 8
    else:                       # Micro-caps
        return 10

def format_price_universal(price: float) -> str:
    """
    Format price string with adaptive precision.
    """
    if price is None or price == 0:
        return "$0"
    
    precision = get_price_precision(price)
    
    # Special case: Sub-$1 assets should always have min 4 decimals for accuracy
    if abs(price) < 1 and precision < 4:
        precision = 4
        
    return f"${price:,.{precision}f}"
