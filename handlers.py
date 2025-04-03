from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
import logging
import asyncio
from typing import Dict, Any, Optional, Union

from api_client import ElysiumAPIClient
from config import MESSAGES
from utils import format_balances, format_orders, format_order_result, validate_input, GridTrading

# Conversation states
(
    NETWORK_SELECTION, WALLET_ADDRESS, SECRET_KEY,
    SPOT_ACTION, PERP_ACTION, SCALED_ACTION,
    SYMBOL_INPUT, AMOUNT_INPUT, PRICE_INPUT, LEVERAGE_INPUT, SLIPPAGE_INPUT,
    MIN_PRICE_INPUT, MAX_PRICE_INPUT, NUM_ORDERS_INPUT, MIN_DISTANCE_INPUT, MAX_DISTANCE_INPUT,
    CONFIRM_ORDER,GRID_ACTION, GRID_SELECT, GRID_MARKET_TYPE, GRID_SYMBOL, GRID_LOWER_PRICE, 
    GRID_UPPER_PRICE, GRID_NUM_LEVELS, GRID_INVESTMENT, GRID_LEVERAGE, 
    GRID_TAKE_PROFIT, GRID_STOP_LOSS, GRID_CONFIRM, GRID_START_NOW
) = range(30)

# Action types
MARKET_BUY = 'market_buy'
MARKET_SELL = 'market_sell'
LIMIT_BUY = 'limit_buy'
LIMIT_SELL = 'limit_sell'
CLOSE_POSITION = 'close_position'
SET_LEVERAGE = 'set_leverage'
SCALED_ORDERS = 'scaled_orders'
PERP_SCALED_ORDERS = 'perp_scaled_orders'
MARKET_AWARE_SCALED_BUY = 'market_aware_scaled_buy'
MARKET_AWARE_SCALED_SELL = 'market_aware_scaled_sell'

logger = logging.getLogger(__name__)

