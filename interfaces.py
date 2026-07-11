from abc import ABC, abstractmethod
from typing import List


from dataclasses import dataclass

@dataclass
class BrokerPosition:
    trading_symbol: str   # Clean symbol string (e.g., "NIFTY2661823500CE")
    buy_price: float      # Average incoming entry price
    current_premium: float # Last Traded Price (LTP) of the option contract
    quantity: int         # Total net current open quantity

class BaseBroker(ABC):

    @abstractmethod
    def get_name(self) -> str:
        """
        Returns the name of the broker.
        """
        pass
    
    @abstractmethod
    def get_positions(self, underlying: str) -> List[BrokerPosition]:
        """
        Fetch open positions from the broker and map them into 
        standardized BrokerPosition models filtered by the underlying symbol.
        """
        pass

    @abstractmethod
    def place_long_option_order(self, underlying: str, strike_price: int, right: str, quantity: int) -> str:
        """
        Build and place an option buy order.
        Returns the unique Order ID string from the broker platform.
        """
        pass

    @abstractmethod
    def square_off_all_positions(self, underlying: str) -> None:
        """
        Find and gracefully close all active strategy positions for a given underlying.
        """
        pass

    @abstractmethod
    def quantity_to_trade(self) -> int:
        """
        Returns the quantity to trade for the strategy.
        This can be a fixed value or derived from available funds and risk management rules.
        """
        pass