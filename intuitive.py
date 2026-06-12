
import breeze_utils as bu
import kite_utils as ku
import strategy_config
import pandas as pd
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import os
import dotenv
import requests
from fastapi import FastAPI, BackgroundTasks, status
import uvicorn

dotenv.load_dotenv()


IST = ZoneInfo("Asia/Kolkata")

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

def get_quote(underlying: str):
    """Get current spot price for the underlying"""
    cfg = strategy_config.get_config(underlying)
    payload = {
        "stock_code": cfg["stock_code"],
        "exchange_code": cfg["exchange_code"],
        "product_type": cfg["product_type"]
    }
    print(f"Fetching current quote for {underlying} with payload: {payload}")
    try:
        data = bu.get_prices(payload, type='quote')
        print(f"Quote response for {underlying}: {data}")
        if data and len(data) > 0:
            # filter based on the exchange code
            return [filtered for filtered in data if filtered.get("exchange_code") == cfg["exchange_code"]][0].get("ltp")
    except Exception as e:
        print(f"Error fetching {underlying} quote: {e}")
    return None

def get_history(underlying: str, interval: str = "5minute"):
    """Fetch recent candles to detect big candle pattern"""
    cfg = strategy_config.get_config(underlying)
    now = datetime.now()
    # make from date to 09:00 and the todate to 15:15
    from_date = now.replace(hour=9, minute=0, second=0, microsecond=0).isoformat(timespec='seconds')
    to_date = now.replace(hour=15, minute=15, second=0, microsecond=0).isoformat(timespec='seconds')

    payload = {
        "interval": interval,
        "stock_code": cfg["stock_code"],
        "exchange_code": cfg["exchange_code"],
        "product_type": cfg["product_type"],
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
        print(f"Error fetching 15min history for {underlying}: {e}")
    return pd.DataFrame()

def calculate_atm(current_price, underlying: str):
    """Calculate At-The-Money strike based on underlying-specific rounding factor"""
    if current_price is None:
        return None
    cfg = strategy_config.get_config(underlying)
    rounding_factor = cfg["atm_rounding_factor"]
    return round(current_price / rounding_factor) * rounding_factor



def get_strategy_positions(underlying: str):
    """Get current options positions for an underlying"""
    positions = ku.get_strategy_positions(underlying)
    return positions if positions else []

def square_off_all_positions(underlying: str):
    """Square off all strategy positions for an underlying"""
    ku.square_off_strategy_positions(underlying)

def place_long_option_order(payload):
    """Place long call or put order"""
    return ku.place_order(payload)
    

    
def execute_strategy(underlying: str):
    """Execute the big candle strategy for a given underlying"""
    cfg = strategy_config.get_config(underlying)
    kite_client = ku.get_kite_client()
    now_ist = datetime.now(IST)
    current_time = now_ist.time()
    today_str = now_ist.strftime("%Y-%m-%d")
    df = get_history(underlying)

    print(f"\n=== {underlying} Big Candle Strategy Check @ {now_ist} ===")

    # Get current positions
    positions = get_strategy_positions(underlying)
    active_position = None
    if positions:
        # Take the first one (assuming only one active at a time)
        active_position = positions[0]

    entry_cutoff = cfg["entry_cutoff"]
    exit_cutoff = cfg["exit_cutoff"]

    # ====================== 1. MANAGE ACTIVE POSITION ======================

    if active_position:

        current_premium = active_position.get("last_price")  # Get current premium from the position data
        if current_premium is None:
            print(f"{underlying}: Could not fetch current premium. Skipping management.")
            return

        entry_price = float(active_position.get("buy_price", 0))  # or track entry price separately

        # Target 10%
        if entry_price > 0 and (current_premium - entry_price) / entry_price >= 0.10:
            send_telegram_message(f"{underlying}: EXIT (TARGET 10%) | P&L: {current_premium-entry_price:.2f}")
            square_off_all_positions(underlying)
            return

        # Stop Loss based on ref levels. first we need to retrieve the candle reference data we stored during entry. This will have the big candle's high/low and the stop loss signal (above/below). Based on that we can decide if stop loss is hit.
        candle_reference_data = ku.retrieve_candle_reference_data(underlying)
        if candle_reference_data:
            stop_loss_signal = candle_reference_data.get("stop_loss_signal")
            # compare with underlying's current spot price from the df. 
            current_candle = df.iloc[-1]  # Get the latest candle for current spot price
            current_spot = current_candle['close']
            big_candle_high = candle_reference_data.get("high")
            big_candle_low = candle_reference_data.get("low")
            # If the signal is 'below' and spot goes below the big candle's low, we exit. If the signal is 'above' and spot goes above the big candle's high, we exit.
            if stop_loss_signal == "below" and current_spot < big_candle_low:
                send_telegram_message(f"{underlying}: EXIT (STOP LOSS) | P&L: {current_premium-entry_price:.2f}")
                square_off_all_positions(underlying)
                return
            elif stop_loss_signal == "above" and current_spot > big_candle_high:
                send_telegram_message(f"{underlying}: EXIT (STOP LOSS) | P&L: {current_premium-entry_price:.2f}")
                square_off_all_positions(underlying)
                return
            

        # EOD Exit
        if current_time >= exit_cutoff:
            send_telegram_message(f"{underlying}: EXIT (EOD) @ {current_time} | P&L: {current_premium-entry_price:.2f}")
            square_off_all_positions(underlying)
            return

        print(f"{underlying}: Holding the position. {active_position.get('tradingsymbol', 'Unknown')}: {current_premium:.2f}")
        return

    # ====================== 2. ENTRY LOGIC (No Position) ======================
    if current_time >= entry_cutoff:
        print(f"{underlying}: After entry cutoff. No new entries.")
        return

    # Fetch recent candles to detect big candle on the PREVIOUS completed candle
    if len(df) < 2:
        print(f"{underlying}: Not enough candle data.")
        return

    # Last completed candle (previous one)
    prev_candle = df.iloc[-1]  
    body_size = abs(float(prev_candle['close']) - float(prev_candle['open']))
    close_p = float(prev_candle['close'])
    
    # Calculate percentage-based thresholds
    body_size_threshold_min = close_p * strategy_config.CANDLE_SIZE_MIN_PCT / 100
    body_size_threshold_max = close_p * strategy_config.CANDLE_SIZE_MAX_PCT / 100

    if body_size_threshold_min <= body_size <= body_size_threshold_max:
        is_green = float(prev_candle['close']) > float(prev_candle['open'])
        right = "CE" if is_green else "PE"
        
        current_spot = get_quote(underlying)
        print(f"{underlying}: Current Spot: {current_spot}, Body Size: {body_size:.2f} (Green: {is_green})")
        if not current_spot:
            print(f"{underlying}: Could not get spot price.")
            return

        atm_strike = calculate_atm(current_spot, underlying)
        payload = {
            "underlying": underlying,
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
            ku.store_candle_reference_data(candle_data, underlying)
            send_telegram_message(f"{underlying}: Big Candle detected! {right.upper()} order placed. Spot: {current_spot}, ATM Strike: {atm_strike}")
    else:
        print(f"{underlying}: No big candle. Body size: {body_size:.2f} (thresholds: {body_size_threshold_min:.2f}-{body_size_threshold_max:.2f})")




# Import your existing configuration and core execution logic
# (Assuming strategy_config and execute_strategy are imported/defined above)

app = FastAPI(
    title="Nifty Straddle Execution Engine",
    description="SEBI-compliant Cloud Run Service for Options Trading"
)

def run_strategy_pipeline():
    """Background task to execute the core trading loop"""
    print("⚡ Starting live trading strategy execution...")
    try:
        for underlying in strategy_config.get_all_underlyings():
            print(f"📊 Processing underlying: {underlying}")
            execute_strategy(underlying)
        print("✅ Strategy execution loop completed successfully.")
    except Exception as e:
        print(f"❌ Error during strategy execution: {str(e)}")

@app.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
def trigger_trading_strategy(background_tasks: BackgroundTasks):
    """
    Endpoint triggered by Cloud Scheduler or local curl.
    Spins off the trading loop as a background thread to prevent HTTP timeouts.
    """
    background_tasks.add_task(run_strategy_pipeline)
    return {"status": "execution_triggered", "message": "Strategy running in background."}

@app.get("/healthz", status_code=status.HTTP_200_OK)
def health_check():
    """Liveness probe required by Cloud Run to ensure container is healthy"""
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    # Adding ws="none" forces uvicorn to skip checking for the broken websockets library
    uvicorn.run("intuitive:app", host="0.0.0.0", port=port, workers=1, ws="none")