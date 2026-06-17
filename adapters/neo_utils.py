"""
Script to get portfolio holdings using Kotak Neo API v2 REST API.
This script reads authentication data from Google Cloud Secret Manager
and makes REST API calls without using the Python SDK.
"""
import os
import pyotp
from datetime import datetime, date
from google.cloud import firestore

from utils.storage_utils import get_next_expiry_date_v2
import pandas as pd

from dotenv import load_dotenv
from neo_api_client import NeoAPI

load_dotenv()

   
def get_client():
    data = get_cached_kotak_token()
    
    if not data:
        print("Failed to load authentication data. Cannot initialize NeoAPI client.")
        return None
    client = NeoAPI(environment='prod', access_token=None, neo_fin_key=None, consumer_key=os.getenv('NEO_TOKEN'))
    client.configuration.edit_token = data.get("token")
    client.configuration.edit_sid = data.get("sid")
    client.configuration.edit_rid = data.get("rid")
    client.configuration.serverId = data.get("hsServerId")
    client.configuration.data_center = data.get("dataCenter")
    client.configuration.base_url = data.get("baseUrl")
    return client


def refresh_kotak_token_in_firestore():
    """Generates token and caches it directly to your active Firestore database."""
    print("🔄 Executing Firestore-backed session token refresh...")
    
    # Generate current 2FA PIN
    totp_seed = os.getenv('NEO_TOTP_SEED')
    clean_seed = totp_seed.replace(" ", "").upper().rstrip("=")
    current_totp_pin = pyotp.TOTP(clean_seed).now()

    client = NeoAPI(
        environment='prod', 
        access_token=None, 
        neo_fin_key=None, 
        consumer_key=os.getenv('NEO_TOKEN')
    )
    
    totp_response = client.totp_login(
        mobile_number=os.getenv('NEO_MOBILE'), 
        ucc=os.getenv('NEO_UCC'), 
        totp=current_totp_pin
    )

    
    if totp_response['data'].get('status') == 'success':
        validate_response = client.totp_validate(mpin=os.getenv('NEO_MPIN'))
        
        data = validate_response.get('data', {})
        
        if data:
            # Overwrite the persistent validation record
            db = firestore.Client()
            doc_ref = db.collection("auth_tokens").document("kotak_neo")
            
            doc_ref.set({
                "data": data,
                "updated_at": datetime.now().isoformat()
            })
            print("✅ Session token successfully stored inside Firestore state documents.")
            return
            
    print("❌ Token initialization workflow failed.")

def get_cached_kotak_token() -> str:
    """Retrieves active session key directly from Firestore tracking blocks."""
    db = firestore.Client()
    doc_snapshot = db.collection("auth_tokens").document("kotak_neo").get()
    if doc_snapshot.exists:
        return doc_snapshot.to_dict().get("data", "")
    return ""


def square_off_strategy_positions(underlying):
    client = get_client()
    try:
        # Fetch all day and net positions
        positions = client.positions()['data']

        for pos in positions:
            if underlying.upper() not in pos.get("sym", "").upper():
                continue  # Skip positions that don't match the underlying filter

            quantity = pos.get("flBuyQty", 0)

            print(f"Preparing to square off position: {pos['trdSym']} | Quantity: {quantity}")
            
            # Skip if the position is already squared off (quantity is 0)
            if int(quantity) == 0:
                continue

            # Determine the opposite transaction type to close out
            if int(quantity) > 0:
                transaction_type = "S"
                action_qty = quantity
            else:
                transaction_type = "B"
                action_qty = abs(quantity)

            print( pos)

            # Place the counter order to square off
            order_id = client.place_order(
                product=pos["prod"],  # Must match the original product (e.g., MIS, NRML, CNC)
                exchange_segment=pos['exSeg'],
                order_type="MKT",  # Market order ensures instant exit
                trading_symbol=pos["trdSym"],
                validity="DAY",
                price="0",  # Price is ignored for market orders
                transaction_type=transaction_type,
                quantity=action_qty,
                market_protection="1"
            )
            print(f"Squared off {pos['tradingsymbol']} | Order ID: {order_id}")

    except Exception as e:
        print(f"Error executing square off: {e}")


def calculate_trading_symbol(underlying, strike, right):

    expiry_date_v2, is_last_in_month = get_next_expiry_date_v2(date.today().strftime("%Y-%m-%d"), underlying)

    
    date_format = "%d%b%y" if not is_last_in_month else "%y%b"
    expiry_dt = pd.to_datetime(expiry_date_v2).strftime(date_format).upper()
    

    trading_symbol = f"{underlying}{expiry_dt}{strike}{right.upper()}"
    return trading_symbol

import pandas as pd




if __name__ == "__main__":
    pass