import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import asyncio
from datetime import datetime

class TechnicalAnalyzer:
    def __init__(self):
        # Используем Binance Futures (USDT-M) как основной источник данных
        self.exchange = ccxt.binance({
            'options': {
                'defaultType': 'future'
            }
        })
        
    async def fetch_candles(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
        """
        Fetches OHLCV data from Binance Futures.
        """
        try:
            # Check if symbol has /USDT suffix, add if missing
            # Для фьючерсов Binance тикеры обычно выглядят как BTC/USDT:USDT или просто BTC/USDT в CCXT
            if '/' not in symbol:
                symbol = f"{symbol}/USDT"
                
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Ensure float types
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].astype(float)
            
            return df
        except Exception as e:
            print(f"Error fetching candles for {symbol}: {e}")
            return pd.DataFrame()
        finally:
            # We don't close self.exchange here because it might be reused. 
            # Ideally we should close it when the instance is destroyed or explicitly.
            pass

    async def close(self):
        await self.exchange.close()

    def calculate_levels(self, df: pd.DataFrame, timeframe: str = '1h') -> pd.DataFrame:
        """
        Ports logic from TrendLevelPRO.pine to calculate Support/Resistance levels.
        """
        if df.empty:
            return df

        # --- Settings (matching Pine Script defaults) ---
        # React Bars: 24
        # ATR Length: 14
        # kReact: 1.30
        # Merge Tolerance: 0.60
        REACT_BARS = 24
        ATR_LEN = 14
        K_REACT = 1.30
        MERGE_ATR = 0.60
        
        # Pivot Length logic based on timeframe (simplified mapping)
        # Pine: 5m->2, 15m->3, 30m->4, else->5
        pivot_l, pivot_r = 5, 5
        if timeframe == '5m':
            pivot_l, pivot_r = 2, 2
        elif timeframe == '15m':
            pivot_l, pivot_r = 3, 3
        elif timeframe == '30m':
            pivot_l, pivot_r = 4, 4
            
        # --- 1. Calculate ATR ---
        # Pine: ta.atr(atrLen) = rma(tr, atrLen)
        # Pandas TA or manual RMA. RMA is EMA of TR with alpha=1/length.
        high = df['high']
        low = df['low']
        close = df['close']
        
        # TR calculation
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR (RMA)
        # Pandas ewm adjust=False alpha=1/N is equivalent to RMA/Wilder's SMMA? 
        # Wilder's Smoothing (RMA) uses alpha = 1/N. 
        # Pandas ewm(span=N) uses alpha = 2/(N+1).
        # Pandas ewm(alpha=1/N, adjust=False) matches Pine RMA.
        atr = tr.ewm(alpha=1/ATR_LEN, adjust=False).mean()
        df['ATR'] = atr
        
        # --- 2. Pivot Detection & Logic ---
        # We need to iterate to simulate the "stateful" behavior of Pine Script arrays
        # (pending pivots, merging levels).
        # Vectorizing this is hard because merging depends on the current state of levels.
        
        # State variables
        levels = [] # List of dicts: {'price': float, 'atr': float, 'count': int, 'last_idx': int, 'is_res': bool}
        pending_pivots = [] # List of dicts: {'price', 'is_res', 'atr', 'eval_idx'}
        
        # Prepare data for iteration
        # We need numpy arrays for speed
        h_arr = high.values
        l_arr = low.values
        atr_arr = atr.values
        n = len(df)
        
        # Output columns (optional, for visualization/debug)
        # We will return the levels as a separate structure or attach to latest row?
        # The user asked to "add columns with calculations".
        # But "Levels" is a list of zones, not a time-series column (except for plotting boxes).
        # Let's add columns indicating *active* levels at each bar? 
        # Or just return the final list of levels?
        # "Возвращает DataFrame... и добавляет колонки с расчетами"
        # I will add columns for Pivot Points (raw) and maybe a column 'ActiveLevels' (json string?) or just print them.
        # Let's store the list of levels in the class or return it separately.
        # But the method signature is `calculate_levels(df)`. I'll assume it modifies DF and maybe returns it.
        # I will add 'PivotHigh', 'PivotLow' columns.
        
        pivot_highs = pd.Series(np.nan, index=df.index)
        pivot_lows = pd.Series(np.nan, index=df.index)
        
        # Helper to find pivot
        # Pivot High at index `i` means `i` is the peak.
        # It is confirmed at `i + pivot_r`.
        # We iterate through bars. `i` is current bar index.
        
        # To avoid re-calculating pivots inefficiently, we can pre-calculate pivots.
        # But we need to process them sequentially for the "Reaction" logic.
        
        for i in range(pivot_l + pivot_r, n):
            # 1. Check for Pivot at `i - pivot_r`
            curr_idx = i
            pivot_idx = i - pivot_r
            
            # Check Pivot High
            # range: [pivot_idx - pivot_l, pivot_idx + pivot_r]
            window_h = h_arr[pivot_idx - pivot_l : pivot_idx + pivot_r + 1]
            if len(window_h) > 0 and h_arr[pivot_idx] == np.max(window_h):
                # Found Pivot High
                pivot_highs.iloc[pivot_idx] = h_arr[pivot_idx]
                pending_pivots.append({
                    'price': h_arr[pivot_idx],
                    'is_res': True,
                    'atr': atr_arr[pivot_idx] if not np.isnan(atr_arr[pivot_idx]) else 0,
                    'eval_idx': pivot_idx + REACT_BARS # Evaluate reaction here
                })
                
            # Check Pivot Low
            window_l = l_arr[pivot_idx - pivot_l : pivot_idx + pivot_r + 1]
            if len(window_l) > 0 and l_arr[pivot_idx] == np.min(window_l):
                # Found Pivot Low
                pivot_lows.iloc[pivot_idx] = l_arr[pivot_idx]
                pending_pivots.append({
                    'price': l_arr[pivot_idx],
                    'is_res': False,
                    'atr': atr_arr[pivot_idx] if not np.isnan(atr_arr[pivot_idx]) else 0,
                    'eval_idx': pivot_idx + REACT_BARS
                })
            
            # 2. Evaluate Pending Pivots
            # We iterate backwards to allow removal
            for p_idx in range(len(pending_pivots) - 1, -1, -1):
                p = pending_pivots[p_idx]
                if curr_idx >= p['eval_idx']:
                    # Time to evaluate
                    # Reaction Window start: pivot index (which is eval_idx - reactBars)
                    # Actually logic in Pine:
                    # evalAt = bar_index - pivotR + reactBars  <-- This was when pushed.
                    # Wait, in Pine: 
                    # a_pivEval.push(bar_index - pivotR + reactBars)
                    # Check: if bar_index >= evalAt
                    # shift = bar_index - evalAt (how many bars passed since evaluation time? usually 0 if we catch it exactly)
                    # winLen = reactBars + 1
                    # range for Highest/Lowest: [current - winLen + 1 ... current] ?
                    # In Pine: ta.lowest(low, winLen). This looks at [current-winLen+1, current].
                    # Let's verify range.
                    # The pivot was at `eval_idx - REACT_BARS`.
                    # We are at `curr_idx` (which is >= eval_idx).
                    # We want to check if price moved away from pivot.
                    # For Resistance (High): Check Lowest Low since Pivot.
                    # Pine: `if (pPrice - ta.lowest(low, winLen)) >= (kReact * pAtr)`
                    # If we check exactly at `eval_idx`, then `winLen = reactBars + 1`.
                    # This covers exactly from Pivot Index to Current Index.
                    
                    p_price = p['price']
                    p_res = p['is_res']
                    p_atr = p['atr']
                    
                    # Look back window
                    # range [curr_idx - REACT_BARS, curr_idx + 1] (python slicing is exclusive at end)
                    # Actually we need `winLen` bars ending at `curr_idx`.
                    # start_idx = curr_idx - REACT_BARS
                    # But if `curr_idx` > `eval_idx` (lagging), we should still look at the window?
                    # Pine logic runs every bar. If we missed the exact bar, `shift >= 0`.
                    # `ta.lowest` always looks back from current bar.
                    # So if we are late, we look at recent bars. 
                    # Ideally we process exactly when `curr_idx == eval_idx`.
                    
                    if curr_idx == p['eval_idx']:
                        # Exact match
                        start_search = curr_idx - REACT_BARS
                        end_search = curr_idx + 1 # +1 for slicing
                        
                        is_valid = False
                        if p_res:
                            # Resistance: Price should drop
                            # Lowest Low in window
                            min_low = np.min(l_arr[start_search:end_search])
                            if (p_price - min_low) >= (K_REACT * p_atr):
                                is_valid = True
                        else:
                            # Support: Price should rise
                            # Highest High in window
                            max_high = np.max(h_arr[start_search:end_search])
                            if (max_high - p_price) >= (K_REACT * p_atr):
                                is_valid = True
                                
                        if is_valid:
                            # Add or Merge Level
                            self._add_or_merge(levels, p_price, p_res, p_atr, curr_idx, MERGE_ATR)
                    
                    # Remove processed pivot (whether valid or not, it's one-time check in Pine?)
                    # Pine: `a_pivPrice.remove(i)` happens unconditionally after check block.
                    pending_pivots.pop(p_idx)
        
        df['pivot_high'] = pivot_highs
        df['pivot_low'] = pivot_lows
        
        # Store levels in df metadata or return?
        # Let's format levels for output
        # We can create a DataFrame of levels
        self.levels = levels # Store for later retrieval if needed
        return df

    def _add_or_merge(self, levels, price, is_res, atr, curr_idx, merge_mult):
        tol = merge_mult * atr
        best_dist = 1e10
        found_idx = -1
        
        for i, lvl in enumerate(levels):
            if lvl['is_res'] == is_res:
                dist = abs(price - lvl['price'])
                if dist <= tol and dist < best_dist:
                    best_dist = dist
                    found_idx = i
        
        if found_idx != -1:
            # Merge
            lvl = levels[found_idx]
            old_p = lvl['price']
            old_t = lvl['count']
            
            new_t = old_t + 1
            new_p = (old_p * old_t + price) / new_t
            # Update ATR? Pine: `newA = (oldA * oldT + _atrAtPivot) / newT`
            old_a = lvl.get('atr', atr)
            new_a = (old_a * old_t + atr) / new_t
            
            lvl['price'] = new_p
            lvl['count'] = new_t
            lvl['atr'] = new_a
            lvl['last_idx'] = curr_idx
        else:
            # Add new
            levels.append({
                'price': price,
                'is_res': is_res,
                'atr': atr,
                'count': 1,
                'last_idx': curr_idx
            })
            
            # Garbage collection (Pine: maxStorage)
            if len(levels) > 1000:
                levels.pop(0)

    def get_active_levels(self):
        """
        Returns the currently active support/resistance levels.
        """
        if not hasattr(self, 'levels'):
            return []
        return self.levels

if __name__ == "__main__":
    async def main():
        analyzer = TechnicalAnalyzer()
        print("Fetching BTC/USDT candles...")
        df = await analyzer.fetch_candles('BTC/USDT', '1h', limit=500)
        
        if not df.empty:
            print(f"Fetched {len(df)} candles.")
            print("Calculating levels...")
            df = analyzer.calculate_levels(df, timeframe='1h')
            
            levels = analyzer.get_active_levels()
            print(f"\nFound {len(levels)} active levels.")
            
            # Sort by price
            levels.sort(key=lambda x: x['price'], reverse=True)
            
            print("\nTop 5 Closest Levels to Current Price:")
            current_price = df['close'].iloc[-1]
            print(f"Current Price: {current_price}")
            
            # Calculate distance to current price
            for lvl in levels:
                lvl['dist'] = abs(lvl['price'] - current_price)
            
            levels.sort(key=lambda x: x['dist'])
            
            for i, lvl in enumerate(levels[:5]):
                type_str = "RESISTANCE" if lvl['is_res'] else "SUPPORT"
                print(f"{i+1}. {type_str} @ {lvl['price']:.2f} (Touches: {lvl['count']}, ATR: {lvl['atr']:.2f})")
                
        await analyzer.close()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
