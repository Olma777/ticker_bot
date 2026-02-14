# Market Lens Bot — Technical Whitepaper v1.0

**Version:** Alpha 3 • **Date:** February 2026 • **Classification:** Confidential

---

## 1. Executive Summary

Market Lens is an **automated technical analysis system** for cryptocurrency perpetual futures.
The system receives real-time price level alerts from TradingView, enriches them with on-chain and order book data, applies a multi-layer safety pipeline, and generates actionable trade setups (Entry, Stop-Loss, Take-Profit) with strict risk management.

**Key characteristics:**
- Deterministic signal pipeline — identical inputs always produce identical outputs
- 5-layer Kevlar safety system — blocks dangerous entries before they happen
- ATR-based order math — all levels calculated from market volatility, not fixed offsets
- 1% risk per trade — hardcoded capital preservation

---

## 2. System Architecture

```
                        ┌──────────────────┐
                        │   TradingView    │
                        │  Pine Script v3.7│
                        └────────┬─────────┘
                                 │ Webhook (HTTPS + HMAC)
                        ┌────────▼─────────┐
                        │   FastAPI Server  │
                        │   (server.py)     │
                        └────────┬─────────┘
                                 │ Background Task
              ┌──────────────────▼──────────────────┐
              │         Decision Engine              │
              │       (decision_engine.py)           │
              └──┬──────────┬──────────┬──────────┬──┘
                 │          │          │          │
          ┌──────▼──┐  ┌───▼───┐  ┌───▼───┐  ┌──▼───────┐
          │Indicators│  │P-Score│  │ Kevlar│  │Order Calc│
          │(.py)     │  │(.py)  │  │(.py)  │  │(.py)     │
          └──────────┘  └───────┘  └───────┘  └──────────┘
                 │
          ┌──────▼──────┐
          │ AI Analyst   │
          │(ai_analyst.py│
          └──────┬──────┘
                 │
          ┌──────▼──────┐
          │  Telegram    │
          │  Notifier    │
          └─────────────┘
```

### 2.1 Data Flow

| Step | Module | Function | Description |
|------|--------|----------|-------------|
| 1 | `server.py` | `webhook_listener` | Receives TradingView alert, validates HMAC signature |
| 2 | `server.py` | `generate_event_id` | SHA-256 deduplication prevents double processing |
| 3 | `decision_engine.py` | `process_signal` | Orchestrates analysis pipeline |
| 4 | `indicators.py` | `run_full_analysis` | Fetches OHLCV, calculates S/R levels, ATR, RSI, VWAP |
| 5 | `pscore.py` | `calculate_score` | Computes probability score (0-100) |
| 6 | `kevlar.py` | `check_safety_v2` | 5-layer safety filter |
| 7 | `ai_analyst.py` | `get_ai_sniper_analysis` | Direction decision + order generation |
| 8 | `order_calc.py` | `build_order_plan` | Deterministic Entry/SL/TP calculation |
| 9 | `notifier.py` | `send_card` | Formats and sends to Telegram |

### 2.2 Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Runtime | Python 3.11 | Core language |
| Web Server | FastAPI + Uvicorn | Webhook receiver |
| Hosting | Railway | Cloud deployment |
| Data Source | CCXT (Binance, Bybit, OKX, +3) | Price aggregation |
| Alerts | TradingView Pine Script v3.7 | Level detection |
| Notifications | Telegram Bot API | Signal delivery |
| Database | SQLite (aiosqlite) | Event deduplication |

---

## 3. Signal Generation Pipeline

### 3.1 Pine Script v3.7 — Level Detection (TradingView)

The TradingView indicator runs on 30-minute charts and detects **Support** and **Resistance** levels using the following algorithm:

```
Parameters (Locked):
  React Bars    = 24
  K_React       = 1.3
  Merge ATR     = 0.6
  Wt (Touches)  = 1.0
  Wa (Age Decay)= 0.35
  T_min         = 5
  ATR Length     = 14
```

