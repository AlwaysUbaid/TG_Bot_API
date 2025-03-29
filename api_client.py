import aiohttp
import logging
import json
import time
import asyncio
from typing import Dict, Any, Optional

from config import API_BASE_URL, API_ENDPOINTS

logger = logging.getLogger(__name__)

class ElysiumAPIClient:
    def __init__(self):
        self.session = None
        self.base_url = None
        self.credentials = None
        self.is_connected = False
        self.network = None
        self._session_create_time = None
        
    async def initialize(self):
        """Initialize HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            )
        
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def connect(self, wallet_address: str, secret_key: str, network: str) -> Dict[str, Any]:
        await self.initialize()
        
        self.network = network
        self.base_url = API_BASE_URL

        self.credentials = {
            "wallet_address": wallet_address,
            "secret_key": secret_key
        }
        
        payload = {
            "network": network,
            "credentials": {
                "wallet_address": wallet_address,
                "secret_key": secret_key
            }
        }
        
        try:
            logger.info(f"Attempting to connect to {network}")
            response = await self._make_request("POST", API_ENDPOINTS['connect'], payload)
            logger.info(f"Connection response: {response}")
        
            # Fix the response checking to handle both formats
            if response and (response.get('success', False) or response.get('status') == 'success'):
                self.is_connected = True
                self._session_create_time = time.time()
                logger.info(f"Connection successful, session created at {self._session_create_time}")
                return {"success": True, "message": response.get('message', f'Connected to {network}')}
            
            logger.error(f"Connection failed: {response}")
            return {"success": False, "message": response.get('message', 'Failed to connect')}
        
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            return {"success": False, "message": f"Connection error: {str(e)}"}
    
    async def get_balances(self) -> Dict[str, Any]:
        """Get account balances"""
        return await self._make_request("GET", API_ENDPOINTS['balances'])
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get open orders, optionally filtered by symbol"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._make_request("GET", API_ENDPOINTS['open_orders'], params=params)
    
    async def spot_market_buy(self, symbol: str, size: float, slippage: float = 0.05) -> Dict[str, Any]:
        """Execute a spot market buy order"""
        payload = {
            "symbol": symbol,
            "size": size,
            "slippage": slippage
        }
        return await self._make_request("POST", API_ENDPOINTS['spot_market_buy'], payload)
    
    async def spot_market_sell(self, symbol: str, size: float, slippage: float = 0.05) -> Dict[str, Any]:
        """Execute a spot market sell order"""
        payload = {
            "symbol": symbol,
            "size": size,
            "slippage": slippage
        }
        return await self._make_request("POST", API_ENDPOINTS['spot_market_sell'], payload)
    
    async def spot_limit_buy(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """Place a spot limit buy order"""
        payload = {
            "symbol": symbol,
            "size": size,
            "price": price
        }
        return await self._make_request("POST", API_ENDPOINTS['spot_limit_buy'], payload)
    
    async def spot_limit_sell(self, symbol: str, size: float, price: float) -> Dict[str, Any]:
        """Place a spot limit sell order"""
        payload = {
            "symbol": symbol,
            "size": size,
            "price": price
        }
        return await self._make_request("POST", API_ENDPOINTS['spot_limit_sell'], payload)
    
    async def perp_market_buy(self, symbol: str, size: float, leverage: int = 1, slippage: float = 0.05) -> Dict[str, Any]:
        """Execute a perpetual market buy order"""
        payload = {
            "symbol": symbol,
            "size": size,
            "leverage": leverage,
            "slippage": slippage
        }
        return await self._make_request("POST", API_ENDPOINTS['perp_market_buy'], payload)
    
    async def perp_market_sell(self, symbol: str, size: float, leverage: int = 1, slippage: float = 0.05) -> Dict[str, Any]:
        """Execute a perpetual market sell order"""
        payload = {
            "symbol": symbol,
            "size": size,
            "leverage": leverage,
            "slippage": slippage
        }
        return await self._make_request("POST", API_ENDPOINTS['perp_market_sell'], payload)
    
    async def perp_limit_buy(self, symbol: str, size: float, price: float, leverage: int = 1) -> Dict[str, Any]:
        """Place a perpetual limit buy order"""
        payload = {
            "symbol": symbol,
            "size": size,
            "price": price,
            "leverage": leverage
        }
        return await self._make_request("POST", API_ENDPOINTS['perp_limit_buy'], payload)
    
    async def perp_limit_sell(self, symbol: str, size: float, price: float, leverage: int = 1) -> Dict[str, Any]:
        """Place a perpetual limit sell order"""
        payload = {
            "symbol": symbol,
            "size": size,
            "price": price,
            "leverage": leverage
        }
        return await self._make_request("POST", API_ENDPOINTS['perp_limit_sell'], payload)
    
    async def perp_close_position(self, symbol: str, slippage: float = 0.05) -> Dict[str, Any]:
        """Close an entire position for a symbol"""
        payload = {
            "symbol": symbol,
            "slippage": slippage
        }
        return await self._make_request("POST", API_ENDPOINTS['perp_close_position'], payload)
    
    async def perp_set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a symbol"""
        payload = {
            "symbol": symbol,
            "leverage": leverage
        }
        return await self._make_request("POST", API_ENDPOINTS['perp_set_leverage'], payload)
    
    async def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel a specific order"""
        payload = {
            "symbol": symbol,
            "order_id": order_id
        }
        return await self._make_request("POST", API_ENDPOINTS['spot_cancel_order'], payload)
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Cancel all open orders, optionally filtered by symbol"""
        payload = {}
        if symbol:
            payload["symbol"] = symbol
        return await self._make_request("POST", API_ENDPOINTS['spot_cancel_all'], payload)
    
    async def _make_request(
        self, method: str, endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the API with retry mechanism"""
        if not self.is_connected and endpoint != API_ENDPOINTS['connect']:
            return {"success": False, "message": "Not connected to the exchange"}
        
        url = f"{self.base_url}{endpoint}"
        
        # Check if session is expired (except for connect endpoint)
        if (self._session_create_time and 
            time.time() - self._session_create_time > 3600 and 
            endpoint != API_ENDPOINTS['connect']):
            self.is_connected = False
            return {"success": False, "message": "Session expired, please reconnect"}
        
        for attempt in range(3):  # Retry up to 3 times
            try:
                await self.initialize()
                
                if method == "GET":
                    async with self.session.get(url, params=params) as response:
                        result = await response.json()
                        if response.status != 200:
                            logger.error(f"API error: {response.status} - {result}")
                            if response.status == 429:  # Rate limit
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                                continue
                        return result
                else:  # POST
                    async with self.session.post(url, json=data) as response:
                        result = await response.json()
                        if response.status != 200:
                            logger.error(f"API error: {response.status} - {result}")
                            if response.status == 429:  # Rate limit
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                                continue
                        return result
                        
            except aiohttp.ClientError as e:
                logger.error(f"Request error (attempt {attempt+1}/3): {str(e)}")
                await asyncio.sleep(1)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response from API (attempt {attempt+1}/3)")
                await asyncio.sleep(1)
                
        return {"success": False, "message": "Failed after multiple attempts"}
    
    def clear_credentials(self):
        """Clear stored credentials"""
        self.credentials = None
        self.is_connected = False
        self._session_create_time = None