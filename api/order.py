# All order operations (simple, grid, TWAP)
"""Order handling for Elysium Trading Platform"""

import logging
from typing import Dict, List, Any, Optional, Union

class OrderHandler:
    """Handles order execution and management for Elysium Trading Platform"""
    
    def __init__(self, api_connector=None):
        """
        Initialize order handler
        
        Args:
            api_connector: The API connector to use
        """
        self.api_connector = api_connector
        self.logger = logging.getLogger(__name__)
    
    def set_api_connector(self, api_connector):
        """Set the API connector"""
        self.api_connector = api_connector
    
    def _check_connection(self) -> bool:
        """Check if we're connected to the API"""
        if not self.api_connector or not hasattr(self.api_connector, 'connected') or not self.api_connector.connected:
            self.logger.error("Not connected to API")
            return False
        return True
    
    def _process_order_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and log the result of an order execution
        
        Args:
            result: Order execution result
        
        Returns:
            Processed result
        """
        status = result.get("status", "error")
        
        if status == "ok" or status == "success":
            self.logger.info("Order executed successfully")
            # Log any additional details if available
            if "details" in result:
                self.logger.info(f"Order details: {result['details']}")
            elif "filled" in result:
                self.logger.info(f"Filled: {result['filled']}")
        else:
            self.logger.error(f"Order failed: {result.get('message', 'Unknown error')}")
        
        return result
    
    # Spot Trading Methods
    
    def market_buy(self, symbol: str, size: float, slippage: float = 0.03) -> Dict[str, Any]:
        """Execute a market buy order"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Executing market buy: {size} {symbol}")
        result = self.api_connector.market_buy(symbol, size, slippage)
        return self._process_order_result(result)
    
    def market_sell(self, symbol: str, size: float, slippage: float = 0.03) -> Dict[str, Any]:
        """Execute a market sell order"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Executing market sell: {size} {symbol}")
        result = self.api_connector.market_sell(symbol, size, slippage)
        return self._process_order_result(result)
    
    def limit_buy(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """Place a limit buy order"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Placing limit buy: {size} {symbol} @ {price}")
        result = self.api_connector.limit_buy(symbol, size, price)
        return self._process_order_result(result)
    
    def limit_sell(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """Place a limit sell order"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Placing limit sell: {size} {symbol} @ {price}")
        result = self.api_connector.limit_sell(symbol, size, price)
        return self._process_order_result(result)
    
    # Perpetual Trading Methods
    
    def perp_market_buy(self, symbol: str, size: float, leverage: int = 1, slippage: float = 0.03) -> Dict[str, Any]:
        """Execute a perpetual market buy order"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Executing perp market buy: {size} {symbol} with {leverage}x leverage")
        result = self.api_connector.perp_market_buy(symbol, size, leverage, slippage)
        return self._process_order_result(result)
    
    def perp_market_sell(self, symbol: str, size: float, leverage: int = 1, slippage: float = 0.03) -> Dict[str, Any]:
        """Execute a perpetual market sell order"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Executing perp market sell: {size} {symbol} with {leverage}x leverage")
        result = self.api_connector.perp_market_sell(symbol, size, leverage, slippage)
        return self._process_order_result(result)
    
    def perp_limit_buy(self, symbol: str, size: float, price: float, leverage: int = 1) -> Dict[str, Any]:
        """Place a perpetual limit buy order"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Placing perp limit buy: {size} {symbol} @ {price} with {leverage}x leverage")
        result = self.api_connector.perp_limit_buy(symbol, size, price, leverage)
        return self._process_order_result(result)
    
    def perp_limit_sell(self, symbol: str, size: float, price: float, leverage: int = 1) -> Dict[str, Any]:
        """Place a perpetual limit sell order"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Placing perp limit sell: {size} {symbol} @ {price} with {leverage}x leverage")
        result = self.api_connector.perp_limit_sell(symbol, size, price, leverage)
        return self._process_order_result(result)
    
    def close_position(self, symbol: str, slippage: float = 0.03) -> Dict[str, Any]:
        """Close an entire position for a symbol"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Closing position for {symbol}")
        result = self.api_connector.close_position(symbol, slippage)
        return self._process_order_result(result)
    
    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a symbol"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Setting {leverage}x leverage for {symbol}")
        result = self.api_connector.set_leverage(symbol, leverage)
        return result
    
    # Order Management Methods
    
    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel a specific order"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Cancelling order {order_id} for {symbol}")
        result = self.api_connector.cancel_order(symbol, order_id)
        return result
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Cancel all open orders, optionally filtered by symbol"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        symbol_text = f" for {symbol}" if symbol else ""
        self.logger.info(f"Cancelling all orders{symbol_text}")
        result = self.api_connector.cancel_all_orders(symbol)
        return result
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open orders, optionally filtered by symbol"""
        if not self._check_connection():
            return []
        
        result = self.api_connector.get_open_orders(symbol)
        if result.get("status") == "error":
            self.logger.error(f"Error getting open orders: {result.get('message')}")
            return []
            
        return result.get("data", [])
    
    # Advanced Order Methods
    
    def scaled_orders(self, symbol: str, is_buy: bool, total_size: float, num_orders: int,
                     start_price: float, end_price: float, skew: float = 0,
                     reduce_only: bool = False, check_market: bool = True) -> Dict[str, Any]:
        """Place multiple orders across a price range with an optional skew"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Placing {num_orders} {'buy' if is_buy else 'sell'} orders for {symbol}")
        result = self.api_connector.scaled_orders(
            symbol, is_buy, total_size, num_orders, 
            start_price, end_price, skew, 
            reduce_only, check_market
        )
        return self._process_order_result(result)
    
    def perp_scaled_orders(self, symbol: str, is_buy: bool, total_size: float, num_orders: int,
                          start_price: float, end_price: float, leverage: int = 1, skew: float = 0,
                          reduce_only: bool = False) -> Dict[str, Any]:
        """Place multiple perpetual orders across a price range with an optional skew"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Placing {num_orders} {'buy' if is_buy else 'sell'} perp orders for {symbol}")
        result = self.api_connector.perp_scaled_orders(
            symbol, is_buy, total_size, num_orders, 
            start_price, end_price, leverage, skew, 
            reduce_only
        )
        return self._process_order_result(result)
    
    def market_aware_scaled_buy(self, symbol: str, total_size: float, num_orders: int, 
                               price_percent: float = 3.0, skew: float = 0) -> Dict[str, Any]:
        """Place multiple buy orders across a price range with market awareness"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Placing market-aware scaled buy: {total_size} {symbol} with {num_orders} orders")
        result = self.api_connector.market_aware_scaled_buy(
            symbol, total_size, num_orders, price_percent, skew
        )
        return self._process_order_result(result)
    
    def market_aware_scaled_sell(self, symbol: str, total_size: float, num_orders: int, 
                                price_percent: float = 3.0, skew: float = 0) -> Dict[str, Any]:
        """Place multiple sell orders across a price range with market awareness"""
        if not self._check_connection():
            return {"status": "error", "message": "Not connected to API"}
        
        self.logger.info(f"Placing market-aware scaled sell: {total_size} {symbol} with {num_orders} orders")
        result = self.api_connector.market_aware_scaled_sell(
            symbol, total_size, num_orders, price_percent, skew
        )
        return self._process_order_result(result)