**Level Score formula:**
```
Score = Wt × Touches − Wa × Age
```

Where:
- **Touches** = number of times price tested the level
- **Age** = bars since level was first detected
- **Score ≥ 3.0** → Strong level (🟢)
- **Score ≥ 1.0** → Medium level (🟡)
- **Score < 1.0** → Weak level

When price tests a level, TradingView sends a webhook to the server.

### 3.2 Local Level Calculation (Fallback)

When TradingView data is unavailable (e.g. manual `/sniper` command), the system calculates levels locally from OHLCV data using the same algorithm:

1. **Pivot detection** — Identifies swing highs/lows from 30m candles
2. **Level merging** — Clusters nearby pivots within `0.6 × ATR` distance
3. **Scoring** — Applies `Score = Wt × Touches − Wa × Age`
4. **Filtering** — Removes levels with `Score < -100` (ghost levels)

> **Note:** Local levels have negative scores by design because they lack the touch-count enrichment from real-time TradingView data. The system uses them as positional references, not quality indicators.

---

## 4. Probability Score (P-Score)

P-Score is a **0-100 composite metric** estimating the probability of a successful trade.

### 4.1 Calculation

| Factor | Condition | Impact |
|--------|-----------|--------|
| **Base** | — | 50 |
| **Level Strength** | Score ≥ 1.0 (Strong) | +15 |
| | Score < 0 (Weak) | −20 |
| | Score 0–1 (Medium) | 0 |
| **BTC Regime** | EXPANSION (trending up) | +10 |
| | COMPRESSION (high z-score) | −10 |
| | NEUTRAL | 0 |
| **RSI Context** | RSI < 35 at Support (oversold) | +5 |
| | RSI > 65 at Resistance (overbought) | +5 |
| **Sentiment** | High Open Interest (HOT) | +10 |
| | Low Open Interest (COLD) | −5 |

**Hard gate:** `P-Score < 35` → signal blocked, no trade generated.

### 4.2 BTC Regime Detection

The system monitors BTC's 30-period Rate of Change to determine the global regime:

```python
z_score = (ROC - mean(ROC, 180)) / std(ROC, 180)

if z_score > 1.25  → COMPRESSION (RISKY)
if z_score < -1.25 → EXPANSION (SAFE)
else               → NEUTRAL (SAFE)
```

When regime is **RISKY**, the minimum P-Score threshold is raised from 35 to 40 (soft gate, not hard block).

---

## 5. Kevlar Safety System

Kevlar is a **5-layer cascading filter** that blocks dangerous entries. Each filter runs sequentially; any failure immediately blocks the trade.

### 5.1 Filter Chain

| Filter | Name | Logic | Purpose |
|--------|------|-------|---------|
| **K0** | Data Integrity | `ATR = 0 ∨ Price = 0 ∨ Candles < 5` | Prevents trading on bad data |
| **K1** | Level Distance | `|Price − Level| / Price > 15%` | Blocks stale/irrelevant levels |
| **K2** | Momentum (Falling Knife) | `Close[0]/Close[5] − 1 < −5%` at Support | Prevents buying into crashes |
| **K2B** | Short Squeeze | `Close[0]/Close[5] − 1 > +5%` at Resistance | Prevents shorting into squeezes |
| **K3** | RSI Panic/FOMO | `RSI < 20 ∧ P-Score < 50` or `RSI > 80 ∧ P-Score < 50` | Blocks emotional entries |
| **K4** | Sentiment Trap | LONG with `Funding > 0.03%` and `Price < VWAP` | Blocks contrarian traps |

### 5.2 Anti-Trap Mechanism (STEP 4B)

An additional filter after direction selection:

- If **LONG** and price is within **0.3%** of a strong resistance (Score ≥ 3.0) → BLOCK
- If **SHORT** and price is within **0.3%** of a strong support (Score ≥ 3.0) → BLOCK

This prevents entries that are technically valid but practically about to reverse.

