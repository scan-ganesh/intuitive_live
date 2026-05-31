import breeze_connect
import time
import os
from dotenv import load_dotenv
# Load .env into environment
load_dotenv()

# --- Configuration ---
app_key = os.environ.get("BREEZE_API_KEY")
app_secret = os.environ.get("BREEZE_API_SECRET")
api_session = os.environ.get("BREEZE_API_SESSION")

# --- Global Variables ---
breeze = breeze_connect.BreezeConnect(api_key=app_key)
api_counter = 0
breeze_session_cache = None

# --- Helper Functions ---
def sleep(ms):
    """Waits for a specified number of milliseconds."""
    time.sleep(ms / 1000)

def generate_session():
    """
    Generates a new session or returns a cached one.
    Handles session generation and caching synchronously.
    """
    global api_counter
    api_counter += 1
    
    # API call limit logic (98 calls per minute)
    if api_counter % 98 == 1 and api_counter > 98:
        print("Sleeping for a minute...")
        sleep(62000)  # Sleep
        api_counter = 0  # Reset counter after sleep

    global breeze_session_cache
    if breeze_session_cache:
        return breeze_session_cache
    else:
        breeze.generate_session(api_secret=app_secret, session_token=api_session)
        breeze_session_cache = breeze
        return breeze

# --- Main Function ---


def get_prices(payload, type='quote'):

    try:
        generate_session()
        if type == 'quote':
            prices = breeze.get_quotes(**payload)
        elif type == 'historical':
            prices = breeze.get_historical_data_v2(**payload)

        else:
            raise ValueError("Invalid type specified. Use 'quote' or 'historical'.")
    except Exception as err:
        print("Error with payload:", payload)
        print("Error:", err)
        return None
    if not prices or prices.get('Status') != 200:
        print("Error with payload:", payload)
        return None
    success_data = prices.get('Success')
    return success_data

def get_portfolio_positions():
    """
    Fetches current portfolio positions.
    """
    generate_session()
    positions = breeze.get_portfolio_positions()
    if positions is None:
        print("Error fetching portfolio positions.")
        return None
    
    return positions.get('Success')

def place_order(payload):
    """
    Places an order with the given payload.
    """
    try:
        generate_session()
        payload['validity'] = 'day'
        order_response = breeze.place_order(**payload)
    except Exception as err:
        print("Error+++:", err)
        return None
    if not order_response or order_response.get('Status') != 200:
        print("Error placing order with payload:", payload, "Response:", order_response)
        raise ValueError("Order placement failed or status not 200")
    success_data = order_response.get('Success')
    return success_data

def square_off(payload):
    """
    Squares off an existing position with the given payload.
    """
    try:
        generate_session()
        square_off_response = breeze.square_off(**payload)
        print(square_off_response)
    except Exception as err:
        print("Error squaring off position with payload:", payload)
        print("Error:", err)
        return None
    if not square_off_response or square_off_response.get('Status') != 200:
        print("Error squaring off position with payload:", payload)
        raise ValueError("Square off failed or status not 200")
    success_data = square_off_response.get('Success')
    return success_data

def get_margin(exchange_code='NFO'):
    """
    Fetches margin details for the specified exchange.
    """
    try:
        generate_session()
        margin_response = breeze.get_margin(exchange_code=exchange_code)
    except Exception as err:
        print("Error fetching margin for exchange:", exchange_code)
        print("Error:", err)
        return None
    if not margin_response or margin_response.get('Status') != 200:
        print("Error fetching margin for exchange:", exchange_code)
        raise ValueError("Margin fetch failed or status not 200")
    success_data = margin_response.get('Success')
    return success_data