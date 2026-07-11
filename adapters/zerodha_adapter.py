from typing import List
import kite_utils as ku  # Keeping your existing script untouched
from interfaces import BaseBroker, BrokerPosition   # Assumes interface is saved in interface.py

class ZerodhaAdapter(BaseBroker):
    
    def __init__(self):
        # Cache the client instance at initialization to prevent duplicate requests
        self.client = ku.get_kite_client()
        if not self.client:
            print("⚠️ ZerodhaAdapter Init Warning: KiteConnect client could not be created.")

    def get_name(self) -> str:
        """Returns the name of the broker."""
        return "Zerodha"

    def get_positions(self, underlying: str) -> List[BrokerPosition]:
        """Fetch raw positions from Zerodha and convert them into the clean format."""
        raw_positions = ku.get_strategy_positions(underlying)
        normalized_positions = []
        
        for pos in raw_positions:
            normalized_positions.append(
                BrokerPosition(
                    trading_symbol=pos.get("tradingsymbol", "Unknown"),
                    buy_price=float(pos.get("buy_price", 0.0)),
                    current_premium=float(pos.get("last_price", 0.0)),
                    quantity=int(pos.get("quantity", 0))
                )
            )
        return normalized_positions

    def place_long_option_order(self, underlying: str, strike_price: int, right: str, quantity: int) -> str:
        """Translates strategy inputs into Zerodha specific payload formatting."""
        if not self.client:
            print("Error: Kite client uninitialized. Order aborted.")
            return ""

        # Use your explicit internal payload structure mapped to Zerodha's SDK hooks
        payload = {
            "underlying": underlying,
            "transaction_type": self.client.TRANSACTION_TYPE_BUY,
            "strike_price": strike_price,
            "right": right,
            "quantity": quantity  # Represents multiplier factor (e.g. 1 lot)
        }
        
        order_id = ku.place_order(payload)
        return str(order_id) if order_id else ""

    def square_off_all_positions(self, underlying: str) -> None:
        """Executes the standard counter order square-off routine via kite_utils."""
        ku.square_off_strategy_positions(underlying)


