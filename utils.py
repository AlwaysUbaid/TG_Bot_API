import asyncio
import time
import logging
import uuid
from typing import Dict, Any, Optional, List


logger = logging.getLogger(__name__)

def format_balances(balance_data: Dict[str, Any]) -> str:
    """Format balance data for display in Telegram message"""
    try:
        spot_balances = balance_data.get('spot', [])
        perp_balance = balance_data.get('perp', {})
        
        # Format spot balances
        spot_msg = "📊 *Spot Balances*:\n"
        
        # Filter out zero balances
        non_zero_spot = [b for b in spot_balances if b.get('total', 0) > 0]
        
        if non_zero_spot:
            for balance in non_zero_spot:
                asset = balance.get('asset', 'Unknown')
                available = balance.get('available', 0)
                total = balance.get('total', 0)
                in_orders = balance.get('in_orders', 0)
                
                spot_msg += f"• {asset}: {total:.8f} (Available: {available:.8f}, In Orders: {in_orders:.8f})\n"
        else:
            spot_msg += "No spot balances found.\n"
        
        # Format perpetual balances
        perp_msg = "\n📈 *Perpetual Balance*:\n"
        if perp_balance:
            account_value = perp_balance.get('account_value', 0)
            margin_used = perp_balance.get('margin_used', 0)
            position_value = perp_balance.get('position_value', 0)
            
            perp_msg += f"• Account Value: {account_value:.8f}\n"
            perp_msg += f"• Margin Used: {margin_used:.8f}\n"
            perp_msg += f"• Position Value: {position_value:.8f}\n"
        else:
            perp_msg += "No perpetual balance information found.\n"
            
        return spot_msg + perp_msg
        
    except Exception as e:
        logger.error(f"Error formatting balances: {str(e)}")
        return "Error formatting balance data. Please try again."

def format_orders(orders_data: Dict[str, Any]) -> str:
    """Format open orders data for display in Telegram message"""
    try:
        orders = orders_data.get('orders', [])
        
        if not orders:
            return "No open orders found."
        
        result = "📋 *Open Orders*:\n\n"
        
        for i, order in enumerate(orders, 1):
            symbol = order.get('symbol', 'Unknown')
            order_id = order.get('order_id', 'Unknown')
            side = order.get('side', 'Unknown')
            order_type = order.get('order_type', 'Unknown')
            price = order.get('price', 'Market')
            quantity = order.get('quantity', 0)
            filled = order.get('filled', 0)
            remaining = order.get('remaining', 0)
            status = order.get('status', 'Unknown')
            
            result += f"*Order #{i} (ID: {order_id})*\n"
            result += f"• Symbol: {symbol}\n"
            result += f"• Type: {side.upper()} {order_type.upper()}\n"
            result += f"• Price: {price}\n"
            result += f"• Quantity: {quantity} (Filled: {filled}, Remaining: {remaining})\n"
            result += f"• Status: {status.upper()}\n\n"
            
        return result
        
    except Exception as e:
        logger.error(f"Error formatting orders: {str(e)}")
        return "Error formatting order data. Please try again."

def format_order_result(order_result: Dict[str, Any]) -> str:
    """Format order execution result for display in Telegram message"""
    try:
        success = order_result.get('success', False)
        message = order_result.get('message', 'No message provided')
        data = order_result.get('data', {})
        
        if success:
            result = "✅ *Order Successful*\n\n"
            result += f"• Message: {message}\n"
            
            # Add any additional data if available
            if data:
                for key, value in data.items():
                    if key != 'message' and key != 'success':
                        result += f"• {key.replace('_', ' ').title()}: {value}\n"
                        
            return result
        else:
            return f"❌ *Order Failed*\n\n• Error: {message}"
            
    except Exception as e:
        logger.error(f"Error formatting order result: {str(e)}")
        return "Error processing order result. Please check if the order was executed."

