import datetime

from google.cloud import firestore
from dotenv import load_dotenv
import pandas as pd
import os

load_dotenv()
# Cache for expiry
expiry_cache = {}

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

    doc_name = datetime.now().strftime("%Y-%m-%d")
    db = firestore.Client()
    doc_ref = db.collection("candle_reference").document(doc_name)
    doc_ref.set(candle_data)

def retrieve_candle_reference_data():
    """Retrieve candle reference data from Firestore"""
    doc_name = datetime.now().strftime("%Y-%m-%d")
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

def calculate_LOTS(underlying):
    """Calculate lot size based on underlying"""
    LOTS = {
        "NIFTY": 65,
        "BANKNIFTY": 25
    }
    return LOTS.get(underlying, 0)

def get_strategy_positions(underlying_symbol="NIFTY"):
    
    positions = get_positions()
    if not positions:
        return []
    # we will filter data.day that contains the positions for the day. Filter by tradingsymbol that starts with the underlying symbol (e.g., "NIFTY") and ends with "CE" or "PE" 
    filtered_positions = [pos for pos in positions if pos.get("tradingsymbol", "").startswith(underlying_symbol) and (pos.get("tradingsymbol", "").endswith("CE") or pos.get("tradingsymbol", "").endswith("PE"))]
    
    return filtered_positions


# method that calculates the trading symbol for the given underlying, strike, right and expiry. Formula for the same will be Weekly- Index/Stock Name +Year of Expiry(numerical) +Month of expiry(numerical) + Day of expiry(numerical) + Strike and Option type(or FUT for futures) Regex- (?:(.*?)(\d{2}[A-Za-z0-9_]{1}\d{3})(.*)){1,1}. Expiry date will be a string yyyy-mm-dd. While formatting the date use yyMdd for the months which are in single digits and yyMMMMMdd for two digit months, Exanple 26523 for 23rd of May 2026. 26OCT23 for 23rd of October 2026. 

def calculate_trading_symbol(underlying, strike, right, expiry_date):
    expiry_dt = pd.to_datetime(expiry_date)
    year = expiry_dt.year % 100  # Get last two digits of the year
    month = expiry_dt.month
    day = expiry_dt.day

    if month < 10:
        month_str = f"{month}"
        date_str = f"{year}{month_str}{day}"
    else:
        month_str = expiry_dt.strftime("%b").upper()  # Get abbreviated month name in uppercase
        date_str = f"{year}{month_str}{day}"

    trading_symbol = f"{underlying}{date_str}{strike}{right.upper()}"
    return trading_symbol

def place_order(payload):
    kite_client = get_kite_client()
    if not kite_client:
        print("Failed to initialize KiteConnect client.")
        return None
    
    try:
        order_id = kite_client.place_order(
            variety=payload.get("variety", kite_client.VARIETY_REGULAR),
            exchange=payload["exchange_code"],
            tradingsymbol=calculate_trading_symbol(payload["underlying"], payload["strike_price"], payload["right"], payload["expiry_date"]),
            transaction_type=payload["transaction_type"],
            quantity=calculate_LOTS(payload["underlying"]) * payload["quantity"],
            product=payload.get("product", kite_client.PRODUCT_MIS),  # Default to MIS if not specified
            order_type=payload.get("order_type", kite_client.ORDER_TYPE_MARKET),  # Default to market order
            validity=payload.get("validity", kite_client.VALIDITY_DAY)  # Default to day validity
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
                validity=kite_client.VALIDITY_DAY
            )
            print(f"Squared off {pos['tradingsymbol']} | Order ID: {order_id}")

    except Exception as e:
        print(f"Error executing square off: {e}")



def get_next_expiry_date(date):
    if date in expiry_cache:
        return expiry_cache[date]

    try:
        df = pd.read_csv("expiry_dates.csv")
        df["expiry_date"] = pd.to_datetime(df["expiry_date"])
        date_dt = pd.to_datetime(date)
        mask = df["expiry_date"] >= date_dt
        if not mask.any():
            next_expiry = None
        else:
            next_expiry = df.loc[mask, "expiry_date"].min().strftime("%Y-%m-%d")
        expiry_cache[date] = next_expiry
        return next_expiry
    except Exception as e:
        print(f"Error reading expiry_dates.csv: {e}")
        return None

if __name__ == "__main__":
    result = calculate_trading_symbol("NIFTY", 17500, "CE", "2026-05-23")
    print(result)
    result1 = calculate_trading_symbol("NIFTY", 17500, "CE", "2026-10-23")
    print(result1)
