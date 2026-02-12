# Release Notes: Market Lens Bot v3.7-alpha1

**Date:** 2026-02-12
**Tag:** `v3.7-alpha1`
**Codename:** "Pine Sync & Kevlar Armor"

---

## 🚀 Key Highlights

This release marks a critical stabilization milestone. We have strictly aligned the Python logic with Pine Script v3.7 specifications, fixed critical data integrity issues, and hardened the bot against "rogue instance" conflicts.

### 1. Critical Logic Fixes (P0)
- **Pivot Detection Synced:** Changed `left_bars` and `right_bars` from **10** to **4** in `indicators.py`. This fixed the "No Levels" bug where the bot failed to detect obvious support/resistance zones. Sensitivity is now ~2.5x higher, matching the TradingView indicator.
- **Instance Locking:** Implemented `fcntl` lock file (`/tmp/marketlens-bot.lock`) in `main.py`. It is now impossible to accidentally run two instances of the bot, preventing `TelegramConflictError`.
- **Kevlar "Falling Knife" Tuned:** Relaxed `K2_NO_BRAKES` threshold from **-3%** to **-5%** and added data sufficiency checks. This reduces false positives while still protecting against crashes.

### 2. Diagnostic System
- **Deep Data Inspection:** `get_technical_indicators` now performs rigorous checks on:
    - Candle data existence and shape.
    - Timeframe accuracy (verifies 30m intervals).
    - Pivot detection internal logic (logs how many pivots found).
- **Self-Healing:** The bot now explicitly logs *why* it fails (e.g., `❌ WRONG TIMEFRAME`), allowing for instant debugging.

### 3. Stability & Infrastructure
- **Systemd Ready:** Full support for `systemctl` management.
- **Process Cleanup:** Rogue process termination protocols established.

---

## ⚠️ Upgrade Instructions

1. **Stop existing services:**
   ```bash
   sudo systemctl stop marketlens-bot
   ```

2. **Pull changes:**
   ```bash
   git pull origin main
   ```

3. **Restart service:**
   ```bash
   sudo systemctl restart marketlens-bot
   ```

4. **Verify:**
   ```bash
   journalctl -u marketlens-bot -f
   ```
   Look for: `logger.info("bot_started", version="v3.7-alpha1")`

---

## Known Issues (Alpha)
- `ccxt` fetching may occasionally timeout on weak networks (Auto-retry implemented).
- `/audit` command is still in Beta (VC-Analysis logic validation pending).