def validate_input(input_type: str, value: str) -> (bool, str):
    """Validate user input based on type"""
    try:
        if input_type == 'wallet_address':
            # Basic ETH address validation
            if not value.startswith('0x') or len(value) != 42:
                return False, "Invalid wallet address format. It should start with '0x' and be 42 characters long."
            return True, value
            
        elif input_type == 'secret_key':
            # Basic private key validation
            if (not value.startswith('0x') or len(value) != 66) and len(value) != 64:
                return False, "Invalid secret key format. Please check and try again."
            return True, value
            
        elif input_type == 'symbol':
            # Symbol validation
            if not value or '/' not in value:
                return False, "Invalid trading pair. Format should be like 'BTC/USDC'."
            return True, value.upper()
            
        elif input_type == 'amount':
            # Amount validation
            try:
                amount = float(value)
                if amount <= 0.0001 or amount > 1000:
                    return False, "Amount must be between 0.0001 and 1000."
                return True, amount
            except ValueError:
                return False, "Invalid amount. Please enter a valid number."
                
        elif input_type == 'price':
            # Price validation
            try:
                price = float(value)
                if price <= 0.0001 or price > 1000000:
                    return False, "Price must be between 0.0001 and 1000000."
                return True, price
            except ValueError:
                return False, "Invalid price. Please enter a valid number."
                
        elif input_type == 'leverage':
            # Leverage validation
            try:
                leverage = int(value)
                if leverage < 1 or leverage > 100:
                    return False, "Leverage must be between 1 and 100."
                return True, leverage
            except ValueError:
                return False, "Invalid leverage. Please enter a valid integer."
                
        elif input_type == 'slippage':
            # Slippage validation
            try:
                slippage = float(value)
                if slippage < 0 or slippage > 1:
                    return False, "Slippage must be between 0 and 1."
                return True, slippage
            except ValueError:
                return False, "Invalid slippage. Please enter a valid number between 0 and 1."
                
        return False, "Unknown input type for validation."
        
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        return False, "Error during input validation. Please try again."
    