---

## 6. Order Calculation Module

### 6.1 Deterministic Math

All order parameters are calculated from a single function `build_order_plan()` with zero randomness:

```
Input:  Side, Level, ATR, Capital, Risk%
Output: Entry, SL, TP1, TP2, TP3, Size, RRR
```

### 6.2 Formulas

| Parameter | LONG | SHORT |
|-----------|------|-------|
| **Entry** | Level (limit order) | Level (limit order) |
| **Stop-Loss** | Entry − 1.0 × ATR | Entry + 1.0 × ATR |
| **TP1** | Entry + 0.75 × ATR | Entry − 0.75 × ATR |
| **TP2** | Entry + 1.25 × ATR | Entry − 1.25 × ATR |
| **TP3** | Entry + 2.0 × ATR | Entry − 2.0 × ATR |

### 6.3 Position Sizing

```
Risk Amount = Capital × (Risk% / 100)
             = $1,000 × 0.01 = $10

Stop Distance = |Entry − SL| = 1.0 × ATR

Size = Risk / Stop Distance
```

### 6.4 Sanity Gates

| Check | Condition | Result |
|-------|-----------|--------|
| Zero stop distance | `|Entry − SL| = 0` | Trade blocked |
| Zero position size | `Size ≤ 0` | Trade blocked |
| Low RRR | `RRR(TP2) < 1.10` | Trade blocked |
| High funding cost | `Funding > 0.5%` and `RRR < 1.30` | Trade blocked |

---

## 7. AI Analysis Layer

### 7.1 Smart Money Phase Detection

The system classifies market phase based on price action relative to VWAP and RSI:

| Phase | Conditions | Meaning |
|-------|-----------|---------|
| **ACCUMULATION** 🟢 | Price < VWAP, RSI < 40, negative funding | Large players buying quietly |
| **DISTRIBUTION** 🔴 | Price > VWAP, RSI > 60, positive funding | Large players selling to retail |
| **NEUTRAL** ⚪ | Mixed signals | No clear institutional bias |

### 7.2 Liquidity Analysis

The system estimates **stop-loss clusters** based on recent swing points and ATR:

- **Long stops** are projected below the nearest support
- **Short stops** are projected above the nearest resistance
- **Hunt probability** is assessed based on distance from current price

### 7.3 Market Maker Behavior Analysis

Detects potential spoofing and manipulation patterns through:
- Price vs VWAP divergence
- RSI vs Price divergence
- Funding rate anomalies

---

## 8. Security Architecture

### 8.1 Webhook Authentication

All incoming webhooks are validated with **HMAC comparison** in constant time:

```python
hmac.compare_digest(x_ml_secret, Config.WEBHOOK_SECRET)
```

Failed authentication returns `HTTP 401` with no data leakage.

### 8.2 Event Deduplication

Each event generates a **deterministic SHA-256 ID**:

```
ID = SHA256(SYMBOL | TF | BAR_TIME | EVENT | LEVEL | ZONE_HALF)
```

Duplicate events are ignored (database uniqueness constraint).

### 8.3 Input Validation

- Pydantic models enforce strict typing on all webhook fields
- `bar_time` must be a Unix timestamp post-2020
- Symbol normalization handles all input formats (APE, APEUSDT, APE/USDT)
- All numeric inputs validated for NaN, inf, and zero division

### 8.4 Credential Management

| Credential | Storage | Purpose |
|-----------|---------|---------|
| `WEBHOOK_SECRET` | Environment variable | Webhook authentication |
| `TELEGRAM_TOKEN` | Environment variable | Bot communication |
| `OPENROUTER_API_KEY` | Environment variable | AI analysis (optional) |

Server **fails to start** if `WEBHOOK_SECRET` is missing or set to default.

---

## 9. Risk Management Summary

### 9.1 Capital Protection Layers

