# Refactoring Plan: Support NIFTY & SENSEX Without Code Duplication

## Current State - Hardcoded NIFTY Dependencies

| Area | Hardcoded Elements | Files |
|------|-------------------|-------|
| **Function Names** | `get_nifty_quote()`, `get_nifty_history()` | `intuitive.py` |
| **Stock Code** | `"NIFTY"` in API calls | `intuitive.py` (lines 68, 78) |
| **ATM Calculation** | Division by 50 (NIFTY-specific) | `intuitive.py` line 88 |
| **Underlying Symbol** | `"NIFTY"` passed to strategy functions | `intuitive.py` line 91, 106, 130 |
| **Main Logic** | Single entry point for NIFTY only | `intuitive.py` line 154+ |
| **Telegram Messages** | References only candle, no underlying info | `intuitive.py` lines 123, 148 |

---

## Proposed Refactoring Strategy

### 1. Create Configuration Layer
**File:** `config.py` (NEW)

Define underlyings with their properties:
- `stock_code` (NIFTY, SENSEX, etc.)
- `atm_rounding_factor` (50 for NIFTY, 100 for SENSEX)
- `big_candle_thresholds` (min/max body size per underlying)
- `entry_cutoff_time`, `exit_cutoff_time`

**Example structure:**
```python
UNDERLYINGS = {
    "NIFTY": {
        "stock_code": "NIFTY",
        "exchange": "NSE",
        "product_type": "cash",
        "atm_rounding_factor": 50,
        "big_candle_min": 12,
        "big_candle_max": 30,
        "entry_cutoff": "15:00",
        "exit_cutoff": "15:15",
    },
    "SENSEX": {
        "stock_code": "SENSEX",
        "exchange": "BSE",
        "product_type": "cash",
        "atm_rounding_factor": 100,
        "big_candle_min": 15,
        "big_candle_max": 35,
        "entry_cutoff": "15:00",
        "exit_cutoff": "15:15",
    }
}
```

### 2. Genericize Core Functions in `intuitive.py`

Replace hardcoded functions with parameterized versions:

| Old Function | New Function | Change |
|--------------|--------------|--------|
| `get_nifty_quote()` | `get_quote(underlying)` | Accept underlying parameter |
| `get_nifty_history()` | `get_history(underlying, interval='5minute')` | Accept underlying parameter |
| `calculate_atm(current_price)` | `calculate_atm(current_price, underlying)` | Use config-based rounding factor |
| `get_strategy_positions()` | Already generic ✓ | No change needed |

### 3. Add Underlying-Aware Logic

- Modify `calculate_atm()` to use `UNDERLYINGS[underlying]["atm_rounding_factor"]`
- Update Telegram messages to include underlying symbol:
  - From: `"Big Candle detected! CE order placed..."`
  - To: `"NIFTY: Big Candle detected! CE order placed..."`
- Create strategy handler function: `execute_strategy(underlying)`

### 4. Refactor Main Execution Flow

**Old:** Single-pass `main_live()` for NIFTY only

**New:** Loop-based execution
```python
def main_live():
    for underlying in UNDERLYINGS.keys():
        execute_strategy(underlying)

def execute_strategy(underlying):
    # Core strategy logic (manage positions, detect big candles, place orders)
    # Uses underlying parameter throughout
```

### 5. Update Firestore References

**File:** `kite_utils.py` (MINOR CHANGES)

- Update `store_candle_reference_data(candle_data, underlying)` to accept underlying parameter
- Update `retrieve_candle_reference_data(underlying)` to retrieve by underlying
- Change Firestore document naming from:
  - Old: `candle_reference/{date}`
  - New: `candle_reference/{date}-{underlying}` or use subcollection

### 6. No Changes Needed

- ✓ `kite_utils.py` (core functions) - Already generic, takes `underlying` parameter
- ✓ `breeze_utils.py` - Already generic in API calls
- ✓ `kite_utils.calculate_trading_symbol()` - Already works with any underlying

---

## File Structure After Refactoring

```
intuitive_live/
├── config.py                 # NEW - Configuration for NIFTY, SENSEX, etc.
├── intuitive.py              # MODIFIED - Generic functions + main loop
├── kite_utils.py             # MINOR CHANGE - Firestore doc naming
├── breeze_utils.py           # NO CHANGE
├── .env                       # NO CHANGE (but can add more underlyings)
├── Dockerfile                # NO CHANGE
├── pyproject.toml            # NO CHANGE
└── README.md                 # UPDATE - Document multi-underlying support
```

---

## Implementation Steps

1. **Create `config.py`**
   - Define `UNDERLYINGS` dict with NIFTY and SENSEX configs
   - Add function to get config for a given underlying

2. **Modify `intuitive.py`**
   - Import config
   - Rename `get_nifty_quote()` → `get_quote(underlying)`
   - Rename `get_nifty_history()` → `get_history(underlying)`
   - Update `calculate_atm()` to accept `underlying` parameter
   - Create `execute_strategy(underlying)` function with core logic
   - Modify `main_live()` to loop through underlyings
   - Update all Telegram messages to include underlying symbol
   - Update candle reference data calls to include underlying

3. **Modify `kite_utils.py`**
   - Update `store_candle_reference_data()` signature
   - Update `retrieve_candle_reference_data()` signature
   - Update Firestore document naming logic

4. **Test**
   - Verify NIFTY strategy still works
   - Test SENSEX strategy
   - Check Firestore document structure
   - Validate Telegram messages include underlying

5. **Document**
   - Update README.md with multi-underlying support
   - Add example `.env` configuration

---

## Key Benefits

✅ **No code duplication** - One strategy loop serves multiple underlyings  
✅ **Easy to add more underlyings** - Just add to UNDERLYINGS dict (BANKNIFTY, FINNIFTY, etc.)  
✅ **Separate config** - Easy to tweak per-underlying settings without code changes  
✅ **Scalable** - Can run multiple instances with different configs  
✅ **Backward compatible** - Same API, same behavior for NIFTY  
✅ **Better Telegram clarity** - Messages specify which underlying triggered the action  

---

## Environment Variables (`.env`) - No Changes Needed

Current structure works as-is. The config.py can read from `.env` if per-underlying overrides are needed in future:
```makefile
API_KEY=<api_key>
API_SECRET=<api_secret>
SESSION_ID=<session_id>
TELEGRAM_FROM=<bot_token>
TELEGRAM_TO=<chat_id>
TELEGRAM_URL=<base_url>
```

Optional future additions:
```makefile
NIFTY_BIG_CANDLE_MIN=12
NIFTY_BIG_CANDLE_MAX=30
SENSEX_BIG_CANDLE_MIN=15
SENSEX_BIG_CANDLE_MAX=35
```

---

## Firestore Structure Changes

### Before:
```
candle_reference/
├── 2026-06-08 → {open, high, low, close, ...}
```

### After (Recommended):
```
candle_reference/
├── 2026-06-08-NIFTY → {open, high, low, close, ...}
├── 2026-06-08-SENSEX → {open, high, low, close, ...}
```

Or with subcollections:
```
candle_reference/
├── 2026-06-08/
│   ├── NIFTY → {open, high, low, close, ...}
│   └── SENSEX → {open, high, low, close, ...}
```

---

## Rollout Strategy

1. Create `config.py` with both NIFTY and SENSEX configs
2. Refactor `intuitive.py` functions to be generic but initially run only NIFTY
3. Test NIFTY extensively (no behavior change)
4. Enable SENSEX in main loop
5. Monitor both strategies
6. Document in README

This ensures minimal risk - we can keep NIFTY-only mode until confident.
