import datetime
from datetime import timedelta
from google.cloud import firestore
from dotenv import load_dotenv
import pandas as pd
import time
import os
import strategy_config 
from utils.storage_utils import _get_underlying_reference_data, get_next_expiry_date_v2

load_dotenv()
# Cache for symbol information


customer_cache = None
cache_timestamp = 0  # Stores the epoch time when the cache was created
CACHE_TTL_SECONDS =  3600  # Set expiry time (e.g., 1 hour = 3600 seconds)

def get_customer_data():
    global customer_cache, cache_timestamp
    current_time = time.time()
    if customer_cache is not None and (current_time - cache_timestamp < CACHE_TTL_SECONDS):
        return customer_cache

    db = firestore.Client()

    doc_ref = db.collection("customers").document("DG1262")
    doc_snapshot = doc_ref.get()
    data = None
    if doc_snapshot.exists:
        # to_dict() converts the Firestore document fields into a Python dictionary
        data = doc_snapshot.to_dict()

    customer_cache = data
    cache_timestamp = current_time
    return data

def store_candle_reference_data(candle_data, underlying: str = "NIFTY"):
    """Store candle data in Firestore for reference"""
    # document name should be today's date and underlying in yyyy-mm-dd-UNDERLYING format

    doc_name = datetime.datetime.now().strftime("%Y-%m-%d") + f"-{underlying}"
    db = firestore.Client()
    doc_ref = db.collection("candle_reference").document(doc_name)
    doc_ref.set(candle_data)

def retrieve_candle_reference_data(underlying: str = "NIFTY"):
    """Retrieve candle reference data from Firestore"""
    doc_name = datetime.datetime.now().strftime("%Y-%m-%d") + f"-{underlying}"
    db = firestore.Client()
    doc_ref = db.collection("candle_reference").document(doc_name)
    try:
        doc_snapshot = doc_ref.get()
        if doc_snapshot.exists:
            return doc_snapshot.to_dict()
        else:
            print(f"No candle reference data found for {doc_name}")
            return None
    except Exception as e:
        print(f"Error retrieving candle reference data: {e}")
        return None

def get_kite_client():
    from kiteconnect import KiteConnect
    customer_data = get_customer_data()
    if not customer_data:
        print("Failed to retrieve customer data. Cannot initialize KiteConnect client.")
        return None

    api_key = os.getenv("KITE_API_KEY")
    access_token = customer_data.get("access_token")

    if not api_key or not access_token:
        print("Kite API key or access token is missing in customer data.")
        return None

    kite_client = KiteConnect(api_key=api_key, access_token=access_token)
   
    return kite_client

def get_positions():
    """Get current NIFTY options positions"""
    kite_client = get_kite_client()
    if not kite_client:
        print("Failed to initialize KiteConnect client.")
        return []
    
    try:
        positions = kite_client.positions()  # This returns a dictionary with 'net' and 'day' positions
        return positions.get("net", [])  # Return only net positions
    except Exception as e:
        print(f"Error fetching positions from KiteConnect: {e}")
        return []


def get_strategy_positions(underlying_symbol="NIFTY"):
    
    positions = get_positions()
    if not positions:
        return []
    # we will filter data.day that contains the positions for the day. Filter by tradingsymbol that starts with the underlying symbol (e.g., "NIFTY") and ends with "CE" or "PE" 
    filtered_positions = [pos for pos in positions if pos.get("quantity") > 0 and pos.get("tradingsymbol", "").startswith(underlying_symbol) and (pos.get("tradingsymbol", "").endswith("CE") or pos.get("tradingsymbol", "").endswith("PE"))]
    
    return filtered_positions


def format_zerodha_weekly_expiry(e_date: datetime) -> str:
    """
    Format expiry date according to Zerodha/NSE weekly & monthly option symbol convention.
    
    - Weekly expiry: yyMdd  (e.g., 26O15, 26318)
    - Monthly expiry: yyMMM (e.g., 26MAR)
    """
    # Check if this is the last expiry of the month (monthly expiry)
    compare_date = e_date + timedelta(days=8)
    
    if e_date.month != compare_date.month:
        # Monthly expiry → yyMMM (e.g., 26MAR)
        return e_date.strftime('%y%b').upper()
    
    # Weekly expiry
    yy = e_date.strftime('%y')
    dd = e_date.strftime('%d')
    
    month = e_date.month  # 1-based in Python (1=Jan, ..., 12=Dec)
    
    if month >= 10:
        # October, November, December
        month_map = {10: 'O', 11: 'N', 12: 'D'}
        m = month_map[month]
    else:
        # January to September → single digit
        m = str(month)
    
    return f"{yy}{m}{dd}"

