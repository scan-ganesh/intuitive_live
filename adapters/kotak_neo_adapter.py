from typing import List
import neo_utils as nu
from interfaces import BaseBroker, BrokerPosition
import strategy_config   # Assumes interface is saved in interface.py

class KotakNeoAdapter(BaseBroker):
    
    def __init__(self):
        # Cache the client instance at initialization to prevent duplicate requests
        self.client = nu.get_client()
        if not self.client:
            print("⚠️ KotakNeoAdapter Init Warning: Neo client could not be created.")

    def get_name(self) -> str:
        """Returns the name of the broker."""
        return "Kotak Neo"

    def get_positions(self, underlying: str) -> List[BrokerPosition]:
        """Fetch raw positions from Neo and convert them into the clean format."""
        raw_positions = self.client.positions()
        print(f"Raw positions data from Neo API: {raw_positions}")  # Debug log to inspect the raw responseß
        if raw_positions['stat'].lower() != 'ok':
            print("No positions found in Neo API response.")
            return []
        
        normalized_positions = []
        
        for pos in raw_positions['data']:
            if underlying.upper() not in pos.get("trdSym", "").upper() or int(pos.get("qty", 0)) == 0:
                continue  # Skip positions that don't match the underlying filter or have zero quantity

            normalized_positions.append(
                BrokerPosition(
                    trading_symbol=pos.get("trdSym", "Unknown"),
                    buy_price=float(pos.get("buyAmt", 0.0)),
                    current_premium=float(pos.get("prc", 0.0)),
                    quantity=int(pos.get("qty", 0))
                )
            )
        return normalized_positions

    def place_long_option_order(self, underlying: str, strike_price: int, right: str, quantity: int) -> str:
        """Translates strategy inputs into Neo specific payload formatting."""
        if not self.client:
            print("Error: Neo client uninitialized. Order aborted.")
            return ""

        # Use your explicit internal payload structure mapped to Neo's SDK hooks
        payload = {
            "exchange_segment": strategy_config.get_config(underlying)["neo_exchange_segment"],
            "product": "NRML",  # Assuming normal product type for options,
            "order_type": "MKT",  # Market order for immediate execution
            "underlying": underlying,
            "transaction_type": "B",  # 'B' for Buy
            "market_protection": 1,  # No price protection for market orders
            "strike_price": strike_price,
            "right": right,
            "quantity": quantity  # Represents multiplier factor (e.g. 1 lot)
        }
        
        order_id = nu.place_order(payload)
        return str(order_id) if order_id else ""

    def square_off_all_positions(self, underlying: str) -> None:
        """Executes the standard counter order square-off routine via neo_utils."""
        nu.square_off_strategy_positions(underlying)