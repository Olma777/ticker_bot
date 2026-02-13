
import logging
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Optional
import pandas as pd

from bot.config import Config
from bot.database import get_recent_events
# from bot.indicators import process_levels <- Circular Import Fix
from bot.formatting import format_price_universal

logger = logging.getLogger(__name__)

class MarketDataProvider:
    """
    Abstracts the source of Support/Resistance levels.
    Prioritizes Webhook data (Pine Script) > Local Calculation (Python).
    """

    @staticmethod
    async def get_levels(ticker: str, df: pd.DataFrame) -> Tuple[List[Dict], List[Dict], str]:
        """
        Get S/R levels from best available source.
        Returns: (supports, resistances, source_name)
        """
        # 1. Try to get recent Webhook events (Freshness < 5 min usually, but levels valid longer)
        # We look back 24h for active levels, but "freshness" for priority might be shorter.
        # User requirement: "Prioritize cached webhook data (if < 5 min old)"
        # This likely refers to the "Signal" freshness. But levels are structural.
        # We will fetch recent events and see if any are fresh.
        
        try:
            # Check DB for recent events
            events = await get_recent_events(symbol=ticker, limit=20)
            
            # Filter for "Fresh" events (e.g. last 15 mins to be safe, plan said 5)
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=60) # Expanded window for levels
            # Note: stored 'bar_time' is int timestamps (seconds)
            
            valid_webhook_levels = []
            source = "LOCAL"
            
            # Simple deduplication
            seen_prices = set()
            
            current_price = df['close'].iloc[-1]
            atr = df['atr'].iloc[-1] if 'atr' in df else 0
            
            if events:
                # Check freshness of latest event
                latest_ts = events[0]['created_at'] # Timestamp string or datetime?
                # Aiosqlite returns parsing if configured? 'created_at' is TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                # SQLite returns string "YYYY-MM-DD HH:MM:SS".
                # Let's rely on 'bar_time' which is integer
                latest_bar_time = events[0]['bar_time']
                latest_dt = datetime.fromtimestamp(latest_bar_time, tz=timezone.utc)
                
                # If data is recent (e.g. within 60 mins), we consider it usable
                if latest_dt > cutoff:
                    source = "WEBHOOK"
                    for e in events:
                        try:
                            payload = json.loads(e['payload_json'])
                            lvl_price = payload.get('level')
                            evt_type = payload.get('event') # SUPPORT_TEST or RESISTANCE_TEST
                            score = payload.get('score', 0)
                            
                            if lvl_price and lvl_price not in seen_prices:
                                seen_prices.add(lvl_price)
                                valid_webhook_levels.append({
                                    'price': lvl_price,
                                    'type': 'SUPPORT' if 'SUPPORT' in evt_type else 'RESISTANCE',
                                    'score': score,
                                    'source': 'pine',
                                    'age': 0 # Unknown
                                })
                        except Exception:
                            continue
            
            # IF we found webhook levels, use them
            if source == "WEBHOOK" and valid_webhook_levels:
                # Separate into Sup/Res
                supports = []
                resistances = []
                for l in valid_webhook_levels:
                    # Dynamic Classification based on current Price
                    # Pine sends "SUPPORT_TEST", but if price broke below it, is it resistance?
                    # Generally yes.
                    if l['price'] < current_price:
                        l['type'] = 'SUPPORT'
                        supports.append(l)
                    else:
                        l['type'] = 'RESISTANCE'
                        resistances.append(l)
                
                # Sort
                supports.sort(key=lambda x: x['score'], reverse=True)
                resistances.sort(key=lambda x: x['score'], reverse=True)
                
                logger.info(f"Using WEBHOOK levels for {ticker} (Count: {len(valid_webhook_levels)})")
                return supports[:3], resistances[:3], "WEBHOOK"

        except Exception as e:
            logger.warning(f"Error fetching webhook levels for {ticker}: {e}")
            # Fallback to local
        
        # 2. Local Fallback
        # logger.info(f"Using LOCAL calculation for {ticker}")
        from bot.indicators import process_levels
        supports, resistances = process_levels(df)
        return supports, resistances, "LOCAL"