class GridTrading:
    def __init__(self, api_client):
        self.api_client = api_client
        self.active_grids = {}  # Store active grid strategies
        self.grid_tasks = {}  # Store asyncio tasks for monitoring grids
        self.logger = logging.getLogger(__name__)
        
    async def create_grid(self, symbol: str, upper_price: float, lower_price: float, 
                         num_grids: int, total_investment: float,
                         is_perp: bool = False, leverage: int = 1, 
                         take_profit: Optional[float] = None, stop_loss: Optional[float] = None) -> Dict[str, Any]:
        """
        Create a new grid trading strategy
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDC')
            upper_price: Upper bound of the grid
            lower_price: Lower bound of the grid
            num_grids: Number of grid levels
            total_investment: Total amount to invest
            is_perp: Whether to use perpetual contracts
            leverage: Leverage for perpetual contracts
            take_profit: Optional take profit level
            stop_loss: Optional stop loss level
            
        Returns:
            Dict containing grid_id or error message
        """
        if upper_price <= lower_price:
            return {"success": False, "message": "Upper price must be greater than lower price"}
        
        if num_grids < 2:
            return {"success": False, "message": "Number of grids must be at least 2"}
            
        # Generate a unique ID for this grid
        grid_id = f"{symbol.replace('/', '_')}_{str(uuid.uuid4())[:8]}"
        
        # Calculate price levels
        price_step = (upper_price - lower_price) / (num_grids - 1)
        price_levels = [lower_price + i * price_step for i in range(num_grids)]
        
        # Calculate order size for each grid level
        size_per_grid = total_investment / num_grids
        
        # Create grid configuration
        grid_config = {
            "id": grid_id,
            "symbol": symbol,
            "upper_price": upper_price,
            "lower_price": lower_price,
            "num_grids": num_grids,
            "price_levels": price_levels,
            "investment": total_investment,
            "size_per_grid": size_per_grid,
            "is_perp": is_perp,
            "leverage": leverage,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "active": False,
            "orders": [],
            "created_at": time.time(),
            "status": "created"
        }
        
        # Store the grid
        self.active_grids[grid_id] = grid_config
        
        return {"success": True, "message": f"Grid created with ID: {grid_id}", "grid_id": grid_id}
        
    async def start_grid(self, grid_id: str) -> Dict[str, Any]:
        """Start the grid trading strategy"""
        if grid_id not in self.active_grids:
            return {"success": False, "message": "Grid not found"}
            
        grid = self.active_grids[grid_id]
        if grid["active"]:
            return {"success": False, "message": "Grid already active"}
        
        # Get current market price
        try:
            # Determine which API to use based on grid type
            if grid["is_perp"]:
                # For perpetual markets, we would use market data API
                # Since we don't have a direct API function for getting market price,
                # we'll use a small market order to get the current price
                # In a real implementation, you would use a dedicated market data API
                
                # Place a tiny order to get market price
                test_order = await self.api_client.perp_market_buy(
                    grid["symbol"], 0.001, grid["leverage"], 0.01
                )
                
                if not test_order.get("success", False):
                    return {"success": False, "message": f"Failed to get market data: {test_order.get('message', 'Unknown error')}"}
                
                # Extract current price (this is approximate, in real implementation you'd use proper market data)
                current_price = test_order.get("data", {}).get("price", 0)
                if current_price == 0:
                    return {"success": False, "message": "Failed to get current market price"}
            else:
                # For spot markets
                test_order = await self.api_client.spot_market_buy(
                    grid["symbol"], 0.001, 0.01
                )
                
                if not test_order.get("success", False):
                    return {"success": False, "message": f"Failed to get market data: {test_order.get('message', 'Unknown error')}"}
                
                # Extract current price (this is approximate, in real implementation you'd use proper market data)
                current_price = test_order.get("data", {}).get("price", 0)
                if current_price == 0:
                    return {"success": False, "message": "Failed to get current market price"}
        
        except Exception as e:
            self.logger.error(f"Error getting market price: {str(e)}")
            return {"success": False, "message": f"Error getting market price: {str(e)}"}
        
        # Place initial grid orders
        grid_orders = []
        
        # Create buy orders below current price
        for price in grid["price_levels"]:
            if price < current_price:
                # Calculate size in base currency
                size = grid["size_per_grid"] / price
                
                try:
                    if grid["is_perp"]:
                        result = await self.api_client.perp_limit_buy(
                            grid["symbol"], size, price, grid["leverage"]
                        )
                    else:
                        result = await self.api_client.spot_limit_buy(
                            grid["symbol"], size, price
                        )
                    
                    if result.get("success", False):
                        order_id = self._extract_order_id(result)
                        if order_id:
                            grid_orders.append({
                                "type": "buy",
                                "price": price,
                                "size": size,
                                "order_id": order_id,
                                "status": "open"
                            })
                    else:
                        self.logger.error(f"Failed to place buy order at {price}: {result}")
                except Exception as e:
                    self.logger.error(f"Error placing buy order: {str(e)}")
        
        # Create sell orders above current price
        for price in grid["price_levels"]:
            if price > current_price:
                # For sell orders, use base currency amount directly
                size = grid["size_per_grid"] / price
                
                try:
                    if grid["is_perp"]:
                        result = await self.api_client.perp_limit_sell(
                            grid["symbol"], size, price, grid["leverage"]
                        )
                    else:
                        result = await self.api_client.spot_limit_sell(
                            grid["symbol"], size, price
                        )
                    
                    if result.get("success", False):
                        order_id = self._extract_order_id(result)
                        if order_id:
                            grid_orders.append({
                                "type": "sell",
                                "price": price,
                                "size": size,
                                "order_id": order_id,
                                "status": "open"
                            })
                    else:
                        self.logger.error(f"Failed to place sell order at {price}: {result}")
                except Exception as e:
                    self.logger.error(f"Error placing sell order: {str(e)}")
        
        # Update grid with orders
        grid["orders"] = grid_orders
        grid["active"] = True
        grid["status"] = "active"
        grid["started_at"] = time.time()
        
        # Start a monitoring task
        monitor_task = asyncio.create_task(self._monitor_grid(grid_id))
        self.grid_tasks[grid_id] = monitor_task
        
        return {
            "success": True, 
            "message": f"Grid {grid_id} started with {len(grid_orders)} orders",
            "orders_placed": len(grid_orders)
        }
    
    def _extract_order_id(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract order ID from API response"""
        try:
            # Extract order ID from the response
            # This would need to be adjusted based on the actual API response structure
            if "data" in result:
                return result["data"].get("order_id")
            return None
        except Exception:
            return None
    
    async def _monitor_grid(self, grid_id: str) -> None:
        """Monitor and manage a grid strategy"""
        grid = self.active_grids[grid_id]
        symbol = grid["symbol"]
        
        while grid["active"]:
            try:
                # Get open orders
                if grid["is_perp"]:
                    open_orders_result = await self.api_client.get_open_orders(symbol)
                else:
                    open_orders_result = await self.api_client.get_open_orders(symbol)
                
                if not open_orders_result.get("success", False):
                    await asyncio.sleep(10)
                    continue
                
                # Extract order IDs from the response
                open_orders = open_orders_result.get("orders", [])
                open_order_ids = [order.get("order_id") for order in open_orders]
                
                # Check for filled orders
                for order in grid["orders"]:
                    if order["status"] == "open" and order["order_id"] not in open_order_ids:
                        # Order was filled
                        order["status"] = "filled"
                        order["filled_at"] = time.time()
                        
                        self.logger.info(f"Grid {grid_id}: Order filled at price {order['price']}")
                        
                        # Place opposite order at the same price level
                        opposite_type = "sell" if order["type"] == "buy" else "buy"
                        try:
                            if opposite_type == "sell":
                                if grid["is_perp"]:
                                    result = await self.api_client.perp_limit_sell(
                                        symbol, order["size"], order["price"], grid["leverage"]
                                    )
                                else:
                                    result = await self.api_client.spot_limit_sell(
                                        symbol, order["size"], order["price"]
                                    )
                            else:
                                if grid["is_perp"]:
                                    result = await self.api_client.perp_limit_buy(
                                        symbol, order["size"], order["price"], grid["leverage"]
                                    )
                                else:
                                    result = await self.api_client.spot_limit_buy(
                                        symbol, order["size"], order["price"]
                                    )
                                
                            if result.get("success", False):
                                order_id = self._extract_order_id(result)
                                if order_id:
                                    grid["orders"].append({
                                        "type": opposite_type,
                                        "price": order["price"],
                                        "size": order["size"],
                                        "order_id": order_id,
                                        "status": "open"
                                    })
                            else:
                                self.logger.error(f"Failed to place {opposite_type} order: {result}")
                        except Exception as e:
                            self.logger.error(f"Error placing opposite order: {str(e)}")
                
                # Check take profit or stop loss if configured
                if grid["take_profit"] or grid["stop_loss"]:
                    # Get current market price (simplified)
                    try:
                        # This is a simplified approach to get market price
                        # In a real implementation, you would use a proper market data API
                        if grid["is_perp"]:
                            test_order = await self.api_client.perp_market_buy(
                                grid["symbol"], 0.001, grid["leverage"], 0.01
                            )
                        else:
                            test_order = await self.api_client.spot_market_buy(
                                grid["symbol"], 0.001, 0.01
                            )
                        
                        if test_order.get("success", False):
                            current_price = test_order.get("data", {}).get("price", 0)
                            
                            if current_price > 0:
                                if grid["take_profit"] and current_price >= grid["take_profit"]:
                                    self.logger.info(f"Grid {grid_id}: Take profit triggered at {current_price}")
                                    await self.stop_grid(grid_id)
                                    break
                                    
                                if grid["stop_loss"] and current_price <= grid["stop_loss"]:
                                    self.logger.info(f"Grid {grid_id}: Stop loss triggered at {current_price}")
                                    await self.stop_grid(grid_id)
                                    break
                    except Exception as e:
                        self.logger.error(f"Error checking take profit/stop loss: {str(e)}")
                
                # Sleep before next check
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error in grid monitoring: {str(e)}")
                await asyncio.sleep(60)  # Longer delay after error
    
    async def stop_grid(self, grid_id: str) -> Dict[str, Any]:
        """Stop a grid trading strategy"""
        if grid_id not in self.active_grids:
            return {"success": False, "message": "Grid not found"}
            
        grid = self.active_grids[grid_id]
        if not grid["active"]:
            return {"success": False, "message": "Grid already stopped"}
        
        # Mark as inactive
        grid["active"] = False
        grid["status"] = "stopping"
        
        # Cancel all open orders
        symbol = grid["symbol"]
        try:
            result = await self.api_client.cancel_all_orders(symbol)
            if not result.get("success", False):
                self.logger.error(f"Error cancelling orders: {result}")
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {str(e)}")
        
        # Update grid status
        grid["status"] = "stopped"
        grid["stopped_at"] = time.time()
        
        # Cancel the monitoring task if it exists
        if grid_id in self.grid_tasks:
            try:
                self.grid_tasks[grid_id].cancel()
                del self.grid_tasks[grid_id]
            except Exception as e:
                self.logger.error(f"Error cancelling monitoring task: {str(e)}")
        
        return {"success": True, "message": f"Grid {grid_id} stopped"}
    
    def get_grid_status(self, grid_id: str) -> Dict[str, Any]:
        """Get current status of a grid"""
        if grid_id not in self.active_grids:
            return {"success": False, "message": "Grid not found"}
            
        grid = self.active_grids[grid_id]
        
        # Calculate statistics
        filled_orders = [o for o in grid["orders"] if o["status"] == "filled"]
        open_orders = [o for o in grid["orders"] if o["status"] == "open"]
        
        # Calculate profit/loss if possible
        filled_buys = [o for o in filled_orders if o["type"] == "buy"]
        filled_sells = [o for o in filled_orders if o["type"] == "sell"]
        
        # Simplified P&L calculation
        # This is just an estimate, real P&L would need to account for fees, etc.
        total_buy_volume = sum(o["size"] * o["price"] for o in filled_buys)
        total_sell_volume = sum(o["size"] * o["price"] for o in filled_sells)
        estimated_pnl = total_sell_volume - total_buy_volume
        
        return {
            "success": True,
            "id": grid_id,
            "symbol": grid["symbol"],
            "status": grid["status"],
            "active": grid["active"],
            "upper_price": grid["upper_price"],
            "lower_price": grid["lower_price"],
            "num_grids": grid["num_grids"],
            "investment": grid["investment"],
            "is_perp": grid["is_perp"],
            "leverage": grid["leverage"],
            "take_profit": grid["take_profit"],
            "stop_loss": grid["stop_loss"],
            "filled_orders": len(filled_orders),
            "open_orders": len(open_orders),
            "estimated_pnl": estimated_pnl if filled_orders else 0,
            "created_at": grid["created_at"],
            "started_at": grid.get("started_at"),
            "stopped_at": grid.get("stopped_at")
        }
    
    def list_grids(self) -> Dict[str, Any]:
        """List all grid trading strategies"""
        active = []
        inactive = []
        
        for grid_id in self.active_grids:
            status = self.get_grid_status(grid_id)
            if status.get("success", False):
                if status.get("active", False):
                    active.append(status)
                else:
                    inactive.append(status)
                    
        return {
            "success": True,
            "active": active,
            "inactive": inactive
        }
    
    async def clean_completed_grids(self) -> int:
        """Remove inactive grids from memory"""
        to_remove = []
        for grid_id, grid in self.active_grids.items():
            if not grid["active"]:
                to_remove.append(grid_id)
                
        for grid_id in to_remove:
            if grid_id in self.grid_tasks:
                try:
                    self.grid_tasks[grid_id].cancel()
                except:
                    pass
                del self.grid_tasks[grid_id]
            del self.active_grids[grid_id]
                
        return len(to_remove)
    
    async def stop_all_grids(self) -> Dict[str, Any]:
        """Stop all active grid strategies"""
        stopped = 0
        errors = []
        
        for grid_id, grid in list(self.active_grids.items()):
            if grid["active"]:
                result = await self.stop_grid(grid_id)
                if result.get("success", False):
                    stopped += 1
                else:
                    errors.append(f"Grid {grid_id}: {result.get('message', 'Unknown error')}")
                    
        return {
            "success": True,
            "message": f"Stopped {stopped} grid(s)",
            "stopped_count": stopped,
            "errors": errors
        }
    
    async def modify_grid(self, grid_id: str, take_profit: Optional[float] = None, 
                          stop_loss: Optional[float] = None) -> Dict[str, Any]:
        """Modify parameters of an existing grid"""
        if grid_id not in self.active_grids:
            return {"success": False, "message": "Grid not found"}
            
        grid = self.active_grids[grid_id]
        
        if take_profit is not None:
            grid["take_profit"] = take_profit
            
        if stop_loss is not None:
            grid["stop_loss"] = stop_loss
            
        return {
            "success": True,
            "message": f"Grid {grid_id} modified",
            "take_profit": grid["take_profit"],
            "stop_loss": grid["stop_loss"]
        }