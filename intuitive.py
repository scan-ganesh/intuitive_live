import os
from breeze_connect import BreezeConnect

# Load environment variables
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
SESSION_ID = os.getenv("SESSION_ID")

# Initialize Breeze API connection
breeze = BreezeConnect(api_key=API_KEY, api_secret=API_SECRET, session_id=SESSION_ID)

# Get historical data for NIFTY for the current day
data = breeze.get_historical_data_v2(
    stock_code="NIFTY",
    exchange_code="NFO",
    product_type="options",
    expiry_date=breeze.get_expiration_date("NFO", "NIFTY", "options"),
    from_date=breeze.get_last_trading_day(),
    to_date=breeze.get_last_trading_day(),
    interval="1minute"
)

print(data)
