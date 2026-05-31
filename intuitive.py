
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


def send_telegram_message(message):
    telegram = {
        "from": os.getenv("TELEGRAM_FROM"),
        "to": os.getenv("TELEGRAM_TO"),
        "message": message
    }
    telegram_url = f"{TELEGRAM_PROVIDER}{telegram['from']}/sendMessage?chat_id={telegram['to']}&text={telegram['message']}"

    try:
        response = requests.get(telegram_url)
        response.raise_for_status() 
    except requests.RequestException as err:
        print(f"Error sending the telegram message: {telegram['message']}", err)


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
    kite_client = ku.get_kite_client()
    return kite_client.place_order(payload)
    

def get_option_premium(strike, expiry_date, right, timestamp=None):
    """Get current option premium"""
    if timestamp is None:
        timestamp = datetime.now(IST)
    
    payload = {
        "interval": "5minute",
        "stock_code": "NIFTY",
        "exchange_code": "NFO",
        "product_type": "options",
        "strike_price": strike,
        "expiry_date": pd.to_datetime(expiry_date).isoformat(),
        "from_date": timestamp.isoformat(),
        "to_date": (timestamp + timedelta(minutes=5)).isoformat(),
        "right": right.lower()
    }
    try:
        data = bu.get_prices(payload, type='historical')
        if data and len(data) > 0:
            return float(data[0]["close"])
    except Exception as e:
        print(f"Error fetching option premium: {e}")
    return None

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

    entry_cutoff = time(14, 30)
    exit_cutoff = time(15, 15)

    # ====================== 1. MANAGE ACTIVE POSITION ======================

    if active_position:
        right = active_position.get("right", "").lower()
        strike = int(active_position.get("strike_price"))
        expiry = active_position.get("expiry_date")
        
        current_premium = get_option_premium(strike, expiry, right)
        if current_premium is None:
            print("Could not fetch current premium. Skipping management.")
            return

        entry_price = float(active_position.get("average_price", 0))  # or track entry price separately


        # Target 10%
        if entry_price > 0 and (current_premium - entry_price) / entry_price >= 0.10:
            print(f"EXIT (TARGET 10%) | Premium: {current_premium:.2f}")
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
                print(f"EXIT (STOP LOSS) | Premium: {current_premium:.2f} | Spot: {current_spot:.2f} below Big Candle Low: {big_candle_low:.2f}")
                square_off_all_positions()
                return
            elif stop_loss_signal == "above" and current_spot > big_candle_high:
                print(f"EXIT (STOP LOSS) | Premium: {current_premium:.2f} | Spot: {current_spot:.2f} above Big Candle High: {big_candle_high:.2f}")
                square_off_all_positions()
                return
            


        # EOD Exit
        if current_time >= exit_cutoff:
            print(f"EXIT (EOD) @ {current_time} | Premium: {current_premium:.2f}")
            square_off_all_positions()
            return

        print(f"Holding {right.upper()} position. Premium: {current_premium:.2f}")
        return

    # ====================== 2. ENTRY LOGIC (No Position) ======================
    if current_time >= entry_cutoff:
        print("After entry cutoff. No new entries.")
        #return



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
            "exchange_code": kite_client.EXCHANGE_NFO,
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