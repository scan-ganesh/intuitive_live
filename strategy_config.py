"""
Configuration for multi-underlying strategy support.
Defines settings for each underlying (NIFTY, SENSEX, etc.)
"""

from datetime import time

# Global candle size thresholds (percentage-based, applies to all underlyings)
CANDLE_SIZE_MIN_PCT = 0.05  # Minimum body size as percentage of close price
CANDLE_SIZE_MAX_PCT = 0.13  # Maximum body size as percentage of close price

# Define all supported underlyings and their configurations
UNDERLYINGS = {
    "NIFTY": {
        "stock_code": "NIFTY",
        "exchange_code": "NSE",
        "product_type": "cash",
        "atm_rounding_factor": 50,  # ATM strike rounding
        "entry_cutoff": time(15, 0),  # After this time, no new entries
        "exit_cutoff": time(15, 15),  # EOD exit time
        "neo_exchange_segment": "nse_fo",  # Specific segment code for Neo API
    },
    "SENSEX": {
        "stock_code": "BSESEN",
        "exchange_code": "BSE",
        "product_type": "cash",
        "atm_rounding_factor": 100,  # ATM strike rounding (100 for SENSEX)
        "entry_cutoff": time(15, 0),  # After this time, no new entries
        "exit_cutoff": time(15, 15),
        "neo_exchange_segment": "bse_fo",  # Specific segment code for Neo API
    },
}


def get_config(underlying: str) -> dict:
    """
    Get configuration for a given underlying.
    
    Args:
        underlying: Underlying symbol (e.g., "NIFTY", "SENSEX")
    
    Returns:
        Configuration dictionary for the underlying
    
    Raises:
        ValueError: If underlying is not supported
    """
    if underlying not in UNDERLYINGS:
        raise ValueError(f"Underlying '{underlying}' not found in configuration. Supported: {list(UNDERLYINGS.keys())}")
    
    return UNDERLYINGS[underlying]


def get_all_underlyings() -> list:
    """Get list of all configured underlyings."""
    return list(UNDERLYINGS.keys())


if __name__ == "__main__":
    # Test configuration
    for underlying in get_all_underlyings():
        config = get_config(underlying)
        print(f"{underlying}: {config}")
