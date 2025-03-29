from typing import Dict, Any, List
import logging

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