
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
    async def get_levels(ticker: str, df: pd.DataFrame) -> Tuple[List[Dict], List[Dict], str, Optional[Dict]]:
        """
        Get S/R levels and Regime from best available source.
        Returns: (supports, resistances, source_name, regime_data)
        """
        # 1. Try to get recent Webhook events
        try:
            events = await get_recent_events(symbol=ticker, limit=20)
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
            
            valid_webhook_levels = {
                'supports': [],
                'resistances': []
            }
            webhook_regime = None
            source = "LOCAL"
            
            if events:
                latest_ts = events[0]['bar_time']
                latest_dt = datetime.fromtimestamp(latest_ts, tz=timezone.utc)
                
                if latest_dt > cutoff:
                    # We have fresh data
                    latest_payload = json.loads(events[0]['payload_json'])
                    
                    # A. Try V3.7 "levels" array (Source of Truth)
                    if 'levels' in latest_payload:
                        source = "WEBHOOK_V3.7"
                        raw_levels = latest_payload['levels']
                        webhook_regime = latest_payload.get('regime')
                        
                        # Parse Resistances
                        for r in raw_levels.get('resistances', []):
                            valid_webhook_levels['resistances'].append({
                                'price': r['price'],
                                'type': 'RESISTANCE',
                                'score': r.get('score', 0),
                                'source': 'pine_v3.7',
                                'age': 0
                            })
                            
                        # Parse Supports
                        for s in raw_levels.get('supports', []):
                            valid_webhook_levels['supports'].append({
                                'price': s['price'],
                                'type': 'SUPPORT',
                                'score': s.get('score', 0),
                                'source': 'pine_v3.7',
                                'age': 0
                            })
                            
                    # B. Fallback to Legacy (Single Level)
                    else:
                        source = "WEBHOOK_LEGACY"
                        seen_prices = set()
                        # Aggregate levels from multiple recent events
                        for e in events:
                            try:
                                p = json.loads(e['payload_json'])
                                if 'levels' in p: continue # Skip partial v3.7

                                lvl_price = p.get('level')
                                evt_type = p.get('event')
                                score = p.get('score', 0)
                                
                                if lvl_price and lvl_price not in seen_prices:
                                    seen_prices.add(lvl_price)
                                    l_type = 'SUPPORT' if 'SUPPORT' in evt_type else 'RESISTANCE'
                                    
                                    # Anti-Hallucination: Verify type against current price? 
                                    # Legacy events might be old. We'll trust the event type for now.
                                    
                                    level_obj = {
                                        'price': lvl_price,
                                        'type': l_type,
                                        'score': score,
                                        'source': 'pine_legacy',
                                        'age': 0
                                    }
                                    
                                    if l_type == 'SUPPORT':
                                        valid_webhook_levels['supports'].append(level_obj)
                                    else:
                                        valid_webhook_levels['resistances'].append(level_obj)
                                        
                            except Exception:
                                continue

            # Return Webhook Data if valid
            if source.startswith("WEBHOOK") and (valid_webhook_levels['supports'] or valid_webhook_levels['resistances']):
                logger.info(f"Using {source} data for {ticker}")
                return (
                    valid_webhook_levels['supports'], 
                    valid_webhook_levels['resistances'], 
                    source,
                    webhook_regime
                )

        except Exception as e:
            logger.warning(f"Error fetching webhook levels for {ticker}: {e}")

        # 2. Local Fallback
        from bot.indicators import process_levels
        supports, resistances = process_levels(df)
        return supports, resistances, "LOCAL", None
