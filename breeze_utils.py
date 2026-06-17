from breeze_connect import BreezeConnect
import time
import os
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
app_key = os.environ.get("BREEZE_API_KEY")
app_secret = os.environ.get("BREEZE_API_SECRET")
api_session = os.environ.get("BREEZE_API_SESSION")

# --- Global Cache ---
breeze_session_cache = None
cache_timestamp = 0
CACHE_TTL_SECONDS = 7 * 3600 # 7 hours

api_counter = 0

def generate_session():
    global breeze_session_cache, cache_timestamp, api_counter
    
    current_time = time.time()
    api_counter += 1

    # Rate limiting
    if api_counter % 98 == 1 and api_counter > 98:
        print("Sleeping for a minute due to rate limit...")
        time.sleep(62)
        api_counter = 0

    # === CACHE CHECK ===
    if (breeze_session_cache is not None and 
        (current_time - cache_timestamp < CACHE_TTL_SECONDS)):
        print("✅ Using cached session")
        return breeze_session_cache

    print("🔄 Cache expired or empty. Generating new session...")

    try:
        breeze = BreezeConnect(api_key=app_key)
        start_time = time.time()
        breeze.generate_session(api_secret=app_secret, session_token=api_session)
        end_time = time.time()
        print(f"Session generated in {end_time - start_time:.2f} seconds")
        # Update cache
        breeze_session_cache = breeze
        cache_timestamp = current_time
        
        print("✅ New session generated and cached")
        return breeze
        
    except Exception as e:
        print(f"❌ Error generating session: {e}")
        raise

# --- Main Function ---


def get_prices(payload, type='quote'):

    try:
        breeze = generate_session()
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
    breeze = generate_session()
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
        breeze = generate_session()
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
        breeze = generate_session()
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
        breeze = generate_session()
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