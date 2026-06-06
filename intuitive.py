
import breeze_utils as bu
import kite_utils as ku
import pandas as pd
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import os
import dotenv
import requests

dotenv.load_dotenv()


IST = ZoneInfo("Asia/Kolkata")

# Big candle size thresholds (configurable via .env)
BIG_CANDLE_MIN = float(os.getenv("BIG_CANDLE_MIN", "12"))
BIG_CANDLE_MAX = float(os.getenv("BIG_CANDLE_MAX", "30"))

TELEGRAM_PROVIDER = os.getenv("TELEGRAM_URL")


import requests
from urllib.parse import quote
import os

def send_telegram_message(message: str, parse_mode: str = None):
    """
    Send message to Telegram with proper encoding and better handling.
    """
    bot_token = os.getenv("TELEGRAM_FROM")      # Usually your bot token
    chat_id = os.getenv("TELEGRAM_TO")
    
    if not bot_token or not chat_id:
        print("Error: TELEGRAM_FROM or TELEGRAM_TO environment variable not set.")
        return False

    base_url = f"{TELEGRAM_PROVIDER}{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True
    }
    
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = requests.get(base_url, params=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get("ok"):
            return True
        else:
            print(f"Telegram API Error: {result}")
            return False
            
    except requests.RequestException as err:
        print(f"Error sending Telegram message: {err}")
        print(f"Message was: {message[:200]}...")  # Truncated for log
        return False

def get_nifty_quote():
    """Get current NIFTY spot price"""
    payload = {
        "stock_code": "NIFTY",
        "exchange_code": "NSE",
        "product_type": "cash"
    }
    try:
        data = bu.get_prices(payload, type='quote')
        if data and len(data) > 0:
            return float(data[0]["ltp"])
    except Exception as e:
        print(f"Error fetching NIFTY quote: {e}")
    return None

def get_nifty_history():
    """Fetch recent 15min candles to detect big candle pattern"""
    now = datetime.now()
    # make from date to 09:00 and the todate to 15:15
    from_date = now.replace(hour=9, minute=0, second=0, microsecond=0).isoformat(timespec='seconds')
    to_date = now.replace(hour=15, minute=15, second=0, microsecond=0).isoformat(timespec='seconds')

    payload = {
        "interval": "5minute",
        "stock_code": "NIFTY",
        "exchange_code": "NSE",
        "product_type": "cash",
        "from_date": from_date,
        "to_date": to_date
    }

    
    try:
        data = bu.get_prices(payload, type='historical')
        if data:
            df = pd.DataFrame(data)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)

            # Define proper aggregation rules for financial data
            agg_dict = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum',
                'exchange_code': 'first',      # constant
                'stock_code': 'first'          # constant
            }

            df = df[df.index.time != pd.to_datetime("09:00:00").time()]
            # Resample to 15 minutes
            df_15min = df.resample('15min', origin='09:15:00', ).agg(agg_dict)
            df_15min.dropna(inplace=True, how='any')  # Drop any rows with NaN values resulting from resampling

            # Optional: Reset index if you want datetime as a column again
            df_15min = df_15min.reset_index()
            return df_15min
    except Exception as e:
        print(f"Error fetching 15min history: {e}")
    return pd.DataFrame()

def calculate_atm(current_price):
    if current_price is None:
        return None
    return round(current_price / 50) * 50



def get_strategy_positions():
    """Get current NIFTY options positions"""
    positions = ku.get_strategy_positions('NIFTY')
    return positions if positions else []

def square_off_all_positions():
    """Square off all strategy positions"""
    ku.square_off_strategy_positions()

def place_long_option_order(payload):
    """Place long call or put order"""

    return ku.place_order(payload)
    


