# Exchange connection management
"""API connector for Elysium Trading Platform"""

import os
import json
import logging
import requests
from typing import Dict, List, Any, Optional, Union
from requests.exceptions import RequestException, Timeout

from api.constants import BASE_API_URL, ENDPOINTS

class ApiConnector:
    """Handles connections to the Elysium API"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_url = BASE_API_URL
        self.session = requests.Session()
        self.connected = False
        self.is_testnet = False
        self.wallet_address = None
        
    def connect(self, wallet_address: str, secret_key: str, use_testnet: bool = False) -> bool:
        """
        Connect to Elysium API
        
        Args:
            wallet_address: Wallet address for authentication
            secret_key: Secret key for authentication 
            use_testnet: Whether to use testnet (default is mainnet)
            
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            endpoint = self.base_url + ENDPOINTS["connect"]
            
            data = {
                "wallet_address": wallet_address,
                "secret_key": secret_key,
                "use_testnet": use_testnet
            }
            
            self.logger.info(f"Connecting to Elysium API {'(testnet)' if use_testnet else '(mainnet)'}")
            response = self.session.post(endpoint, json=data, timeout=30)
            
            if response.status_code == 200:
                self.connected = True
                self.is_testnet = use_testnet
                self.wallet_address = wallet_address
                self.logger.info("Successfully connected to Elysium API")
                return True
            else:
                self.logger.error(f"Connection failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error connecting to API: {str(e)}")
            return False
    
    def _api_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict[str, Any]:
        """
        Send a request to the API with proper error handling
        
        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            params: Query parameters 
            data: Request body data
            
        Returns:
            Response data dictionary
        """
        if not self.connected:
            return {"status": "error", "message": "Not connected to API. Use connect first."}
            
        try:
            url = self.base_url + endpoint
            
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=30)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, timeout=30)
            else:
                return {"status": "error", "message": f"Unsupported HTTP method: {method}"}
                
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"API request failed: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                return {"status": "error", "message": error_msg}
                
        except Timeout:
            error_msg = "API request timed out"
            self.logger.error(error_msg)
            return {"status": "error", "message": error_msg}
            
        except RequestException as e:
            error_msg = f"Request error: {str(e)}"
            self.logger.error(error_msg)
            return {"status": "error", "message": error_msg}
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def get_balances(self) -> Dict[str, Any]:
        """Get all balances (spot and perpetual)"""
        return self._api_request("GET", ENDPOINTS["balances"])
    
    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all open orders, optionally filtered by symbol
        
        Args:
            symbol: Optional trading pair symbol to filter
            
        Returns:
            Dictionary with open orders data
        """
        params = None
        if symbol:
            params = {"symbol": symbol}
            
        return self._api_request("GET", ENDPOINTS["open_orders"], params=params)
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions
        
        Returns:
            List of positions
        """
        # There's no specific positions endpoint in the API URLs list, 
        # so we'll extract position info from the balances endpoint
        balances = self.get_balances()
        if balances.get("status") == "error":
            return []
            
        positions = balances.get("positions", [])
        if not positions:
            self.logger.warning("No positions found in API response")
            return []
            
        return positions
    
    # Market operations - Spot
    def market_buy(self, symbol: str, size: float, slippage: float = 0.03) -> Dict[str, Any]:
        """Execute a market buy order"""
        data = {
            "symbol": symbol,
            "size": size,
            "slippage": slippage
        }
        return self._api_request("POST", ENDPOINTS["market_buy"], data=data)
    
    def market_sell(self, symbol: str, size: float, slippage: float = 0.03) -> Dict[str, Any]:
        """Execute a market sell order"""
        data = {
            "symbol": symbol,
            "size": size,
            "slippage": slippage
        }
        return self._api_request("POST", ENDPOINTS["market_sell"], data=data)
    
    def limit_buy(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """Place a limit buy order"""
        data = {
            "symbol": symbol,
            "size": size,
            "price": price
        }
        return self._api_request("POST", ENDPOINTS["limit_buy"], data=data)
    
    def limit_sell(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """Place a limit sell order"""
        data = {
            "symbol": symbol,
            "size": size,
            "price": price
        }
        return self._api_request("POST", ENDPOINTS["limit_sell"], data=data)
    
    # Market operations - Perpetual
    def perp_market_buy(self, symbol: str, size: float, 
                      leverage: int = 1, slippage: float = 0.03) -> Dict[str, Any]:
        """Execute a perpetual market buy order"""
        data = {
            "symbol": symbol,
            "size": size,
            "leverage": leverage,
            "slippage": slippage
        }
        return self._api_request("POST", ENDPOINTS["perp_market_buy"], data=data)
    
    def perp_market_sell(self, symbol: str, size: float, 
                       leverage: int = 1, slippage: float = 0.03) -> Dict[str, Any]:
        """Execute a perpetual market sell order"""
        data = {
            "symbol": symbol,
            "size": size,
            "leverage": leverage,
            "slippage": slippage
        }
        return self._api_request("POST", ENDPOINTS["perp_market_sell"], data=data)
    
    def perp_limit_buy(self, symbol: str, size: float, 
                      price: float, leverage: int = 1) -> Dict[str, Any]:
        """Place a perpetual limit buy order"""
        data = {
            "symbol": symbol,
            "size": size,
            "price": price,
            "leverage": leverage
        }
        return self._api_request("POST", ENDPOINTS["perp_limit_buy"], data=data)
    
    def perp_limit_sell(self, symbol: str, size: float, 
                       price: float, leverage: int = 1) -> Dict[str, Any]:
        """Place a perpetual limit sell order"""
        data = {
            "symbol": symbol,
            "size": size,
            "price": price,
            "leverage": leverage
        }
        return self._api_request("POST", ENDPOINTS["perp_limit_sell"], data=data)
    
    def close_position(self, symbol: str, slippage: float = 0.03) -> Dict[str, Any]:
        """Close an entire position for a symbol"""
        data = {
            "symbol": symbol,
            "slippage": slippage
        }
        return self._api_request("POST", ENDPOINTS["close_position"], data=data)
    
    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a symbol"""
        data = {
            "symbol": symbol,
            "leverage": leverage
        }
        return self._api_request("POST", ENDPOINTS["set_leverage"], data=data)
    
    # Order management
    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel a specific order"""
        data = {
            "symbol": symbol,
            "order_id": order_id
        }
        return self._api_request("POST", ENDPOINTS["cancel_order"], data=data)
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Cancel all open orders, optionally filtered by symbol"""
        data = {}
        if symbol:
            data["symbol"] = symbol
            
        return self._api_request("POST", ENDPOINTS["cancel_all_orders"], data=data)
    
    # Advanced orders
    def scaled_orders(self, symbol: str, is_buy: bool, total_size: float, 
                     num_orders: int, start_price: float, end_price: float, 
                     skew: float = 0, reduce_only: bool = False, 
                     check_market: bool = True) -> Dict[str, Any]:
        """Place multiple orders across a price range with an optional skew"""
        data = {
            "symbol": symbol,
            "is_buy": is_buy,
            "total_size": total_size,
            "num_orders": num_orders,
            "start_price": start_price,
            "end_price": end_price,
            "skew": skew,
            "reduce_only": reduce_only,
            "check_market": check_market
        }
        return self._api_request("POST", ENDPOINTS["scaled_orders"], data=data)
    
    def perp_scaled_orders(self, symbol: str, is_buy: bool, total_size: float, 
                          num_orders: int, start_price: float, end_price: float, 
                          leverage: int = 1, skew: float = 0, 
                          reduce_only: bool = False) -> Dict[str, Any]:
        """Place multiple perpetual orders across a price range with an optional skew"""
        data = {
            "symbol": symbol,
            "is_buy": is_buy,
            "total_size": total_size,
            "num_orders": num_orders,
            "start_price": start_price,
            "end_price": end_price,
            "leverage": leverage,
            "skew": skew,
            "reduce_only": reduce_only
        }
        return self._api_request("POST", ENDPOINTS["perp_scaled_orders"], data=data)
    
    def market_aware_scaled_buy(self, symbol: str, total_size: float, 
                               num_orders: int, price_percent: float = 3.0, 
                               skew: float = 0) -> Dict[str, Any]:
        """Place multiple buy orders across a price range with market awareness"""
        data = {
            "symbol": symbol,
            "total_size": total_size,
            "num_orders": num_orders,
            "price_percent": price_percent,
            "skew": skew
        }
        return self._api_request("POST", ENDPOINTS["market_aware_scaled_buy"], data=data)
    
    def market_aware_scaled_sell(self, symbol: str, total_size: float, 
                                num_orders: int, price_percent: float = 3.0, 
                                skew: float = 0) -> Dict[str, Any]:
        """Place multiple sell orders across a price range with market awareness"""
        data = {
            "symbol": symbol,
            "total_size": total_size,
            "num_orders": num_orders,
            "price_percent": price_percent,
            "skew": skew
        }
        return self._api_request("POST", ENDPOINTS["market_aware_scaled_sell"], data=data)