# In-memory storage for active user sessions
user_sessions = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start command handler to initiate the bot"""
    user_id = update.effective_user.id
    
    # Clear any existing session data for this user
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    # Create new session for this user
    user_sessions[user_id] = {
        'api_client': ElysiumAPIClient(),
        'trading_data': {}
    }
    
    await update.message.reply_text(
        f"{MESSAGES['welcome']}\n\n"
        f"{MESSAGES['help']}\n\n"
        "To get started, use /connect to set up your API connection."
    )
    
    return ConversationHandler.END

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the current connection status and details"""
    user_id = update.effective_user.id
    
    # Check if user has a session
    if user_id not in user_sessions:
        await update.message.reply_text("⚠️ You haven't started a session yet. Use /start to initialize.")
        return
    
    # Check if user is connected
    api_client = user_sessions[user_id]['api_client']
    if not api_client.is_connected:
        await update.message.reply_text("❌ Not connected to any network. Use /connect to establish a connection.")
        return
    
    # Get connection details
    network = api_client.network.upper()
    wallet_address = api_client.credentials.get('wallet_address', 'Unknown')
    
    # Format wallet address to show only first 6 and last 4 characters for security
    if len(wallet_address) > 10:
        formatted_wallet = f"{wallet_address[:6]}...{wallet_address[-4:]}"
    else:
        formatted_wallet = wallet_address
    
    # Calculate connection duration
    connection_time = api_client._session_create_time
    if connection_time:
        import time
        current_time = time.time()
        duration_seconds = int(current_time - connection_time)
        hours, remainder = divmod(duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration = f"{hours}h {minutes}m {seconds}s"
    else:
        duration = "Unknown"
    
    # Create status message
    status_message = (
        f"📊 *CONNECTION STATUS*\n\n"
        f"• *Network*: {network}\n"
        f"• *Wallet*: {formatted_wallet}\n"
        f"• *Connected for*: {duration}\n"
        f"• *Session active*: Yes\n"
    )
    
    await update.message.reply_text(status_message, parse_mode='Markdown')

async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begin the connection process by asking for network selection"""
    user_id = update.effective_user.id
    
    # Ensure user has a session
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'api_client': ElysiumAPIClient(),
            'trading_data': {}
        }
    
    # Ask for network selection first
    keyboard = [
        [
            InlineKeyboardButton("Testnet", callback_data="network_testnet"),
            InlineKeyboardButton("Mainnet", callback_data="network_mainnet")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        MESSAGES['ask_network'],
        reply_markup=reply_markup
    )
    return NETWORK_SELECTION

async def network_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process network selection and ask for wallet address"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    network = query.data.split("_")[1]  # Extract network from callback data
    
    # Store network choice
    user_sessions[user_id]['trading_data']['network'] = network
    
    # Now ask for wallet address
    await query.edit_message_text(MESSAGES['ask_wallet'])
    return WALLET_ADDRESS

async def wallet_address_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process wallet address input and ask for secret key"""
    user_id = update.effective_user.id
    wallet_address = update.message.text
    
    # Validate wallet address
    is_valid, result = validate_input('wallet_address', wallet_address)
    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid wallet address:")
        return WALLET_ADDRESS
    
    # Store wallet address in user session
    user_sessions[user_id]['trading_data']['wallet_address'] = result
    
    # Ask for secret key
    await update.message.reply_text(
        f"{MESSAGES['warn_secret']}\n\n"
        f"{MESSAGES['ask_secret']}"
    )
    return SECRET_KEY

async def secret_key_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process secret key input and connect to API"""
    user_id = update.effective_user.id
    secret_key = update.message.text
    
    # Delete the message containing the secret key for security
    await update.message.delete()
    
    # Validate secret key
    is_valid, result = validate_input('secret_key', secret_key)
    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid secret key:")
        return SECRET_KEY
    
    # Store secret key in user session
    user_sessions[user_id]['trading_data']['secret_key'] = result
    
    # Get all required data
    wallet_address = user_sessions[user_id]['trading_data']['wallet_address']
    network = user_sessions[user_id]['trading_data']['network']
    
    # Update UI to show connecting message
    connecting_message = await update.message.reply_text(f"Connecting to {network}...")
    
    try:
        # Connect to API
        api_client = user_sessions[user_id]['api_client']
        result = await api_client.connect(wallet_address, secret_key, network)
        
        if result.get('success', False):
            await connecting_message.edit_text(
                f"✅ {MESSAGES['conn_success'].format(network)}"
            )
        else:
            error_msg = result.get('message', 'Unknown error')
            await connecting_message.edit_text(
                f"❌ {MESSAGES['conn_error'].format(error_msg)}"
            )
    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        await connecting_message.edit_text(
            f"❌ {MESSAGES['conn_error'].format(str(e))}"
        )
    
    return ConversationHandler.END

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get and display account balances"""
    user_id = update.effective_user.id
    
    # Check if user is connected
    if (user_id not in user_sessions or 
        not user_sessions[user_id]['api_client'].is_connected):
        await update.message.reply_text(MESSAGES['not_connected'])
        return
    
    # Send a "loading" message
    message = await update.message.reply_text("Fetching your balances...")
    
    try:
        # Get balances from API
        api_client = user_sessions[user_id]['api_client']
        balance_data = await api_client.get_balances()
        
        # Format the response
        formatted_balances = format_balances(balance_data)
        
        # Update the message with the formatted balances
        await message.edit_text(formatted_balances, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error fetching balances: {str(e)}")
        await message.edit_text(f"❌ Error fetching balances: {str(e)}")

async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get and display open orders"""
    user_id = update.effective_user.id
    
    # Check if user is connected
    if (user_id not in user_sessions or 
        not user_sessions[user_id]['api_client'].is_connected):
        await update.message.reply_text(MESSAGES['not_connected'])
        return
    
    # Send a "loading" message
    message = await update.message.reply_text("Fetching your open orders...")
    
    try:
        # Get orders from API
        api_client = user_sessions[user_id]['api_client']
        
        # Check if a symbol was provided
        symbol = None
        if context.args and len(context.args) > 0:
            symbol = context.args[0].upper()
        
        orders_data = await api_client.get_open_orders(symbol)
        
        # Format the response
        formatted_orders = format_orders(orders_data)
        
        # Update the message with the formatted orders
        await message.edit_text(formatted_orders, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error fetching orders: {str(e)}")
        await message.edit_text(f"❌ Error fetching orders: {str(e)}")

async def spot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle spot trading commands"""
    user_id = update.effective_user.id
    
    # Check if user is connected
    if (user_id not in user_sessions or 
        not user_sessions[user_id]['api_client'].is_connected):
        await update.message.reply_text(MESSAGES['not_connected'])
        return ConversationHandler.END
    
    # Clear previous trading data
    user_sessions[user_id]['trading_data'] = {
        'market': 'spot'
    }
    
    # Show spot trading options
    keyboard = [
        [
            InlineKeyboardButton("Market Buy", callback_data="spot_market_buy"),
            InlineKeyboardButton("Market Sell", callback_data="spot_market_sell")
        ],
        [
            InlineKeyboardButton("Limit Buy", callback_data="spot_limit_buy"),
            InlineKeyboardButton("Limit Sell", callback_data="spot_limit_sell")
        ],
        [
            InlineKeyboardButton("Scaled Orders", callback_data="spot_scaled_orders")
        ],
        [
            InlineKeyboardButton("Cancel", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📈 *Spot Trading*\n\nSelect a trading action:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return SPOT_ACTION

async def perp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
   """Handle perpetual trading commands"""
   user_id = update.effective_user.id
   
   # Check if user is connected
   if (user_id not in user_sessions or 
       not user_sessions[user_id]['api_client'].is_connected):
       await update.message.reply_text(MESSAGES['not_connected'])
       return ConversationHandler.END
   
   # Clear previous trading data
   user_sessions[user_id]['trading_data'] = {
       'market': 'perp'
   }
   
   # Show perpetual trading options
   keyboard = [
       [
           InlineKeyboardButton("Market Buy", callback_data="perp_market_buy"),
           InlineKeyboardButton("Market Sell", callback_data="perp_market_sell")
       ],
       [
           InlineKeyboardButton("Limit Buy", callback_data="perp_limit_buy"),
           InlineKeyboardButton("Limit Sell", callback_data="perp_limit_sell")
       ],
       [
           InlineKeyboardButton("Scaled Orders", callback_data="perp_scaled_orders")
       ],
       [
           InlineKeyboardButton("Close Position", callback_data="perp_close_position"),
           InlineKeyboardButton("Set Leverage", callback_data="perp_set_leverage")
       ],
       [
           InlineKeyboardButton("Cancel", callback_data="cancel")
       ]
   ]
   reply_markup = InlineKeyboardMarkup(keyboard)
   
   await update.message.reply_text(
       "📊 *Perpetual Trading*\n\nSelect a trading action:",
       reply_markup=reply_markup,
       parse_mode='Markdown'
   )
   return PERP_ACTION

async def scaled_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle scaled order commands"""
    user_id = update.effective_user.id
    
    # Check if user is connected
    if (user_id not in user_sessions or 
        not user_sessions[user_id]['api_client'].is_connected):
        await update.message.reply_text(MESSAGES['not_connected'])
        return ConversationHandler.END
    
    # Clear previous trading data
    user_sessions[user_id]['trading_data'] = {}
    
    # Show scaled order options
    keyboard = [
        [
            InlineKeyboardButton("Spot Scaled Orders", callback_data="spot_scaled_orders"),
            InlineKeyboardButton("Perp Scaled Orders", callback_data="perp_scaled_orders")
        ],
        [
            InlineKeyboardButton("Market-Aware Scaled Buy", callback_data="market_aware_scaled_buy"),
            InlineKeyboardButton("Market-Aware Scaled Sell", callback_data="market_aware_scaled_sell")
        ],
        [
            InlineKeyboardButton("Cancel", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 *Scaled Orders*\n\nSelect a scaling strategy:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return SCALED_ACTION

async def trading_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle trading action selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    
    if action == "cancel":
        await query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END
    
    # Handle side selection for scaled orders
    if action.startswith("side_"):
        side = action.split("_")[1]  # Extract buy or sell
        user_sessions[user_id]['trading_data']['side'] = side
        
        # Ask for amount
        await query.edit_message_text(
            f"Enter the total amount to {side.upper()} (0.0001-1000):"
        )
        return AMOUNT_INPUT
    
    # Handle market type selection for market-aware scaled orders
    if action.startswith("market_type_"):
        market_type = action.split("_")[2]  # Extract spot or perp
        user_sessions[user_id]['trading_data']['market'] = market_type
        
        if market_type == "perp":
            # For perp market, ask for leverage
            await query.edit_message_text(
                "Enter leverage (1-100, default is 1):"
            )
            return LEVERAGE_INPUT
        else:
            # For spot market, go to confirmation
            return prepare_scaled_order_confirmation(update, user_id, is_callback=True)
    
    # Parse action (format: market_action)
    action_parts = action.split('_')
    market_type = action_parts[0]  # spot or perp
    
    # Store the full action string (needed for scaled orders)
    user_sessions[user_id]['trading_data']['action'] = action
    
    # Set market type
    if market_type == 'spot' or market_type == 'perp':
        user_sessions[user_id]['trading_data']['market'] = market_type
    
    # For scaled orders detection
    if 'scaled_orders' in action:
        # Ask for symbol
        await query.edit_message_text(
            "Enter the trading pair (e.g., BTC/USDC):"
        )
        return SYMBOL_INPUT
    
    # For market-aware scaled orders
    if 'market_aware_scaled' in action:
        # Ask for symbol
        await query.edit_message_text(
            "Enter the trading pair (e.g., BTC/USDC):"
        )
        return SYMBOL_INPUT
    
    # For regular actions (market/limit orders)
    action_type = '_'.join(action_parts[1:])  # market_buy, limit_sell, etc.
    
    # Ask for symbol
    if action_type == 'close_position':
        # For close position, we only need the symbol
        await query.edit_message_text(
            "Enter the symbol of the position to close (e.g., BTC):"
        )
    elif action_type == 'set_leverage':
        # For set leverage, we need symbol and leverage
        await query.edit_message_text(
            "Enter the symbol to set leverage for (e.g., BTC):"
        )
    else:
        # For regular orders, we need trading pair
        await query.edit_message_text(
            "Enter the trading pair (e.g., BTC/USDC):"
        )
    
    return SYMBOL_INPUT

async def scaled_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle scaled order action selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    
    if action == "cancel":
        await query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END
    
    # Store action in user session
    user_sessions[user_id]['trading_data']['action'] = action
    
    # Determine market type
    if action.startswith("perp_"):
        user_sessions[user_id]['trading_data']['market'] = 'perp'
    elif action.startswith("spot_"):
        user_sessions[user_id]['trading_data']['market'] = 'spot'
    
    # Ask for trading pair
    await query.edit_message_text(
        "Enter the trading pair (e.g., BTC/USDC):"
    )
    return SYMBOL_INPUT

async def symbol_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process symbol input and move to next step based on action"""
    user_id = update.effective_user.id
    symbol = update.message.text.strip().upper()
    
    # Get the current action
    action = user_sessions[user_id]['trading_data'].get('action', '')
    market = user_sessions[user_id]['trading_data'].get('market', '')
    
    # Special handling for close_position and set_leverage
    if action == 'perp_close_position':
        # Just need to validate the symbol is not empty
        if not symbol:
            await update.message.reply_text("❌ Symbol cannot be empty. Please enter a valid symbol:")
            return SYMBOL_INPUT
        
        # Store symbol and go to confirmation
        user_sessions[user_id]['trading_data']['symbol'] = symbol
        
        await update.message.reply_text(
            f"⚠️ You are about to close your entire position for {symbol}.\n\n"
            f"Type 'confirm' to proceed or 'cancel' to abort:"
        )
        return CONFIRM_ORDER
    
    elif action == 'perp_set_leverage':
        # Just need to validate the symbol is not empty
        if not symbol:
            await update.message.reply_text("❌ Symbol cannot be empty. Please enter a valid symbol:")
            return SYMBOL_INPUT
        
        # Store symbol and ask for leverage
        user_sessions[user_id]['trading_data']['symbol'] = symbol
        
        await update.message.reply_text(
            f"Enter the leverage value (1-100) for {symbol}:"
        )
        return LEVERAGE_INPUT
    
    # For regular orders, validate trading pair format
    is_valid, result = validate_input('symbol', symbol)
    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid trading pair:")
        return SYMBOL_INPUT
    
    # Store symbol and determine next step
    user_sessions[user_id]['trading_data']['symbol'] = symbol
    
    # Handle scaled orders
    if "scaled_orders" in action:
        # For scaled orders, determine the side
        keyboard = [
            [
                InlineKeyboardButton("Buy", callback_data="side_buy"),
                InlineKeyboardButton("Sell", callback_data="side_sell")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Select order side for {symbol}:",
            reply_markup=reply_markup
        )
        return SPOT_ACTION  # Reusing SPOT_ACTION state for side selection
    
    elif "market_aware_scaled_buy" in action:
        # For market-aware buy orders, side is buy
        user_sessions[user_id]['trading_data']['side'] = 'buy'
        await update.message.reply_text(
            f"Enter the total amount to trade (0.0001-1000):"
        )
        return AMOUNT_INPUT
    
    elif "market_aware_scaled_sell" in action:
        # For market-aware sell orders, side is sell
        user_sessions[user_id]['trading_data']['side'] = 'sell'
        await update.message.reply_text(
            f"Enter the total amount to trade (0.0001-1000):"
        )
        return AMOUNT_INPUT
    
    # For regular market/limit orders, ask for amount
    action_type = action.split('_', 1)[1] if '_' in action else action  # Extract the action type part
    await update.message.reply_text(
        f"Enter the amount to {action_type.replace('_', ' ')} (0.0001-1000):"
    )
    return AMOUNT_INPUT

async def amount_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process amount input and move to next step based on action"""
    user_id = update.effective_user.id
    amount_text = update.message.text.strip()
    
    # Validate amount
    is_valid, result = validate_input('amount', amount_text)
    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid amount:")
        return AMOUNT_INPUT
    
    # Store amount
    user_sessions[user_id]['trading_data']['amount'] = result
    
    # Get current action and determine next step
    action = user_sessions[user_id]['trading_data'].get('action', '')
    
    # Handle scaled orders
    if "scaled_orders" in action:
        # For scaled orders, we need min price
        await update.message.reply_text(
            "Enter the minimum price for your scaled orders:"
        )
        return MIN_PRICE_INPUT
    
    elif "market_aware_scaled" in action:
        # For market-aware scaled orders, we need number of orders
        await update.message.reply_text(
            "Enter the number of orders to place (2-50):"
        )
        return NUM_ORDERS_INPUT
    
    elif 'limit' in action:
        # For limit orders, we need price
        await update.message.reply_text(
            "Enter the price for your limit order (0.0001-1000000):"
        )
        return PRICE_INPUT
    
    elif 'market' in action:
        # For market orders, we need slippage
        await update.message.reply_text(
            "Enter maximum slippage allowed (0-1, default is 0.05):"
        )
        return SLIPPAGE_INPUT
    
    # Shouldn't reach here, but just in case
    return ConversationHandler.END

async def min_price_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process minimum price input for scaled orders"""
    user_id = update.effective_user.id
    min_price_text = update.message.text.strip()
    
    # Validate price
    is_valid, result = validate_input('price', min_price_text)
    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid minimum price:")
        return MIN_PRICE_INPUT
    
    # Store minimum price
    user_sessions[user_id]['trading_data']['min_price'] = result
    
    # Ask for maximum price
    await update.message.reply_text(
        "Enter the maximum price for your scaled orders:"
    )
    return MAX_PRICE_INPUT

async def max_price_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process maximum price input for scaled orders"""
    user_id = update.effective_user.id
    max_price_text = update.message.text.strip()
    
    # Validate price
    is_valid, result = validate_input('price', max_price_text)
    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid maximum price:")
        return MAX_PRICE_INPUT
    
    # Get min_price for comparison
    min_price = user_sessions[user_id]['trading_data'].get('min_price', 0)
    
    # Ensure max price is greater than min price
    if result <= min_price:
        await update.message.reply_text(
            f"❌ Maximum price must be greater than minimum price ({min_price}).\n\n"
            f"Please enter a valid maximum price:"
        )
        return MAX_PRICE_INPUT
    
    # Store maximum price
    user_sessions[user_id]['trading_data']['max_price'] = result
    
    # Ask for number of orders
    await update.message.reply_text(
        "Enter the number of orders to place (2-50):"
    )
    return NUM_ORDERS_INPUT

async def num_orders_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process number of orders input for scaled orders"""
    user_id = update.effective_user.id
    num_orders_text = update.message.text.strip()
    
    # Validate number of orders
    try:
        num_orders = int(num_orders_text)
        if num_orders < 2 or num_orders > 50:
            await update.message.reply_text(
                "❌ Number of orders must be between 2 and 50.\n\n"
                "Please enter a valid number of orders:"
            )
            return NUM_ORDERS_INPUT
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Please enter a valid integer for number of orders:"
        )
        return NUM_ORDERS_INPUT
    
    # Store number of orders
    user_sessions[user_id]['trading_data']['num_orders'] = num_orders
    
    # Check action type to determine next step
    action = user_sessions[user_id]['trading_data'].get('action', '')
    market = user_sessions[user_id]['trading_data'].get('market', '')
    
    if "market_aware" in action:
        # For market-aware orders, ask for min distance
        await update.message.reply_text(
            "Enter the minimum distance from market price (as percentage, e.g. 1.5 for 1.5%):"
        )
        return MIN_DISTANCE_INPUT
    elif "perp_scaled_orders" in action:
        # For perp scaled orders, ask for leverage
        await update.message.reply_text(
            "Enter leverage (1-100, default is 1):"
        )
        return LEVERAGE_INPUT
    else:
        # For regular scaled orders, prepare confirmation
        return await prepare_scaled_order_confirmation(update, user_id)

async def min_distance_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process minimum distance input for market-aware scaled orders"""
    user_id = update.effective_user.id
    min_distance_text = update.message.text.strip()
    
    # Validate min distance
    try:
        min_distance = float(min_distance_text)
        if min_distance < 0.1 or min_distance > 50:
            await update.message.reply_text(
                "❌ Minimum distance must be between 0.1% and 50%.\n\n"
                "Please enter a valid minimum distance:"
            )
            return MIN_DISTANCE_INPUT
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Please enter a valid number for minimum distance:"
        )
        return MIN_DISTANCE_INPUT
    
    # Store min distance (convert to decimal)
    user_sessions[user_id]['trading_data']['min_distance'] = min_distance / 100
    
# Ask for max distance
    await update.message.reply_text(
        "Enter the maximum distance from market price (as percentage, e.g. 5.0 for 5%):"
    )
    return MAX_DISTANCE_INPUT

async def max_distance_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process maximum distance input for market-aware scaled orders"""
    user_id = update.effective_user.id
    max_distance_text = update.message.text.strip()
    
    # Validate max distance
    try:
        max_distance = float(max_distance_text)
        min_distance = user_sessions[user_id]['trading_data'].get('min_distance', 0) * 100
        
        if max_distance < min_distance or max_distance > 100:
            await update.message.reply_text(
                f"❌ Maximum distance must be between {min_distance}% and 100%.\n\n"
                f"Please enter a valid maximum distance:"
            )
            return MAX_DISTANCE_INPUT
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Please enter a valid number for maximum distance:"
        )
        return MAX_DISTANCE_INPUT
    
    # Store max distance (convert to decimal)
    user_sessions[user_id]['trading_data']['max_distance'] = max_distance / 100
    
    # Ask for market type
    keyboard = [
        [
            InlineKeyboardButton("Spot", callback_data="market_type_spot"),
            InlineKeyboardButton("Perpetual", callback_data="market_type_perp")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Select market type:",
        reply_markup=reply_markup
    )
    return PERP_ACTION  # Reusing PERP_ACTION state for market type selection

async def price_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
   """Process price input for limit orders"""
   user_id = update.effective_user.id
   price_text = update.message.text.strip()
   
   # Validate price
   is_valid, result = validate_input('price', price_text)
   if not is_valid:
       await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid price:")
       return PRICE_INPUT
   
   # Store price
   user_sessions[user_id]['trading_data']['price'] = result
   
   # For perp market, we need leverage
   market = user_sessions[user_id]['trading_data'].get('market')
   if market == 'perp':
       await update.message.reply_text(
           "Enter leverage (1-100, default is 1):"
       )
       return LEVERAGE_INPUT
   
   # For spot limit orders, go to confirmation
   data = user_sessions[user_id]['trading_data']
   action = data.get('action', '')
   action_text = action.split('_', 1)[1] if '_' in action else action
   action_text = action_text.replace('_', ' ')
   symbol = data.get('symbol', '')
   amount = data.get('amount', 0)
   price = data.get('price', 0)
   
   await update.message.reply_text(
       f"⚠️ You are about to place a {action_text} order:\n\n"
       f"• Symbol: {symbol}\n"
       f"• Amount: {amount}\n"
       f"• Price: {price}\n\n"
       f"Type 'confirm' to place the order or 'cancel' to abort:"
   )
   return CONFIRM_ORDER

async def leverage_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
   """Process leverage input for perpetual orders"""
   user_id = update.effective_user.id
   leverage_text = update.message.text.strip()
   
   # For set_leverage action, we just need leverage
   action = user_sessions[user_id]['trading_data'].get('action', '')
   
   if action == 'perp_set_leverage':
       # Validate leverage
       is_valid, result = validate_input('leverage', leverage_text)
       if not is_valid:
           await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid leverage:")
           return LEVERAGE_INPUT
       
       # Store leverage
       user_sessions[user_id]['trading_data']['leverage'] = result
       
       # Go to confirmation
       symbol = user_sessions[user_id]['trading_data'].get('symbol', '')
       leverage = result
       
       await update.message.reply_text(
           f"⚠️ You are about to set leverage for {symbol} to {leverage}x.\n\n"
           f"Type 'confirm' to proceed or 'cancel' to abort:"
       )
       return CONFIRM_ORDER
   
   # For regular perp orders and scaled orders
   # Default to leverage 1 if empty
   if not leverage_text:
       leverage = 1
   else:
       # Validate leverage
       is_valid, result = validate_input('leverage', leverage_text)
       if not is_valid:
           await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid leverage:")
           return LEVERAGE_INPUT
       leverage = result
   
   # Store leverage
   user_sessions[user_id]['trading_data']['leverage'] = leverage
   
   # Check action type for next step
   if "market_aware_scaled" in action:
       # For market-aware scaled orders with perp market, go to confirmation
       return await prepare_scaled_order_confirmation(update, user_id)
       
   elif "scaled_orders" in action:
       # For regular scaled orders with perp market, go to confirmation
       return await prepare_scaled_order_confirmation(update, user_id)
   
   # For regular perp orders
   # Check if we need slippage (market order) or go to confirmation (limit order)
   if 'market' in action:
       await update.message.reply_text(
           "Enter maximum slippage allowed (0-1, default is 0.05):"
       )
       return SLIPPAGE_INPUT
   
   # For limit orders, go to confirmation
   data = user_sessions[user_id]['trading_data']
   action_text = action.split('_', 1)[1] if '_' in action else action
   action_text = action_text.replace('_', ' ')
   symbol = data.get('symbol', '')
   amount = data.get('amount', 0)
   price = data.get('price', 0)
   
   await update.message.reply_text(
       f"⚠️ You are about to place a {action_text} order with {leverage}x leverage:\n\n"
       f"• Symbol: {symbol}\n"
       f"• Amount: {amount}\n"
       f"• Price: {price}\n"
       f"• Leverage: {leverage}x\n\n"
       f"Type 'confirm' to place the order or 'cancel' to abort:"
   )
   return CONFIRM_ORDER

async def slippage_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
   """Process slippage input for market orders"""
   user_id = update.effective_user.id
   slippage_text = update.message.text.strip()
   
   # Default to 0.05 if empty
   if not slippage_text:
       slippage = 0.05
   else:
       # Validate slippage
       is_valid, result = validate_input('slippage', slippage_text)
       if not is_valid:
           await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid slippage:")
           return SLIPPAGE_INPUT
       slippage = result
   
   # Store slippage
   user_sessions[user_id]['trading_data']['slippage'] = slippage
   
   # Prepare confirmation message
   data = user_sessions[user_id]['trading_data']
   action = data.get('action', '')
   action_text = action.split('_', 1)[1] if '_' in action else action
   action_text = action_text.replace('_', ' ')
   symbol = data.get('symbol', '')
   amount = data.get('amount', 0)
   leverage = data.get('leverage', 1)
   market = data.get('market', 'spot')
   
   if market == 'perp':
       await update.message.reply_text(
           f"⚠️ You are about to place a {action_text} order with {leverage}x leverage:\n\n"
           f"• Symbol: {symbol}\n"
           f"• Amount: {amount}\n"
           f"• Slippage: {slippage}\n"
           f"• Leverage: {leverage}x\n\n"
           f"Type 'confirm' to place the order or 'cancel' to abort:"
       )
   else:
       await update.message.reply_text(
           f"⚠️ You are about to place a {action_text} order:\n\n"
           f"• Symbol: {symbol}\n"
           f"• Amount: {amount}\n"
           f"• Slippage: {slippage}\n\n"
           f"Type 'confirm' to place the order or 'cancel' to abort:"
       )
   
   return CONFIRM_ORDER

async def prepare_scaled_order_confirmation(update, user_id, is_callback=False):
    """Prepare confirmation message for scaled orders"""
    data = user_sessions[user_id]['trading_data']
    action = data.get('action', '')
    symbol = data.get('symbol', '')
    total_amount = data.get('amount', 0)
    num_orders = data.get('num_orders', 0)
    
    confirmation_text = ""
    
    if "market_aware_scaled" in action:
        market_type = data.get('market', 'spot')
        min_distance = data.get('min_distance', 0) * 100  # Convert back to percentage
        max_distance = data.get('max_distance', 0) * 100  # Convert back to percentage
        leverage = data.get('leverage', 1)
        
        order_type = "Market-Aware Scaled " + ("Buy" if "buy" in action else "Sell")
        
        confirmation_text = (
            f"⚠️ You are about to place a {order_type} order:\n\n"
            f"• Symbol: {symbol}\n"
            f"• Total Amount: {total_amount}\n"
            f"• Number of Orders: {num_orders}\n"
            f"• Min Distance: {min_distance:.2f}%\n"
            f"• Max Distance: {max_distance:.2f}%\n"
            f"• Market Type: {market_type.upper()}\n"
        )
        
        if market_type == "perp":
            confirmation_text += f"• Leverage: {leverage}x\n"
            
    else:
        min_price = data.get('min_price', 0)
        max_price = data.get('max_price', 0)
        market = data.get('market', 'spot')
        leverage = data.get('leverage', 1)
        
        order_type = ("Perpetual" if market == "perp" else "Spot") + " Scaled Orders"
        side = "BUY" if data.get('side', '') == "buy" else "SELL"
        
        confirmation_text = (
            f"⚠️ You are about to place {order_type} ({side}):\n\n"
            f"• Symbol: {symbol}\n"
            f"• Total Amount: {total_amount}\n"
            f"• Number of Orders: {num_orders}\n"
            f"• Price Range: {min_price} - {max_price}\n"
        )
        
        if market == "perp":
            confirmation_text += f"• Leverage: {leverage}x\n"
    
    confirmation_text += "\nType 'confirm' to place the orders or 'cancel' to abort:"
    
    if is_callback:
        await update.callback_query.edit_message_text(confirmation_text)
    else:
        await update.message.reply_text(confirmation_text)
    
    return CONFIRM_ORDER

async def confirm_order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process order confirmation and execute the order"""
    user_id = update.effective_user.id
    confirmation = update.message.text.strip().lower()
    
    if confirmation != 'confirm':
        await update.message.reply_text("Order cancelled.")
        return ConversationHandler.END
    
    # Get order details from user session
    data = user_sessions[user_id]['trading_data']
    market = data.get('market', 'spot')
    action = data.get('action', '')
    symbol = data.get('symbol', '')
    amount = data.get('amount', 0)
    price = data.get('price', 0)
    leverage = data.get('leverage', 1)
    slippage = data.get('slippage', 0.05)
    
    # Get API client
    api_client = user_sessions[user_id]['api_client']
    
    # Send a "processing" message
    message = await update.message.reply_text("Processing your order...")
    
    try:
        # Execute order based on market and action
        if "spot_scaled_orders" in action:
            min_price = data.get('min_price', 0)
            max_price = data.get('max_price', 0)
            num_orders = data.get('num_orders', 5)
            side = data.get('side', 'buy')
            result = await api_client.spot_scaled_orders(
                symbol, amount, num_orders, min_price, max_price, side
            )
            
        elif "perp_scaled_orders" in action:
            min_price = data.get('min_price', 0)
            max_price = data.get('max_price', 0)
            num_orders = data.get('num_orders', 5)
            side = data.get('side', 'buy')
            leverage = data.get('leverage', 1)
            result = await api_client.perp_scaled_orders(
                symbol, amount, num_orders, min_price, max_price, side, leverage
            )
            
        elif "market_aware_scaled_buy" in action:
            num_orders = data.get('num_orders', 5)
            min_distance = data.get('min_distance', 0.01)
            max_distance = data.get('max_distance', 0.05)
            market_type = data.get('market', 'spot')
            leverage = data.get('leverage', 1)
            result = await api_client.market_aware_scaled_buy(
                symbol, amount, num_orders, min_distance, max_distance, market_type, leverage
            )
            
        elif "market_aware_scaled_sell" in action:
            num_orders = data.get('num_orders', 5)
            min_distance = data.get('min_distance', 0.01)
            max_distance = data.get('max_distance', 0.05)
            market_type = data.get('market', 'spot')
            leverage = data.get('leverage', 1)
            result = await api_client.market_aware_scaled_sell(
                symbol, amount, num_orders, min_distance, max_distance, market_type, leverage
            )
            
        elif market == 'spot':
            if 'market_buy' in action:
                result = await api_client.spot_market_buy(symbol, amount, slippage)
            elif 'market_sell' in action:
                result = await api_client.spot_market_sell(symbol, amount, slippage)
            elif 'limit_buy' in action:
                result = await api_client.spot_limit_buy(symbol, amount, price)
            elif 'limit_sell' in action:
                result = await api_client.spot_limit_sell(symbol, amount, price)
            else:
                result = {"success": False, "message": "Invalid action"}
        
        elif market == 'perp':
            if 'market_buy' in action:
                result = await api_client.perp_market_buy(symbol, amount, leverage, slippage)
            elif 'market_sell' in action:
                result = await api_client.perp_market_sell(symbol, amount, leverage, slippage)
            elif 'limit_buy' in action:
                result = await api_client.perp_limit_buy(symbol, amount, price, leverage)
            elif 'limit_sell' in action:
                result = await api_client.perp_limit_sell(symbol, amount, price, leverage)
            elif 'close_position' in action:
                result = await api_client.perp_close_position(symbol, slippage)
            elif 'set_leverage' in action:
                result = await api_client.perp_set_leverage(symbol, leverage)
            else:
                result = {"success": False, "message": "Invalid action"}
        
        else:
            result = {"success": False, "message": "Invalid market type"}
        
        # Format the result
        formatted_result = format_order_result(result)
        
        # Update the message with the formatted result
        await message.edit_text(formatted_result, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error executing order: {str(e)}")
        await message.edit_text(f"❌ Error executing order: {str(e)}")
    
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
   """Display help message"""
   await update.message.reply_text(MESSAGES['help'])

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
   """Cancel the current conversation"""
   await update.message.reply_text("Operation cancelled.")
   return ConversationHandler.END

# Utility function to check if user is connected
def check_connected(user_id: int) -> bool:
   """Check if a user is connected to the API"""
   return (user_id in user_sessions and 
           user_sessions[user_id]['api_client'].is_connected)

# Grid Trading Handler Starts

async def grid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle grid trading commands"""
    user_id = update.effective_user.id
    
    # Check if user is connected
    if (user_id not in user_sessions or 
        not user_sessions[user_id]['api_client'].is_connected):
        await update.message.reply_text(MESSAGES['not_connected'])
        return ConversationHandler.END
    
    # Clear previous trading data
    user_sessions[user_id]['trading_data'] = {}
    
    # Show grid trading options
    keyboard = [
        [
            InlineKeyboardButton("Create Grid", callback_data="grid_create"),
            InlineKeyboardButton("List Grids", callback_data="grid_list")
        ],
        [
            InlineKeyboardButton("Start Grid", callback_data="grid_start"),
            InlineKeyboardButton("Stop Grid", callback_data="grid_stop")
        ],
        [
            InlineKeyboardButton("Grid Status", callback_data="grid_status"),
            InlineKeyboardButton("Modify Grid", callback_data="grid_modify")
        ],
        [
            InlineKeyboardButton("Stop All Grids", callback_data="grid_stop_all"),
            InlineKeyboardButton("Cancel", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 *Grid Trading*\n\nSelect a grid trading action:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return GRID_ACTION

async def grid_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle grid selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "cancel":
        await query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END
    
    # Extract grid ID from callback data
    if data.startswith("grid_id_"):
        grid_id = data[8:]  # Remove "grid_id_" prefix
        
        # Store grid ID in user session
        user_sessions[user_id]['trading_data']['grid_id'] = grid_id
        
        # Get the original action
        action = user_sessions[user_id]['trading_data']['action']
        
        if action == "grid_start":
            # Confirm starting the grid
            await query.edit_message_text(
                f"⚠️ You are about to start grid trading with ID: `{grid_id}`\n\n"
                f"Type 'confirm' to proceed or 'cancel' to abort:",
                parse_mode='Markdown'
            )
            return GRID_CONFIRM
            
        elif action == "grid_stop":
            # Confirm stopping the grid
            await query.edit_message_text(
                f"⚠️ You are about to stop grid trading with ID: `{grid_id}`\n\n"
                f"Type 'confirm' to proceed or 'cancel' to abort:",
                parse_mode='Markdown'
            )
            return GRID_CONFIRM
            
        elif action == "grid_status":
            # Show grid status immediately
            return await grid_status_handler(update, context)
            
        elif action == "grid_modify":
            # Ask for take profit and stop loss values
            await query.edit_message_text(
                f"You are modifying grid with ID: `{grid_id}`\n\n"
                f"Enter new take profit price (or 'skip' to leave unchanged):",
                parse_mode='Markdown'
            )
            return GRID_TAKE_PROFIT
    
    # Default fallback
    await query.edit_message_text("Please select a valid grid.")
    return ConversationHandler.END

async def grid_market_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle grid market type selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "cancel":
        await query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END
    
    # Extract market type from callback data
    if data.startswith("grid_market_"):
        market_type = data[12:]  # Remove "grid_market_" prefix
        
        # Store market type in user session
        user_sessions[user_id]['trading_data']['is_perp'] = (market_type == "perp")
        
        # Ask for trading pair
        await query.edit_message_text(
            "Enter the trading pair for your grid (e.g., BTC/USDC):"
        )
        return GRID_SYMBOL
    
    # Default fallback
    await query.edit_message_text("Please select a valid market type.")
    return ConversationHandler.END

async def grid_symbol_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process symbol input for grid trading"""
    user_id = update.effective_user.id
    symbol = update.message.text.strip().upper()
    
    # Validate symbol
    is_valid, result = validate_input('symbol', symbol)
    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid trading pair:")
        return GRID_SYMBOL
    
    # Store symbol in user session
    user_sessions[user_id]['trading_data']['symbol'] = symbol
    
    # Ask for lower price
    await update.message.reply_text(
        "Enter the lower price bound for your grid:"
    )
    return GRID_LOWER_PRICE

async def grid_lower_price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process lower price input for grid trading"""
    user_id = update.effective_user.id
    lower_price_text = update.message.text.strip()
    
    # Validate lower price
    is_valid, result = validate_input('price', lower_price_text)
    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid lower price:")
        return GRID_LOWER_PRICE
    
    # Store lower price in user session
    user_sessions[user_id]['trading_data']['lower_price'] = result
    
    # Ask for upper price
    await update.message.reply_text(
        "Enter the upper price bound for your grid:"
    )
    return GRID_UPPER_PRICE

async def grid_upper_price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process upper price input for grid trading"""
    user_id = update.effective_user.id
    upper_price_text = update.message.text.strip()
    
    # Validate upper price
    is_valid, result = validate_input('price', upper_price_text)
    if not is_valid:
        await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid upper price:")
        return GRID_UPPER_PRICE
    
    # Get lower price for comparison
    lower_price = user_sessions[user_id]['trading_data'].get('lower_price', 0)
    
    # Ensure upper price is greater than lower price
    if result <= lower_price:
        await update.message.reply_text(
            f"❌ Upper price must be greater than lower price ({lower_price}).\n\n"
            f"Please enter a valid upper price:"
        )
        return GRID_UPPER_PRICE
    
    # Store upper price in user session
    user_sessions[user_id]['trading_data']['upper_price'] = result
    
    # Ask for number of grid levels
    await update.message.reply_text(
        "Enter the number of grid levels (2-100):"
    )
    return GRID_NUM_LEVELS

async def grid_num_levels_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process number of grid levels input"""
    user_id = update.effective_user.id
    num_levels_text = update.message.text.strip()
    
    # Validate number of grid levels
    try:
        num_levels = int(num_levels_text)
        if num_levels < 2 or num_levels > 100:
            await update.message.reply_text(
                "❌ Number of grid levels must be between 2 and 100.\n\n"
                "Please enter a valid number of grid levels:"
            )
            return GRID_NUM_LEVELS
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Please enter a valid integer for number of grid levels:"
        )
        return GRID_NUM_LEVELS
    
    # Store number of grid levels in user session
    user_sessions[user_id]['trading_data']['num_grids'] = num_levels
    
    # Ask for total investment
    await update.message.reply_text(
        "Enter the total investment amount for your grid strategy:"
    )
    return GRID_INVESTMENT

async def grid_investment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process total investment input"""
    user_id = update.effective_user.id
    investment_text = update.message.text.strip()
    
    # Validate investment amount
    try:
        investment = float(investment_text)
        if investment <= 0:
            await update.message.reply_text(
                "❌ Investment amount must be greater than 0.\n\n"
                "Please enter a valid investment amount:"
            )
            return GRID_INVESTMENT
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Please enter a valid number for investment amount:"
        )
        return GRID_INVESTMENT
    
    # Store investment amount in user session
    user_sessions[user_id]['trading_data']['total_investment'] = investment
    
    # If it's a perpetual market, ask for leverage
    is_perp = user_sessions[user_id]['trading_data'].get('is_perp', False)
    if is_perp:
        await update.message.reply_text(
            "Enter leverage (1-100, default is 1):"
        )
        return GRID_LEVERAGE
    
    # Ask for take profit
    await update.message.reply_text(
        "Enter take profit price (optional, leave empty to skip):"
    )
    return GRID_TAKE_PROFIT

async def grid_leverage_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process leverage input for grid trading"""
    user_id = update.effective_user.id
    leverage_text = update.message.text.strip()
    
    # Default to leverage 1 if empty
    if not leverage_text:
        leverage = 1
    else:
        # Validate leverage
        is_valid, result = validate_input('leverage', leverage_text)
        if not is_valid:
            await update.message.reply_text(f"❌ {result}\n\nPlease enter a valid leverage:")
            return GRID_LEVERAGE
        leverage = result
    
    # Store leverage in user session
    user_sessions[user_id]['trading_data']['leverage'] = leverage
    
    # Ask for take profit
    await update.message.reply_text(
        "Enter take profit price (optional, leave empty to skip):"
    )
    return GRID_TAKE_PROFIT

async def grid_take_profit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process take profit input"""
    user_id = update.effective_user.id
    take_profit_text = update.message.text.strip()
    
    # Skip if empty or "skip"
    if not take_profit_text or take_profit_text.lower() == 'skip':
        user_sessions[user_id]['trading_data']['take_profit'] = None
    else:
        # Validate take profit price
        try:
            take_profit = float(take_profit_text)
            if take_profit <= 0:
                await update.message.reply_text(
                    "❌ Take profit price must be greater than 0.\n\n"
                    "Please enter a valid take profit price (or leave empty to skip):"
                )
                return GRID_TAKE_PROFIT
                
            # For grid creation, check against upper price
            action = user_sessions[user_id]['trading_data'].get('action', '')
            if 'grid_create' in action:
                upper_price = user_sessions[user_id]['trading_data'].get('upper_price', 0)
                if take_profit <= upper_price:
                    await update.message.reply_text(
                        f"❌ Take profit price must be greater than upper price ({upper_price}).\n\n"
                        f"Please enter a valid take profit price (or leave empty to skip):"
                    )
                    return GRID_TAKE_PROFIT
            
            user_sessions[user_id]['trading_data']['take_profit'] = take_profit
            
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid input. Please enter a valid number for take profit price (or leave empty to skip):"
            )
            return GRID_TAKE_PROFIT
    
    # Ask for stop loss
    await update.message.reply_text(
        "Enter stop loss price (optional, leave empty to skip):"
    )
    return GRID_STOP_LOSS

async def grid_stop_loss_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process stop loss input"""
    user_id = update.effective_user.id
    stop_loss_text = update.message.text.strip()
    
    # Skip if empty or "skip"
    if not stop_loss_text or stop_loss_text.lower() == 'skip':
        user_sessions[user_id]['trading_data']['stop_loss'] = None
    else:
        # Validate stop loss price
        try:
            stop_loss = float(stop_loss_text)
            if stop_loss <= 0:
                await update.message.reply_text(
                    "❌ Stop loss price must be greater than 0.\n\n"
                    "Please enter a valid stop loss price (or leave empty to skip):"
                )
                return GRID_STOP_LOSS
                
            # For grid creation, check against lower price
            action = user_sessions[user_id]['trading_data'].get('action', '')
            if 'grid_create' in action:
                lower_price = user_sessions[user_id]['trading_data'].get('lower_price', 0)
                if stop_loss >= lower_price:
                    await update.message.reply_text(
                        f"❌ Stop loss price must be less than lower price ({lower_price}).\n\n"
                        f"Please enter a valid stop loss price (or leave empty to skip):"
                    )
                    return GRID_STOP_LOSS
            
            user_sessions[user_id]['trading_data']['stop_loss'] = stop_loss
            
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid input. Please enter a valid number for stop loss price (or leave empty to skip):"
            )
            return GRID_STOP_LOSS
    
    # Determine next step based on action
    action = user_sessions[user_id]['trading_data'].get('action', '')
    
    if action == 'grid_create':
        # For creating a new grid, show confirmation
        data = user_sessions[user_id]['trading_data']
        symbol = data.get('symbol', '')
        lower_price = data.get('lower_price', 0)
        upper_price = data.get('upper_price', 0)
        num_grids = data.get('num_grids', 0)
        total_investment = data.get('total_investment', 0)
        is_perp = data.get('is_perp', False)
        leverage = data.get('leverage', 1) if is_perp else "N/A"
        take_profit = data.get('take_profit', "Not set")
        stop_loss = data.get('stop_loss', "Not set")
        
        market_type = "Perpetual" if is_perp else "Spot"
        
        confirmation_text = (
            f"⚠️ You are about to create a new {market_type} grid trading strategy:\n\n"
            f"• Symbol: {symbol}\n"
            f"• Price Range: {lower_price} - {upper_price}\n"
            f"• Number of Grids: {num_grids}\n"
            f"• Total Investment: {total_investment}\n"
        )
        
        if is_perp:
            confirmation_text += f"• Leverage: {leverage}x\n"
            
        confirmation_text += f"• Take Profit: {take_profit}\n"
        confirmation_text += f"• Stop Loss: {stop_loss}\n\n"
        
        confirmation_text += "Type 'confirm' to create the grid or 'cancel' to abort:"
        
        await update.message.reply_text(confirmation_text)
        return GRID_CONFIRM
        
    elif action == 'grid_modify':
        # For modifying an existing grid, show confirmation
        data = user_sessions[user_id]['trading_data']
        grid_id = data.get('grid_id', '')
        take_profit = data.get('take_profit', "Not set")
        stop_loss = data.get('stop_loss', "Not set")
        
        confirmation_text = (
            f"⚠️ You are about to modify grid with ID: `{grid_id}`\n\n"
            f"• New Take Profit: {take_profit}\n"
            f"• New Stop Loss: {stop_loss}\n\n"
            f"Type 'confirm' to modify the grid or 'cancel' to abort:"
        )
        
        await update.message.reply_text(confirmation_text, parse_mode='Markdown')
        return GRID_CONFIRM
    
    # Default fallback
    await update.message.reply_text("Invalid action. Operation cancelled.")
    return ConversationHandler.END

async def grid_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process grid action confirmation"""
    user_id = update.effective_user.id
    confirmation = update.message.text.strip().lower()
    
    if confirmation != 'confirm':
        await update.message.reply_text("Operation cancelled.")
        return ConversationHandler.END
    
    # Get action and data from user session
    data = user_sessions[user_id]['trading_data']
    action = data.get('action', '')
    
    # Get grid trading instance
    api_client = user_sessions[user_id]['api_client']
    
    if 'grid_trading' not in user_sessions[user_id]:
        user_sessions[user_id]['grid_trading'] = GridTrading(api_client)
    
    grid_trading = user_sessions[user_id]['grid_trading']
    
    # Send a "processing" message
    message = await update.message.reply_text("Processing your request...")
    
    try:
        if action == 'grid_create':
            # Create a new grid
            symbol = data.get('symbol', '')
            lower_price = data.get('lower_price', 0)
            upper_price = data.get('upper_price', 0)
            num_grids = data.get('num_grids', 0)
            total_investment = data.get('total_investment', 0)
            is_perp = data.get('is_perp', False)
            leverage = data.get('leverage', 1) if is_perp else 1
            take_profit = data.get('take_profit')
            stop_loss = data.get('stop_loss')
            
            result = await grid_trading.create_grid(
                symbol, upper_price, lower_price, num_grids, total_investment,
                is_perp, leverage, take_profit, stop_loss
            )
            
            if result.get('success', False):
                grid_id = result.get('grid_id', '')
                
                # Ask if user wants to start the grid immediately
                keyboard = [
                    [
                        InlineKeyboardButton("Yes, start now", callback_data=f"start_grid_{grid_id}"),
                        InlineKeyboardButton("No, start later", callback_data="cancel")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await message.edit_text(
                    f"✅ Grid created successfully with ID: `{grid_id}`\n\n"
                    f"Do you want to start this grid trading strategy now?",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return GRID_START_NOW
            else:
                error_msg = result.get('message', 'Unknown error')
                await message.edit_text(f"❌ Failed to create grid: {error_msg}")
                
        elif action == 'grid_start':
            # Start an existing grid
            grid_id = data.get('grid_id', '')
            result = await grid_trading.start_grid(grid_id)
            
            if result.get('success', False):
                await message.edit_text(
                    f"✅ Grid {grid_id} started successfully!\n\n"
                    f"• Orders placed: {result.get('orders_placed', 0)}"
                )
            else:
                error_msg = result.get('message', 'Unknown error')
                await message.edit_text(f"❌ Failed to start grid: {error_msg}")
                
        elif action == 'grid_stop':
            # Stop an existing grid
            grid_id = data.get('grid_id', '')
            result = await grid_trading.stop_grid(grid_id)
            
            if result.get('success', False):
                await message.edit_text(f"✅ Grid {grid_id} stopped successfully!")
            else:
                error_msg = result.get('message', 'Unknown error')
                await message.edit_text(f"❌ Failed to stop grid: {error_msg}")
                
        elif action == 'grid_stop_all':
            # Stop all active grids
            result = await grid_trading.stop_all_grids()
            
            if result.get('success', False):
                stopped_count = result.get('stopped_count', 0)
                errors = result.get('errors', [])
                
                status_msg = f"✅ Stopped {stopped_count} grid(s) successfully!"
                
                if errors:
                    status_msg += "\n\nErrors encountered:"
                    for error in errors:
                        status_msg += f"\n• {error}"
                
                await message.edit_text(status_msg)
            else:
                error_msg = result.get('message', 'Unknown error')
                await message.edit_text(f"❌ Failed to stop all grids: {error_msg}")
                
        elif action == 'grid_modify':
            # Modify an existing grid
            grid_id = data.get('grid_id', '')
            take_profit = data.get('take_profit')
            stop_loss = data.get('stop_loss')
            
            result = await grid_trading.modify_grid(grid_id, take_profit, stop_loss)
            
            if result.get('success', False):
                await message.edit_text(
                    f"✅ Grid {grid_id} modified successfully!\n\n"
                    f"• Take Profit: {result.get('take_profit', 'Not set')}\n"
                    f"• Stop Loss: {result.get('stop_loss', 'Not set')}"
                )
            else:
                error_msg = result.get('message', 'Unknown error')
                await message.edit_text(f"❌ Failed to modify grid: {error_msg}")
        
        else:
            await message.edit_text("Invalid action. Operation cancelled.")
            
    except Exception as e:
        logging.error(f"Error in grid_confirm_handler: {str(e)}")
        await message.edit_text(f"❌ Error processing request: {str(e)}")
    
    return ConversationHandler.END

async def grid_start_now_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle immediate grid start after creation"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "cancel":
        await query.edit_message_text("Grid created but not started. You can start it later.")
        return ConversationHandler.END
    
    # Extract grid ID from callback data
    if data.startswith("start_grid_"):
        grid_id = data[11:]  # Remove "start_grid_" prefix
        
        # Get grid trading instance
        api_client = user_sessions[user_id]['api_client']
        grid_trading = user_sessions[user_id]['grid_trading']
        
        # Send a "processing" message
        await query.edit_message_text("Starting grid trading strategy...")
        
        try:
            # Start the grid
            result = await grid_trading.start_grid(grid_id)
            
            if result.get('success', False):
                await query.edit_message_text(
                    f"✅ Grid {grid_id} started successfully!\n\n"
                    f"• Orders placed: {result.get('orders_placed', 0)}"
                )
            else:
                error_msg = result.get('message', 'Unknown error')
                await query.edit_message_text(
                    f"❌ Failed to start grid: {error_msg}\n\n"
                    f"You can try starting it later using the start grid command."
                )
                
        except Exception as e:
            logging.error(f"Error in grid_start_now_handler: {str(e)}")
            await query.edit_message_text(
                f"❌ Error starting grid: {str(e)}\n\n"
                f"You can try starting it later using the start grid command."
            )
    
    return ConversationHandler.END

async def grid_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle grid status request"""
    # Determine if this was called from a callback query or directly
    if update.callback_query:
        query = update.callback_query
        user_id = query.from_user.id
        message_func = query.edit_message_text
    else:
        user_id = update.effective_user.id
        message_func = update.message.reply_text
    
    # Get grid ID from user session
    grid_id = user_sessions[user_id]['trading_data'].get('grid_id', '')
    
    if not grid_id:
        await message_func("No grid ID selected. Operation cancelled.")
        return ConversationHandler.END
    
    # Get grid trading instance
    api_client = user_sessions[user_id]['api_client']
    
    if 'grid_trading' not in user_sessions[user_id]:
        user_sessions[user_id]['grid_trading'] = GridTrading(api_client)
    
    grid_trading = user_sessions[user_id]['grid_trading']
    
    # Get grid status
    status = grid_trading.get_grid_status(grid_id)
    
    if not status.get('success', False):
        await message_func(f"❌ {status.get('message', 'Failed to get grid status')}")
        return ConversationHandler.END
    
    # Format status message
    symbol = status.get('symbol', '')
    grid_status = status.get('status', 'unknown')
    active = "🟢 Active" if status.get('active', False) else "🔴 Inactive"
    market_type = "Perpetual" if status.get('is_perp', False) else "Spot"
    lower_price = status.get('lower_price', 0)
    upper_price = status.get('upper_price', 0)
    num_grids = status.get('num_grids', 0)
    investment = status.get('investment', 0)
    leverage = status.get('leverage', 1)
    take_profit = status.get('take_profit', "Not set")
    stop_loss = status.get('stop_loss', "Not set")
    filled_orders = status.get('filled_orders', 0)
    open_orders = status.get('open_orders', 0)
    estimated_pnl = status.get('estimated_pnl', 0)
    created_at = status.get('created_at', 0)
    started_at = status.get('started_at', 0)
    stopped_at = status.get('stopped_at', 0)
    
    # Format timestamps
    created_str = format_timestamp(created_at) if created_at else "N/A"
    started_str = format_timestamp(started_at) if started_at else "N/A"
    stopped_str = format_timestamp(stopped_at) if stopped_at else "N/A"
    
    status_message = (
        f"📊 *Grid Trading Status*\n\n"
        f"• Grid ID: `{grid_id}`\n"
        f"• Symbol: {symbol}\n"
        f"• Status: {active} ({grid_status})\n"
        f"• Market Type: {market_type}\n\n"
        
        f"*Grid Configuration*\n"
        f"• Price Range: {lower_price} - {upper_price}\n"
        f"• Number of Grids: {num_grids}\n"
        f"• Total Investment: {investment}\n"
    )
    
    if market_type == "Perpetual":
        status_message += f"• Leverage: {leverage}x\n"
        
    status_message += (
        f"• Take Profit: {take_profit}\n"
        f"• Stop Loss: {stop_loss}\n\n"
        
        f"*Order Status*\n"
        f"• Open Orders: {open_orders}\n"
        f"• Filled Orders: {filled_orders}\n"
        f"• Estimated P&L: {estimated_pnl:.8f}\n\n"
        
        f"*Timestamps*\n"
        f"• Created: {created_str}\n"
        f"• Started: {started_str}\n"
        f"• Stopped: {stopped_str}\n"
    )
    
    await message_func(status_message, parse_mode='Markdown')
    return ConversationHandler.END

async def format_timestamp(timestamp):
    """Format a Unix timestamp to readable date/time"""
    from datetime import datetime
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    # Clear previous trading data
    user_sessions[user_id]['trading_data'] = {}
    
    # Show grid trading options
    keyboard = [
        [
            InlineKeyboardButton("Create Grid", callback_data="grid_create"),
            InlineKeyboardButton("List Grids", callback_data="grid_list")
        ],
        [
            InlineKeyboardButton("Start Grid", callback_data="grid_start"),
            InlineKeyboardButton("Stop Grid", callback_data="grid_stop")
        ],
        [
            InlineKeyboardButton("Grid Status", callback_data="grid_status"),
            InlineKeyboardButton("Modify Grid", callback_data="grid_modify")
        ],
        [
            InlineKeyboardButton("Stop All Grids", callback_data="grid_stop_all"),
            InlineKeyboardButton("Cancel", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 *Grid Trading*\n\nSelect a grid trading action:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return GRID_ACTION

async def grid_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle grid trading action selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    
    if action == "cancel":
        await query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END
    
    # Store the action in user session
    user_sessions[user_id]['trading_data']['action'] = action
    
    if action == "grid_list":
        # List all grids immediately
        return await grid_list_handler(update, context)
    
    elif action == "grid_stop_all":
        # Confirm stopping all grids
        await query.edit_message_text(
            "⚠️ Are you sure you want to stop all active grid trading strategies?\n\n"
            "Type 'confirm' to proceed or 'cancel' to abort:"
        )
        return GRID_CONFIRM
    
    elif action == "grid_start" or action == "grid_stop" or action == "grid_status" or action == "grid_modify":
        # Show active grids to select from
        api_client = user_sessions[user_id]['api_client']
        
        # Check if we have a grid trading instance
        if 'grid_trading' not in user_sessions[user_id]:
            user_sessions[user_id]['grid_trading'] = GridTrading(api_client)
        
        grid_trading = user_sessions[user_id]['grid_trading']
        grids = grid_trading.list_grids()
        
        if not grids.get('success', False) or (len(grids.get('active', [])) == 0 and len(grids.get('inactive', [])) == 0):
            await query.edit_message_text(
                "No grid trading strategies found. Please create a grid first."
            )
            return ConversationHandler.END
        
        keyboard = []
        
        # For grid_start, only show inactive grids
        if action == "grid_start":
            inactive_grids = grids.get('inactive', [])
            if not inactive_grids:
                await query.edit_message_text(
                    "No inactive grid trading strategies found. All grids are already running."
                )
                return ConversationHandler.END
            
            for grid in inactive_grids:
                grid_id = grid.get('id', '')
                symbol = grid.get('symbol', '')
                keyboard.append([InlineKeyboardButton(f"{symbol} ({grid_id})", callback_data=f"grid_id_{grid_id}")])
        
        # For grid_stop, only show active grids
        elif action == "grid_stop":
            active_grids = grids.get('active', [])
            if not active_grids:
                await query.edit_message_text(
                    "No active grid trading strategies found. All grids are already stopped."
                )
                return ConversationHandler.END
            
            for grid in active_grids:
                grid_id = grid.get('id', '')
                symbol = grid.get('symbol', '')
                keyboard.append([InlineKeyboardButton(f"{symbol} ({grid_id})", callback_data=f"grid_id_{grid_id}")])
        
        # For grid_status and grid_modify, show all grids
        else:
            all_grids = grids.get('active', []) + grids.get('inactive', [])
            for grid in all_grids:
                grid_id = grid.get('id', '')
                symbol = grid.get('symbol', '')
                status = "🟢" if grid.get('active', False) else "🔴"
                keyboard.append([InlineKeyboardButton(f"{status} {symbol} ({grid_id})", callback_data=f"grid_id_{grid_id}")])
        
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Select a grid to {action.split('_')[1]}:",
            reply_markup=reply_markup
        )
        return GRID_SELECT
    
    elif action == "grid_create":
        # For creating a new grid, ask for market type first
        keyboard = [
            [
                InlineKeyboardButton("Spot Market", callback_data="grid_market_spot"),
                InlineKeyboardButton("Perpetual Market", callback_data="grid_market_perp")
            ],
            [
                InlineKeyboardButton("Cancel", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Select market type for your grid trading strategy:",
            reply_markup=reply_markup
        )
        return GRID_MARKET_TYPE
    
    # Default fallback
    await query.edit_message_text("Please select a valid action.")
    return ConversationHandler.END

async def grid_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle grid list action"""
    # Determine if this was called from a callback query or directly
    if update.callback_query:
        query = update.callback_query
        user_id = query.from_user.id
        message_func = query.edit_message_text
    else:
        user_id = update.effective_user.id
        message_func = update.message.reply_text
    
    # Get grid trading instance
    api_client = user_sessions[user_id]['api_client']
    
    if 'grid_trading' not in user_sessions[user_id]:
        user_sessions[user_id]['grid_trading'] = GridTrading(api_client)
    
    grid_trading = user_sessions[user_id]['grid_trading']
    
    # Get all grids
    grids = grid_trading.list_grids()
    
    if not grids.get('success', False) or (len(grids.get('active', [])) == 0 and len(grids.get('inactive', [])) == 0):
        await message_func(
            "No grid trading strategies found."
        )
        return ConversationHandler.END
    
    # Format the list
    active_grids = grids.get('active', [])
    inactive_grids = grids.get('inactive', [])
    
    result = "📋 *Grid Trading Strategies*\n\n"
    
    if active_grids:
        result += "🟢 *Active Grids*\n\n"
        for i, grid in enumerate(active_grids, 1):
            grid_id = grid.get('id', '')
            symbol = grid.get('symbol', '')
            lower_price = grid.get('lower_price', 0)
            upper_price = grid.get('upper_price', 0)
            filled = grid.get('filled_orders', 0)
            open_orders = grid.get('open_orders', 0)
            is_perp = "Perpetual" if grid.get('is_perp', False) else "Spot"
            pnl = grid.get('estimated_pnl', 0)
            
            result += f"*Grid #{i}*\n"
            result += f"• ID: `{grid_id}`\n"
            result += f"• Symbol: {symbol}\n"
            result += f"• Type: {is_perp}\n"
            result += f"• Price Range: {lower_price} - {upper_price}\n"
            result += f"• Filled Orders: {filled}\n"
            result += f"• Status: {status}\n\n"
            result += f"• Orders: {open_orders} open, {filled} filled\n"
            result += f"• Est. P&L: {pnl:.4f}\n\n"
    
    if inactive_grids:
        result += "🔴 *Inactive Grids*\n\n"
        for i, grid in enumerate(inactive_grids, 1):
            grid_id = grid.get('id', '')
            symbol = grid.get('symbol', '')
            lower_price = grid.get('lower_price', 0)
            upper_price = grid.get('upper_price', 0)
            filled = grid.get('filled_orders', 0)
            status = grid.get('status', 'unknown')
            is_perp = "Perpetual" if grid.get('is_perp', False) else "Spot"
            
            result += f"*Grid #{i}*\n"
            result += f"• ID: `{grid_id}`\n"
            result += f"• Symbol: {symbol}\n"
            result += f"• Type: {is_perp}\n"
            result += f"• Price Range: {lower_price} - {upper_price}\n"
            result += f"• Filled Orders: {filled}\n"
            result += f"• Status: {status}\n\n"
            result += f"• Orders: {open_orders} open, {filled} filled\n"
            result += f"• Est. P&L: {pnl:.4f}\n\n"
    
    await message_func(result, parse_mode='Markdown')   