```
Layer 1: P-Score Gate       — Blocks weak setups (< 35/100)
Layer 2: BTC Regime         — Raises threshold in volatile markets
Layer 3: Kevlar (5 filters) — Blocks dangerous market conditions
Layer 4: Anti-Trap          — Blocks entries near opposing levels
Layer 5: Entry Validation   — Validates level proximity and direction
Layer 6: Order Math         — Enforces minimum RRR (1.10x)
Layer 7: Funding Check      — Blocks trades with expensive holding costs
```

### 9.2 Worst-Case Scenario

| Parameter | Value |
|-----------|-------|
| Max risk per trade | 1% of capital |
| Max drawdown per trade | $10 on $1,000 account |
| Entry type | Limit only (no market orders) |
| Stop-loss | Always present, ATR-based |
| Max simultaneous trades | 1 per ticker (dedup) |

---

## 10. Supported Assets

The system supports **any USDT-perpetual contract** available on supported exchanges.

### Pre-configured Sectors

| Sector | Assets |
|--------|--------|
| **AI** | FET, RENDER, WLD, ARKM, GRT, NEAR |
| **RWA** | ONDO, PENDLE, OM, TRU, DUSK |
| **L2** | OP, ARB, POL, METIS, MANTA, STRK |
| **DePIN** | FIL, AR, IOTX, THETA, HBAR |

### Supported Exchanges (Price Aggregation)

| Priority | Exchange | Type |
|----------|----------|------|
| 1 | Binance | Futures |
| 2 | Bybit | Linear |
| 3 | OKX | Swap |
| 4 | MEXC | Swap |
| 5 | BingX | Swap |
| 6 | Gate.io | Futures |

The system queries exchanges in priority order and uses the first successful response. This provides **redundancy** — if Binance is down, the system continues via Bybit.

---

## 11. Configuration Parameters (Locked)

All parameters are synchronized with Pine Script v3.7 and frozen in `config.py`:

| Parameter | Value | Source |
|-----------|-------|--------|
| Timeframe | 30m | Pine v3.7 |
| ATR Length | 14 | Pine v3.7 |
| React Bars | 24 | Pine v3.7 |
| K_React | 1.3 | Pine v3.7 |
| Merge ATR | 0.6 | Pine v3.7 |
| Wt (Touch Weight) | 1.0 | Pine v3.7 |
| Wa (Age Decay) | 0.35 | Pine v3.7 |
| Z-Score Window | 180 | Pine v3.7 |
| Z-Score Threshold | 1.25 | Pine v3.7 |
| P-Score Threshold | 35 | Calibrated |
| Funding Threshold | 0.03% | Calibrated |
| SL Multiplier | 1.0 × ATR | User Spec |
| TP1 Multiplier | 0.75 × ATR | User Spec |
| TP2 Multiplier | 1.25 × ATR | User Spec |
| TP3 Multiplier | 2.0 × ATR | User Spec |
| Min RRR | 1.10 | User Spec |
| Default Capital | $1,000 | Config |
| Risk per Trade | 1% | Config |

---

## 12. Glossary

| Term | Definition |
|------|-----------|
| **ATR** | Average True Range — measure of market volatility over 14 periods |
| **VWAP** | Volume-Weighted Average Price — institutional fair value |
| **RSI** | Relative Strength Index (0-100). <30 = oversold, >70 = overbought |
| **P-Score** | Probability Score (0-100) — composite signal strength metric |
| **Kevlar** | Multi-layer safety filter system named for durability |
| **RRR** | Risk-to-Reward Ratio — potential profit / potential loss |
| **Funding Rate** | 8-hourly fee for holding perpetual futures positions |
| **S/R Level** | Support or Resistance — price zone where price likely reverses |
| **Score** | Level quality metric: positive = strong (confirmed), negative = weak |
| **HMAC** | Hash-based Message Authentication Code — webhook security |
| **Pine Script** | TradingView's programming language for indicators |

---

*Document generated: February 14, 2026*
*System version: Alpha 3 (commit 7ec8047)*
*Contact: [Project Maintainer]*