def main_live():
    kite_client = ku.get_kite_client()
    now_ist = datetime.now(IST)
    current_time = now_ist.time()
    today_str = now_ist.strftime("%Y-%m-%d")
    df = get_nifty_history()


    print(f"\n=== Intuitive Big Candle Strategy Check @ {now_ist} ===")

    # Get current positions
    positions = get_strategy_positions()
    active_position = None
    if positions:
        # Take the first one (assuming only one active at a time)
        active_position = positions[0]

    entry_cutoff = time(15, 00)
    exit_cutoff = time(15, 15)

    # ====================== 1. MANAGE ACTIVE POSITION ======================

    if active_position:

        current_premium = active_position.get("last_price")  # Get current premium from the position data
        if current_premium is None:
            print("Could not fetch current premium. Skipping management.")
            return

        entry_price = float(active_position.get("buy_price", 0))  # or track entry price separately


        # Target 10%
        if entry_price > 0 and (current_premium - entry_price) / entry_price >= 0.10:
            send_telegram_message(f"EXIT (TARGET 10%) | P&L: {current_premium-entry_price:.2f}")
            square_off_all_positions()
            return

        # Stop Loss based on ref levels. first we need to retrieve the candle reference data we stored during entry. This will have the big candle's high/low and the stop loss signal (above/below). Based on that we can decide if stop loss is hit.
        candle_reference_data = ku.retrieve_candle_reference_data()
        if candle_reference_data:
            stop_loss_signal = candle_reference_data.get("stop_loss_signal")
            # compare with nifty's current spot price from the df. 
            current_candle = df.iloc[-1]  # Get the latest candle for current spot price
            current_spot = current_candle['close']
            big_candle_high = candle_reference_data.get("high")
            big_candle_low = candle_reference_data.get("low")
            # If the signal is 'below' and spot goes below the big candle's low, we exit. If the signal is 'above' and spot goes above the big candle's high, we exit.
            if stop_loss_signal == "below" and current_spot < big_candle_low:
                send_telegram_message(f"EXIT (STOP LOSS) | P&L: {current_premium-entry_price:.2f}")
                square_off_all_positions()
                return
            elif stop_loss_signal == "above" and current_spot > big_candle_high:
                send_telegram_message(f"EXIT (STOP LOSS) | P&L: {current_premium-entry_price:.2f}")
                square_off_all_positions()
                return
            


        # EOD Exit
        if current_time >= exit_cutoff:
            send_telegram_message(f"EXIT (EOD) @ {current_time} | P&L: {current_premium-entry_price:.2f}")
            square_off_all_positions()
            return

        print(f"Holding the position. {active_position.get('tradingsymbol', 'Unknown')}: {current_premium:.2f}")
        return

    # ====================== 2. ENTRY LOGIC (No Position) ======================
    if current_time >= entry_cutoff:
        print("After entry cutoff. No new entries.")
        return



    # Fetch recent candles to detect big candle on the PREVIOUS completed candle
    if len(df) < 2:
        print("Not enough candle data.")
        return

    # Last completed candle (previous one)
    prev_candle = df.iloc[-1]  
    body_size = abs(float(prev_candle['close']) - float(prev_candle['open']))

    if BIG_CANDLE_MIN <= body_size <= BIG_CANDLE_MAX:
        is_green = float(prev_candle['close']) > float(prev_candle['open'])
        right = "CE" if is_green else "PE"
        
        current_spot = get_nifty_quote()
        if not current_spot:
            print("Could not get spot price.")
            return

        atm_strike = calculate_atm(current_spot)
        payload = {
            "underlying": "NIFTY",
            "transaction_type": kite_client.TRANSACTION_TYPE_BUY,
            "strike_price": atm_strike,
            "right": right,
            "quantity": 1,  # This will be multiplied by lot size in the order function
        }

        success = place_long_option_order(payload)

        if success:
            # We need to create candle_data for reference. This will be used for stop loss calculation later. We can store the high/low of the big candle as reference levels. Stop loss signal like 'above' or 'below' can also be stored based on the candle direction.
            candle_data = {
                "date": today_str,
                "open": float(prev_candle['open']),
                "high": float(prev_candle['high']),
                "low": float(prev_candle['low']),
                "close": float(prev_candle['close']),
                "body_size": body_size,
                "candle_color": "green" if is_green else "red",
                "stop_loss_signal": "below" if is_green else "above",
                "expireAt": (datetime.now() + timedelta(hours=7)).isoformat() # special field for auto deletion after 7 hours from now                
            }
            ku.store_candle_reference_data(candle_data)
            send_telegram_message(f"Big Candle detected!  {right.upper()} order placed. Spot: {current_spot}, ATM Strike: {atm_strike}")
    else:
        print(f"No big candle. Body size: {body_size:.2f} (thresholds: {BIG_CANDLE_MIN}-{BIG_CANDLE_MAX})")

if __name__ == "__main__":
    main_live()