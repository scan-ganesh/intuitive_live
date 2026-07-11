"""
Configuration for multi-underlying strategy support.
Defines settings for each underlying (NIFTY, SENSEX, etc.)
"""

from datetime import time
import time as cache_time
from google.cloud import firestore
from typing import Dict, List

# ========================= CONFIG =========================
CANDLE_SIZE_MIN_PCT = 0.05
CANDLE_SIZE_MAX_PCT = 0.13

CACHE_TTL_SECONDS = 6 * 3600  # 6 hours

# Global cache
UNDERLYINGS_cache: Dict | None = None
cache_timestamp: float = 0.0
# ========================================================

def _load_strategy_config_from_firestore() -> Dict:
    """Internal function to load fresh config from Firestore."""
    print("Loading strategy configuration from Firestore...")
    db = firestore.Client()
    collection_ref = db.collection("references/COMMON/strategy_config")
    
    config_docs = collection_ref.stream()
    config_dict = {}
    
    for doc in config_docs:
        config_dict[doc.id] = doc.to_dict()
    
    # Convert time strings to datetime.time objects
    for settings in config_dict.values():
        if "entry_cutoff" in settings and isinstance(settings["entry_cutoff"], str):
            settings["entry_cutoff"] = time.fromisoformat(settings["entry_cutoff"])
        if "exit_cutoff" in settings and isinstance(settings["exit_cutoff"], str):
            settings["exit_cutoff"] = time.fromisoformat(settings["exit_cutoff"])
    
    return config_dict


def _ensure_cache_loaded() -> None:
    """Ensure cache is loaded and still valid. Loads only if necessary."""
    global UNDERLYINGS_cache, cache_timestamp
    
    current_time = cache_time.time()
    
    # Load if cache is empty or expired
    if (UNDERLYINGS_cache is None or 
        (current_time - cache_timestamp >= CACHE_TTL_SECONDS)):
        
        UNDERLYINGS_cache = _load_strategy_config_from_firestore()
        cache_timestamp = current_time


# ===================== PUBLIC API =====================

def get_all_underlyings() -> List[str]:
    """Get list of all configured underlyings."""
    _ensure_cache_loaded()
    return list(UNDERLYINGS_cache.keys())

def revise_quantity_to_trade(new_quantity: int) -> None:
    """
    Update the quantity to trade for all underlyings in Firestore.
    
    Args:
        new_quantity (int): The new quantity to set for trading.
    """
    _ensure_cache_loaded()
    
    db = firestore.Client()
    collection_ref = db.collection("references/COMMON/strategy_config")
    
    for underlying in UNDERLYINGS_cache.keys():
        doc_ref = collection_ref.document(underlying)
        doc_ref.update({"quantity": new_quantity})
        # Update the cache as well
        UNDERLYINGS_cache[underlying]["quantity"] = new_quantity
    
    print(f"Quantity to trade updated to {new_quantity} for all underlyings.")

def get_config(underlying: str) -> Dict:
    """
    Get configuration for a given underlying.
    
    Raises:
        ValueError: If underlying is not supported
    """
    _ensure_cache_loaded()
    
    if underlying not in UNDERLYINGS_cache:
        raise ValueError(
            f"Underlying '{underlying}' not found. "
            f"Supported: {list(UNDERLYINGS_cache.keys())}"
        )
    
    return UNDERLYINGS_cache[underlying]


def refresh_cache() -> None:
    """Force refresh the cache (useful for manual reloads)."""
    global UNDERLYINGS_cache, cache_timestamp
    UNDERLYINGS_cache = _load_strategy_config_from_firestore()
    cache_timestamp = cache_time.time()
    print("Cache refreshed successfully.")


# ===================== TESTING =====================
if __name__ == "__main__":
    # This will load the cache only once (on first call)
    for underlying in get_all_underlyings():
        config = get_config(underlying)
        print(f"{underlying}: {config}")