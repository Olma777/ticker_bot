# AUDIT_PACKAGE.md
## Market Lens v3.0 — External Logic & Code Audit (ticker_bot-1 structure)

---

## 1. PURPOSE OF THIS AUDIT

This document defines the **scope, rules, and expectations** for an external audit of **Market Lens v3.0**.

Primary goals:
- Verify **correctness of calculations**
- Verify **end-to-end consistency** between TradingView (Pine) and Python backend
- Detect **logical contradictions** between strategy logic and textual output
- Validate **risk-related invariants** (WAIT / TRADE separation)

This is **NOT** a strategy improvement audit.
This is a **correctness and integrity audit**.

---

## 2. SYSTEM OVERVIEW (HIGH LEVEL)

Market Lens is an **event-driven intraday trading assistant**.

### Architecture (event-driven):
TradingView Pine (Trend Level PRO v3.7)
→ Webhook JSON alert
→ FastAPI server endpoint
→ Decision engine (P-Score + Kevlar)
→ Order calculator (only if TRADE)
→ Telegram notifier

### Strategy profile:
- Timeframe: M30
- Strategy type: Mean Reversion / Level Bounce
- Execution mode: LIMIT ORDER ON TOUCH
- No market orders
- No candle-close confirmation

---

## 3. ENTRY MODE (CRITICAL INVARIANT)

ENTRY_MODE = TOUCH_LIMIT

This is a hard invariant.

Implications:
- Orders are executed on price touching a level (touch-based limit)
- Candle close confirmation is NOT used
- Any mention of:
  - "wait for candle close"
  - "confirmation on close"
  - "M30 close required"
is a logic violation, even if calculations are correct.

---

## 4. AUDIT SCOPE (WHAT MUST BE VERIFIED)

### A. End-to-End Data Flow
Verify full chain:
1) Pine Script → Alert JSON payload
2) `bot/server.py` → validation + secret check
3) Server-side deduplication + DB persistence (`bot/database.py` / `bot/db.py`)
4) Decision logic (`bot/decision_engine.py` + `bot/pscore.py` + `bot/kevlar.py`)
5) Market data fetching (`bot/market_data.py`, `bot/prices.py`, `bot/sentiment.py`)
6) Telegram output (`bot/notifier.py`)
7) Integration tests (`test_integration.py`)

Identical inputs must always lead to identical decisions.

---

### B. Level Scoring & Classification (Grade + Color)
Strict mapping:
- sc ≥ 3.0 → STRONG (🟢)
- 1.0 ≤ sc < 3.0 → MEDIUM (🟡)
- sc < 1.0 → WEAK (🔴)

No smoothing, overrides, or alternative mapping.

Output must not show 🟡 for sc < 1.0.

---

### C. P-SCORE DECISION MODEL
Deterministic model:
- Base score: 50
- Level strength:
  - STRONG: +15
  - WEAK: −20
- Regime:
  - EXPANSION: +10
  - COMPRESSION: −10
  - NEUTRAL: 0
- RSI context:
  - Counter-trend only: +5
- Threshold:
  - P-SCORE ≥ 35 → TRADE allowed
  - P-SCORE < 35 → WAIT

Verify calculation location(s): `bot/pscore.py` and how it is used by `bot/decision_engine.py`.

---

### D. Kevlar Safety Filters (Blocking)
Filters must BLOCK trade:
- Momentum Instability
- RSI Panic Guard
- Missed Entry Check
- Sentiment Trap (Funding + VWAP logic)

If any Kevlar filter triggers, decision must be WAIT regardless of score.
Verify implementation: `bot/kevlar.py` and call site(s) in `bot/decision_engine.py`.

---

### E. Order Calculation (Single Source of Truth)
All order math must exist ONLY in:
- `bot/order_calc.py`

Required formulas:
- position_size = risk_usd / stop_distance
- RRR = abs(TP2 - entry) / stop_distance
- If RRR < 1.10 → TRADE blocked (WAIT)

No duplicated order math in other files.

---

### F. WAIT / TRADE OUTPUT CONTRACT (Text is logic)
Text output is part of strategy integrity.

Rules:
- WAIT must not contain execution instructions
- WAIT must not mention candle-close confirmation
- TRADE must respect TOUCH_LIMIT execution logic (no close-confirm language)

Verify output formatting in graphical/telegram layer: `bot/notifier.py` and decision model objects: `bot/decision_models.py`.

---

## 5. OUT OF SCOPE
Explicitly excluded:
- Strategy optimization / tuning
- New indicators / new filters
- UI / UX improvements
- Performance optimization
- Asset-specific adjustments

Any suggestions here must be labeled Out of Scope.

---

## 6. FILES TO REVIEW (CHECKLIST)

### Project root:
- requirements.txt
- pyproject.toml
- .env.example
- test_integration.py
- test_cro.py

### Backend (bot/):
- bot/server.py
- bot/main.py
- bot/config.py
- bot/database.py and/or bot/db.py (persistence)
- bot/decision_engine.py
- bot/decision_models.py
- bot/pscore.py
- bot/kevlar.py
- bot/market_data.py
- bot/prices.py
- bot/sentiment.py
- bot/indicators.py
- bot/notifier.py
- bot/analysis.py (if still used in pipeline)

### Tests:
- tests/test_config.py
- tests/test_db.py
- tests/test_prices.py

### TradingView:
- Pine Script: Trend Level PRO v3.7
- Alert configuration: JSON payload + secret header setup

---

## 7. DATA FOR REPLAY (RECOMMENDED)
Auditor should be given:
- 10–20 real webhook JSON payloads
- 10–20 `/sniper` outputs (Telegram text)
- 3–5 TradingView screenshots with timestamps
- SQLite DB snapshot (optional)

Auditor should replay payloads and verify determinism.

---

## 8. EXPECTED DELIVERABLES
Auditor must deliver:
- Audit report (Critical / Major / Minor)
- File + line references for each finding
- Reproduction steps (how to reproduce)
- Patch list (file-by-file), with priority labels (P0/P1/P2)

Out-of-scope items must be labeled explicitly.
