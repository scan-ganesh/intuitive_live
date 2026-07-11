
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
from interfaces import BaseBroker
from adapters.zerodha_adapter import ZerodhaAdapter
#from adapters.neo_utils import refresh_kotak_token_in_firestore

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

    
# Pass the configured abstraction instance cleanly into your strategy function
def execute_strategy(underlying: str, broker: BaseBroker):
    cfg = strategy_config.get_config(underlying)
    now_ist = datetime.now(IST)
    current_time = now_ist.time()
    today_str = now_ist.strftime("%Y-%m-%d")
    
    # Breeze remains directly anchored for historical data calculations
    df = get_history(underlying) 

    print(f"\n=== {underlying} Big Candle Strategy Check @ {now_ist} ===")

    # 1. Fetch unified data structure 
    positions = broker.get_positions(underlying)
    active_position = positions[0] if positions else None

    entry_cutoff = cfg["entry_cutoff"]
    exit_cutoff = cfg["exit_cutoff"]

    # ====================== MANAGE ACTIVE POSITION ======================
    if active_position:
        current_premium = active_position.current_premium
        entry_price = active_position.buy_price

        # Target 10%
        if entry_price > 0 and (current_premium - entry_price) / entry_price >= 0.10:
            send_telegram_message(f"{underlying}: EXIT (TARGET) | Profit: {int(current_premium-entry_price)}")
            broker.square_off_all_positions(underlying)
            return

        # Stop Loss management blocks...
        candle_reference_data = ku.retrieve_candle_reference_data(underlying)

        if candle_reference_data:
            stop_loss_signal = candle_reference_data.get("stop_loss_signal")
            current_spot = df.iloc[-1]['close']
            if (stop_loss_signal == "below" and current_spot < candle_reference_data.get("low")) or (stop_loss_signal == "above" and current_spot > candle_reference_data.get("high")):
                send_telegram_message(f"{underlying}: EXIT (STOP LOSS)| Loss: {int(current_premium-entry_price)}")
                broker.square_off_all_positions(underlying)
                return
            # ... and so on

        # EOD Exit
        if current_time >= exit_cutoff:
            send_telegram_message(f"{underlying}: EXIT (EOD)| P&L: {int(current_premium-entry_price)}")
            broker.square_off_all_positions(underlying)
            return

        print(f"{underlying}: Holding. {active_position.trading_symbol}: {current_premium:.2f}")
        return

    # ====================== ENTRY LOGIC (No Position) ======================
    if current_time >= entry_cutoff:
        return

    if len(df) < 2:
        return

    prev_candle = df.iloc[-1]
    body_size = abs(float(prev_candle['close']) - float(prev_candle['open']))
    close_p = float(prev_candle['close'])
    
    body_size_threshold_min = close_p * strategy_config.CANDLE_SIZE_MIN_PCT / 100
    body_size_threshold_max = close_p * strategy_config.CANDLE_SIZE_MAX_PCT / 100

    if body_size_threshold_min <= body_size <= body_size_threshold_max:
        is_green = float(prev_candle['close']) > float(prev_candle['open'])
        right = "CE" if is_green else "PE"
        
        current_spot = get_quote(underlying)
        if not current_spot: return

        atm_strike = calculate_atm(current_spot, underlying)

        # Lets introduce ITM instead of ATM. We need to add or subtract 100 to the atm_strike based on the candle color
        if is_green:
            itm_strike = atm_strike - 100
        else:
            itm_strike = atm_strike + 100

        # Execute using abstraction boundaries without passing broker constants
        success = broker.place_long_option_order(
            underlying=underlying,
            strike_price=itm_strike,
            right=right,
            quantity=cfg['quantity']
        )

        if success:
            candle_data = {
                "date": today_str,
                "open": float(prev_candle['open']),
                "high": float(prev_candle['high']),
                "low": float(prev_candle['low']),
                "close": float(prev_candle['close']),
                "body_size": body_size,
                "candle_color": "green" if is_green else "red",
                "stop_loss_signal": "below" if is_green else "above",
                "expireAt": (datetime.now() + timedelta(hours=7)).isoformat()                
            }
            ku.store_candle_reference_data(candle_data, underlying)
            send_telegram_message(f"{underlying}: {right} order @ {itm_strike} placed successfully.")


# Import your existing configuration and core execution logic
# (Assuming strategy_config and execute_strategy are imported/defined above)

app = FastAPI(
    title="Nifty Straddle Execution Engine",
    description="SEBI-compliant Cloud Run Service for Options Trading"
)

def run_strategy_pipeline():
    """Background task to execute the core trading loop"""
    print("⚡ Starting live trading strategy execution...")
    current_execution_broker = ZerodhaAdapter()
    try:
        for underlying in strategy_config.get_all_underlyings():
            print(f"📊 Processing {underlying} with {current_execution_broker.get_name()}")
            execute_strategy(underlying, current_execution_broker)
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

@app.get("/neo-login", status_code=status.HTTP_200_OK)
def neo_login():
    """Logs into Kotak Neo and refreshes the session token in Firestore. Useful for manual triggering or debugging."""
    #refresh_kotak_token_in_firestore()
    return {"status": "ok", "message": "Kotak Neo token refreshed in Firestore."}



@app.get("/healthz", status_code=status.HTTP_200_OK)
def health_check():
    """Liveness probe required by Cloud Run to ensure container is healthy"""
    return {"status": "healthy"}



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print("Starting the server..")
    # Adding ws="none" forces uvicorn to skip checking for the broken websockets library
    uvicorn.run("intuitive:app", host="0.0.0.0", port=port, workers=1, ws="none")
    print("🚀 FastAPI server started on port {port}")