# method that calculates the trading symbol for the given underlying, strike, right and expiry. Formula for the same will be Weekly- Index/Stock Name +Year of Expiry(numerical) +Month of expiry(numerical) + Day of expiry(numerical) + Strike and Option type(or FUT for futures) Regex- (?:(.*?)(\d{2}[A-Za-z0-9_]{1}\d{3})(.*)){1,1}. Expiry date will be a string yyyy-mm-dd. While formatting the date use yyMdd for the months which are in single digits and yyMMMMMdd for two digit months, Exanple 26523 for 23rd of May 2026. 26OCT23 for 23rd of October 2026. 

def calculate_trading_symbol(underlying, strike, right):

    expiry_date_v2, _ = get_next_expiry_date_v2(datetime.date.today().strftime("%Y-%m-%d"), underlying)
    expiry_dt = format_zerodha_weekly_expiry(pd.to_datetime(expiry_date_v2))

    print(f"Calculated expiry date for {underlying} is {expiry_date_v2} and formatted expiry is {expiry_dt}")

    trading_symbol = f"{underlying}{expiry_dt}{strike}{right.upper()}"
    return trading_symbol

def place_order(payload):
    kite_client = get_kite_client()
    if not kite_client:
        print("Failed to initialize KiteConnect client.")
        return None
    tradingsymbol=calculate_trading_symbol(payload["underlying"], payload["strike_price"], payload["right"])
    print(f"Placing order for {tradingsymbol} with quantity {payload['quantity']} and transaction type {payload['transaction_type']}")
    try:
        order_id = kite_client.place_order(
            variety=payload.get("variety", kite_client.VARIETY_REGULAR),
            exchange=get_exchange(payload["underlying"]),
            tradingsymbol=tradingsymbol,
            transaction_type=payload["transaction_type"],
            quantity=get_lot_size(payload["underlying"]) * payload["quantity"],
            product=payload.get("product", kite_client.PRODUCT_MIS),  # Default to MIS if not specified
            order_type=payload.get("order_type", kite_client.ORDER_TYPE_MARKET),  # Default to market order
            validity=payload.get("validity", kite_client.VALIDITY_DAY),  # Default to day validity
            market_protection=1
        )
        return order_id
    except Exception as e:
        print(f"Error placing order: {e}")
        print("The payload was:", payload)
        return None

def square_off_strategy_positions(underlying):
    kite_client = get_kite_client()
    try:
        # Fetch all day and net positions
        positions = get_strategy_positions(underlying)

        for pos in positions:
            quantity = pos.get("quantity", 0)
            
            # Skip if the position is already squared off (quantity is 0)
            if quantity == 0:
                continue

            # Determine the opposite transaction type to close out
            if quantity > 0:
                transaction_type = kite_client.TRANSACTION_TYPE_SELL
                action_qty = quantity
            else:
                transaction_type = kite_client.TRANSACTION_TYPE_BUY
                action_qty = abs(quantity)

            # Place the counter order to square off
            order_id = kite_client.place_order(
                variety=kite_client.VARIETY_REGULAR,
                exchange=pos["exchange"],
                tradingsymbol=pos["tradingsymbol"],
                transaction_type=transaction_type,
                quantity=action_qty,
                product=pos["product"], # Must match the original product (e.g., MIS, NRML, CNC)
                order_type=kite_client.ORDER_TYPE_MARKET, # Market order ensures instant exit
                validity=kite_client.VALIDITY_DAY,
                market_protection=1
            )
            print(f"Squared off {pos['tradingsymbol']} | Order ID: {order_id}")

    except Exception as e:
        print(f"Error executing square off: {e}")


def get_lot_size(underlying):
    """Get lot size for the underlying"""
    ref_data = _get_underlying_reference_data(underlying)
    return ref_data['lot_size'] if ref_data else 0

def _available_funds() -> float:
    """Fetches available funds from Zerodha account."""
    client = get_kite_client()
    if not client:
        print("Error: Kite client uninitialized. Cannot fetch funds.")
        return 0.0
    return client.margins(segment="equity").get("available", 0.0).get('cash', 0.0)

def revise_quantity_to_trade() -> int:
    """Returns the quantity to trade for the strategy."""
    # two indices and each costs 25K per lot. So, 50K for two indices per lot
    # we need to dynamically calculate the quantity based on available funds and take the floor value
    available_funds = _available_funds()

    #reserve 50L for non-strategy trades and another 50K for SENSEX (2 lots). So, we will only use the remaining funds for strategy trades.
    available_funds -= 100000
    lot_cost = 25000  # Cost for NIFTY per lot. This can be made dynamic in future if needed.
    quantity = int(available_funds // lot_cost)

    strategy_config.revise_quantity_to_trade(quantity)

    return quantity

def get_exchange(underlying):
    """Get exchange for the underlying"""
    ref_data = _get_underlying_reference_data(underlying)
    return ref_data['exchange'] if ref_data else None

if __name__ == "__main__":
    print(calculate_trading_symbol("NIFTY", 23500, "CE"))
    print(calculate_trading_symbol("NIFTY", 23600, "CE"))
    print(get_lot_size("SENSEX"))
    print(get_exchange("NIFTY"))
    print(get_exchange("SENSEX"))
    
