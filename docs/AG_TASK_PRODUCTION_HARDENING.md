# AG_TASK_PRODUCTION_HARDENING.md

## TASK TYPE

**Full Refactor & Stability Hardening**
Mode: Deterministic Production Upgrade
Priority: **CRITICAL**

---

## 1. OBJECTIVE

Transform current Ticker Bot / Market Lens backend into:
- Deterministic
- Fail-safe
- Strictly validated
- Log-consistent
- Production-ready
- SaaS-scalable

**No new features.**
Only correctness, safety, determinism, architecture discipline.

---

## 2. EXECUTION RULES (MANDATORY)

1. No partial fixes.
2. No silent error suppression.
3. No duplicated configuration sources.
4. No undefined behavior on missing data.
5. Every change must include tests.
6. All fixes must preserve signal logic integrity.

---

## 3. PHASE 1 — CRITICAL STABILITY FIXES (P0)

### 3.1 Fix TieredCache Inconsistency

**Problem**

`cache.set()` is used but not implemented.

**Required Actions**
- Implement `async set()` method in `TieredCache`

OR
- Refactor to remove direct `set()` calls and unify via `get_or_set()`

**Deliverables**
- Updated `cache.py`
- Unit tests for:
  - cache hit
  - cache miss
  - TTL expiration
  - No `AttributeError` possible

---

### 3.2 Enforce Real Price Freshness

**Problem**

`max_age_seconds` parameter is ineffective.

**Required Actions**
- Store price with timestamp
- Validate age before returning cached price

OR
- Remove parameter entirely and simplify contract

**Acceptance Criteria**
- No stale price > allowed age
- Deterministic behavior on expired cache

---

## 4. PHASE 2 — SECURITY HARDENING (P1)

### 4.1 Strict Symbol Validation

**Required Behavior**

Reject any symbol not matching:

```
^[A-Z0-9]{2,10}$
```

Allowed quotes strictly from `ALLOWED_QUOTES`.

**Must Guarantee**
- No malformed URL calls
- No injection via symbol input
- Explicit rejection response

---

### 4.2 Remove Silent Failures

**Prohibited Pattern**

```python
except Exception:
    pass
```

**Required**
- Replace with specific exception types
- Fail-fast in `/sniper` pipeline
- On incomplete data → explicit NO TRADE

**Acceptance Criteria**
- No generic `Exception` swallowing in critical logic
- No silent execution branches

---

### 4.3 Unified Logging Standard

**Required**
- Single logging framework (prefer `structlog`)
- Every major decision log must include:
  - `trace_id`
  - `symbol`
  - `decision_id`
  - `latency_ms`
  - `outcome`

**Deliverable**

Central logging module + consistent usage

---

## 5. PHASE 3 — ARCHITECTURE CLEANUP (P2)

### 5.1 Configuration Unification

Currently:
- `TradingSettings`
- `Config` class

**Required**

Single source of truth using:
- `pydantic-settings`
- Typed env config
- Immutable runtime config

---

### 5.2 Interface Isolation

Refactor into:

```
domain/
    analysis/
    risk/
    kevlar/
    data/
adapters/
    telegram/
    webhook/
```

Core logic must not depend on transport layer.

---

### 5.3 Repository Hygiene

**Remove:**
- `.DS_Store`
- `.backup` files
- `test_output.html`
- scattered test files

**Move:**
- all tests → `/tests`
- verification scripts → `/scripts`

---

## 6. PHASE 4 — DETERMINISM & SAFETY

### 6.1 Capital Protection Enforcement

Any of the following must trigger **NO TRADE**:
- missing ATR
- missing price
- insufficient candles
- missing levels
- invalid RRR
- high funding conflict

**Fail explicitly. Never degrade silently.**

---

### 6.2 Full Pipeline Integration Test

Add integration test:

```
/sniper BTC
```

Must verify:
- deterministic output
- SL/TP consistency
- RRR correct
- Kevlar blocking logic works
- no hidden fallback behavior

---

## 7. QUALITY ENFORCEMENT

Enable:
- `mypy` strict mode
- `ruff` full lint pass
- `black` formatting
- no unused imports
- no `Any` in domain logic

---

## 8. ACCEPTANCE CRITERIA (GLOBAL)

System is accepted only if:
- No P0 or P1 issues remain
- All tests pass
- Deterministic output confirmed
- No silent exception handling
- No duplicated config sources
- Logs are structured and consistent
- System boot works without shell hacks
- Behavior reproducible across environments

---

## 9. OUTPUT FORMAT REQUIRED FROM ANTIGRAVITY

After implementation, generate:
1. `CHANGELOG_PRODUCTION_HARDENING.md`
2. Summary of refactors
3. Test coverage report
4. List of breaking changes (if any)

---

## 10. END STATE

The system must behave like:

> **Institutional-grade decision engine**
> Not a hobby Telegram bot

- Deterministic
- Auditable
- Fail-safe
- SaaS-ready

---

**END OF TASK**
