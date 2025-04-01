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
from utils import format_balances, format_orders, format_order_result, validate_input

# Conversation states
(
    NETWORK_SELECTION, WALLET_ADDRESS, SECRET_KEY,
    SPOT_ACTION, PERP_ACTION, SCALED_ACTION,
    SYMBOL_INPUT, AMOUNT_INPUT, PRICE_INPUT, LEVERAGE_INPUT, SLIPPAGE_INPUT,
    MIN_PRICE_INPUT, MAX_PRICE_INPUT, NUM_ORDERS_INPUT, MIN_DISTANCE_INPUT, MAX_DISTANCE_INPUT,
    CONFIRM_ORDER
) = range(17)

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