import datetime

from google.cloud import firestore
from dotenv import load_dotenv
import pandas as pd
import os

load_dotenv()
# Cache for symbol information
syminfo_cache = {}

customer_cache = None

def get_customer_data():
    global customer_cache
    if customer_cache is not None:
        return customer_cache

    db = firestore.Client()

    doc_ref = db.collection("customers").document("DG1262")
    doc_snapshot = doc_ref.get()
    data = None
    if doc_snapshot.exists:
        # to_dict() converts the Firestore document fields into a Python dictionary
        data = doc_snapshot.to_dict()

    customer_cache = data
    return data

def store_candle_reference_data(candle_data):
    """Store candle data in Firestore for reference"""
    # document name should be today's date in yyyy-mm-dd format

    doc_name = datetime.datetime.now().strftime("%Y-%m-%d")
    db = firestore.Client()
    doc_ref = db.collection("candle_reference").document(doc_name)
    doc_ref.set(candle_data)

def retrieve_candle_reference_data():
    """Retrieve candle reference data from Firestore"""
    doc_name = datetime.datetime.now().strftime("%Y-%m-%d")
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
    # Get 2-digit year (e.g., '26') and 2-digit day (e.g., '15')
    yy = e_date.strftime('%y')
    dd = e_date.strftime('%d')
    
    # JavaScript getMonth() >= 9 covers October (10), November (11), December (12)
    if e_date.month >= 10:
        # Map 2-digit months to Zerodha's weekly codes (O, N, D)
        month_map = {10: 'O', 11: 'N', 12: 'D'}
        m = month_map[e_date.month]
    else:
        # January to September remain single digits (1 to 9)
        m = str(e_date.month)
        
    return f"{yy}{m}{dd}"

# method that calculates the trading symbol for the given underlying, strike, right and expiry. Formula for the same will be Weekly- Index/Stock Name +Year of Expiry(numerical) +Month of expiry(numerical) + Day of expiry(numerical) + Strike and Option type(or FUT for futures) Regex- (?:(.*?)(\d{2}[A-Za-z0-9_]{1}\d{3})(.*)){1,1}. Expiry date will be a string yyyy-mm-dd. While formatting the date use yyMdd for the months which are in single digits and yyMMMMMdd for two digit months, Exanple 26523 for 23rd of May 2026. 26OCT23 for 23rd of October 2026. 

def calculate_trading_symbol(underlying, strike, right):

    expiry_date_v2 = get_next_expiry_date_v2(datetime.date.today().strftime("%Y-%m-%d"), underlying)
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
        return None

def square_off_strategy_positions():
    kite_client = get_kite_client()
    try:
        # Fetch all day and net positions
        positions = get_strategy_positions()

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


def _get_underlying_reference_data(underlying):
    """Helper: Fetch and cache reference data for an underlying (lot_size, exchange, options expiries)"""
    if underlying in syminfo_cache:
        print(f"Using cached reference data for {underlying}")
        return syminfo_cache[underlying]
    
    db = firestore.Client()
    collection_ref = db.collection('references/COMMON/EXPIRYDATES')
    doc_ref = collection_ref.document(underlying)
    doc_snapshot = doc_ref.get()
    
    if not doc_snapshot.exists:
        print(f"No expiry data found in Firestore for underlying: {underlying}")
        return None

    data = doc_snapshot.to_dict()
    
    cached_data = {
        'lot_size': data.get('lot_size', 0),
        'exchange': data.get('exchange', ''),
        'options': sorted(list(data.get('options', [])))
    }
    
    syminfo_cache[underlying] = cached_data
    return cached_data


def get_lot_size(underlying):
    """Get lot size for the underlying"""
    ref_data = _get_underlying_reference_data(underlying)
    return ref_data['lot_size'] if ref_data else 0


def get_exchange(underlying):
    """Get exchange for the underlying"""
    ref_data = _get_underlying_reference_data(underlying)
    return ref_data['exchange'] if ref_data else None


def get_next_expiry_date_v2(date, underlying):
    """Get next expiry date after the given date for the underlying"""
    ref_data = _get_underlying_reference_data(underlying)
    if not ref_data:
        return None
    
    all_expiries = ref_data['options']
    date_dt = pd.to_datetime(date)
    
    for expiry_str in all_expiries:
        if pd.to_datetime(expiry_str) > date_dt:
            return expiry_str
    
    return None



if __name__ == "__main__":
    print(calculate_trading_symbol("NIFTY", 23500, "CE"))
    print(calculate_trading_symbol("NIFTY", 23600, "CE"))
    print(get_lot_size("SENSEX"))
    print(get_exchange("NIFTY"))
    print(get_exchange("SENSEX"))
    
