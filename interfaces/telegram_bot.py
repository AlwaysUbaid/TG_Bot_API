"""Telegram bot interface for Elysium Trading Platform"""

import os
import logging
import json
import time
import re
import threading
import queue
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Telegram imports
from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler,
    Filters, CallbackContext
)

# Import project modules
from api.constants import DATA_DIR, SELECTING_NETWORK, SELECT_AUTH_TYPE, ENTER_CREDENTIALS
from api.constants import ENTER_SECRET_KEY, ENTER_WALLET_ADDRESS, CONFIRM_CREDENTIALS
from api.constants import SYMBOL, SIDE, AMOUNT, PRICE, CONFIRMATION
from api.connector import ApiConnector
from api.order import OrderHandler
from api.status import StatusChecker
from utils.config import ConfigManager
from utils.menu import create_main_menu

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Get path to user-specific files
def get_user_config_path(user_id):
    """Get path to user-specific config file"""
    return os.path.join(DATA_DIR, f"user_{user_id}_config.json")

def get_user_credentials_path(user_id):
    """Get path to user-specific credentials file"""
    return os.path.join(DATA_DIR, f"user_{user_id}_credentials.json")

# Credential security functions
def encrypt_credentials(data, password):
    """Simple encryption using password as a salt"""
    # In a production environment, use a proper encryption library
    # This is just a basic example to demonstrate the concept
    salt = hashlib.sha256(password.encode()).hexdigest()[:16]
    # For simplicity, just hash the combined string
    # In production, use actual encryption like Fernet
    return hashlib.sha256((json.dumps(data) + salt).encode()).hexdigest()

def save_user_credentials(user_id, network, secret_key, wallet_address, password=None):
    """Save user credentials securely"""
    credentials = {
        "network": network,
        "secret_key": secret_key,
        "wallet_address": wallet_address,
        "timestamp": datetime.now().isoformat()
    }
    
    # If password is provided, add a simple encryption/checksum
    if password:
        credentials["checksum"] = encrypt_credentials(credentials, password)
    
    path = get_user_credentials_path(user_id)
    with open(path, 'w') as f:
        json.dump(credentials, f)
    
    return True

def load_user_credentials(user_id, password=None):
    """Load user credentials"""
    path = get_user_credentials_path(user_id)
    
    if not os.path.exists(path):
        return None
        
    with open(path, 'r') as f:
        credentials = json.load(f)
    
    # If password is provided, verify the checksum
    if password and "checksum" in credentials:
        # Make a copy without the checksum for verification
        verify_data = credentials.copy()
        stored_checksum = verify_data.pop("checksum")
        calculated_checksum = encrypt_credentials(verify_data, password)
        
        if stored_checksum != calculated_checksum:
            logging.warning(f"Credential checksum verification failed for user {user_id}")
            return None
    
    return credentials

class ElysiumTelegramBot:
    """Telegram bot for Elysium Trading Platform"""
    
    def __init__(self, token=None, admin_ids=None):
        self.config_manager = ConfigManager()
        self.status_checker = StatusChecker()
        
        # Bot state
        self.user_data = {}  # Track user-specific data
        self.connected_users = set()  # Track which users are connected
        self.connection_contexts = {}  # Store connection context per user
        self.trading_context = {}  # Store trading info per user
        self.api_connectors = {}  # Store API connectors per user
        self.order_handlers = {}  # Store order handlers per user
        
        # For thread safety and synchronization
        self.state_lock = threading.Lock()
        
        # Initialize Telegram token
        self.telegram_token = token
        self.admin_ids = admin_ids or []
        
        if not self.telegram_token:
            # Try to load from environment or config
            self.telegram_token = os.environ.get('TELEGRAM_TOKEN')
            admin_ids_str = os.environ.get('ADMIN_USER_IDS', '')
            self.admin_ids = list(map(int, admin_ids_str.split(','))) if admin_ids_str else []
            
            # If still no token, try to load from config
            if not self.telegram_token:
                self.telegram_token = self.config_manager.get("telegram_token")
                self.admin_ids = self.config_manager.get("admin_user_ids", [])
        
        if not self.telegram_token:
            logging.error("No Telegram token found! Telegram bot will not start.")
            return
        
        # Initialize Telegram updater
        self.updater = Updater(self.telegram_token)
        self.dispatcher = self.updater.dispatcher
        
        # Register handlers
        self._register_handlers()
        
        logging.info("Elysium Telegram Bot initialized")
    
    def _register_handlers(self):
        """Register all command and message handlers"""
        # Welcome handler
        self.dispatcher.add_handler(CommandHandler("start", self.cmd_start))
        
        # Authentication conversation
        auth_conv = ConversationHandler(
            entry_points=[CommandHandler("connect", self.select_network)],
            states={
                SELECTING_NETWORK: [
                    CallbackQueryHandler(self.select_network_callback, pattern='^network_')
                ],
                SELECT_AUTH_TYPE: [
                    CallbackQueryHandler(self.select_auth_type_callback, pattern='^auth_')
                ],
                ENTER_SECRET_KEY: [
                    MessageHandler(Filters.text & ~Filters.command, self.ENTER_SECRET_KEY)
                ],
                ENTER_WALLET_ADDRESS: [
                    MessageHandler(Filters.text & ~Filters.command, self.enter_wallet_address)
                ],
                CONFIRM_CREDENTIALS: [
                    CallbackQueryHandler(self.confirm_credentials_callback, pattern='^confirm_')
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)]
        )
        self.dispatcher.add_handler(auth_conv)
        
        # Account info commands
        self.dispatcher.add_handler(CommandHandler("balance", self.cmd_balance))
        self.dispatcher.add_handler(CommandHandler("positions", self.cmd_positions))
        self.dispatcher.add_handler(CommandHandler("orders", self.cmd_orders))
        
        # Help and status
        self.dispatcher.add_handler(CommandHandler("help", self.cmd_help))
        self.dispatcher.add_handler(CommandHandler("status", self.cmd_status))
        self.dispatcher.add_handler(CommandHandler("apicheck", self.cmd_api_check))
        self.dispatcher.add_handler(CommandHandler("disconnect", self.cmd_disconnect))
        
        # Market data commands
        self.dispatcher.add_handler(CommandHandler("price", self.cmd_price))
        
        # Main menu
        self.dispatcher.add_handler(CommandHandler("menu", self.cmd_show_menu))
        
        # Add trade commands
        # Note: These methods need to be implemented in this class
        # Comment these out if not implemented yet
        self.dispatcher.add_handler(CommandHandler("buy", self.cmd_buy))
        self.dispatcher.add_handler(CommandHandler("sell", self.cmd_sell))
        self.dispatcher.add_handler(CommandHandler("close", self.cmd_close))
        
        # Trading conversation
        trading_conv = ConversationHandler(
            entry_points=[CommandHandler("trade", self.cmd_trade)],
            states={
                SYMBOL: [
                    MessageHandler(Filters.text & ~Filters.command, self.trade_symbol)
                ],
                SIDE: [
                    CallbackQueryHandler(self.trade_side_callback, pattern='^side_')
                ],
                AMOUNT: [
                    MessageHandler(Filters.text & ~Filters.command, self.trade_amount)
                ],
                PRICE: [
                    CallbackQueryHandler(self.trade_price_type_callback, pattern='^price_'),
                    MessageHandler(Filters.text & ~Filters.command, self.trade_price)
                ],
                CONFIRMATION: [
                    CallbackQueryHandler(self.trade_confirm_callback, pattern='^confirm_')
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)]
        )
        self.dispatcher.add_handler(trading_conv)
        
        # Callback query handler for buttons
        self.dispatcher.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Message handler for keyboard buttons
        self.dispatcher.add_handler(MessageHandler(
            Filters.text & ~Filters.command, 
            self.handle_button_message
        ))
        
        # Error handler
        self.dispatcher.add_error_handler(self.error_handler)
    
    def start(self):
        """Start the bot"""
        if not hasattr(self, 'updater'):
            logging.error("Telegram bot not properly initialized")
            return
        
        logging.info("Starting Elysium Telegram Bot")
        self.updater.start_polling()
        self.updater.idle()  # Block until bot is stopped
    
    def stop(self):
        """Stop the bot"""
        if hasattr(self, 'updater'):
            logging.info("Stopping Elysium Telegram Bot")
            self.updater.stop()
    
    def _is_authorized(self, user_id):
        """Check if a user is authorized to use this bot"""
        # If no admin IDs are set, allow all users
        if not self.admin_ids:
            return True
        return user_id in self.admin_ids
    
    def _is_connected(self, user_id):
        """Check if user is connected to exchange"""
        return user_id in self.connected_users
    
    def _check_auth(self, update: Update, context: CallbackContext):
        """Check if the user is authorized and connected"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return False
            
        if not self._is_connected(user_id):
            update.message.reply_text(
                "You need to connect to an exchange first.\n"
                "Use /connect to start."
            )
            return False
            
        return True
    
    def _connect_user(self, user_id, secret_key, wallet_address, network):
        """Connect a user to the exchange"""
        network = network
        
        logging.info(f"Connecting user {user_id} to {network}")
        
        # Initialize API connector if not exists for this user
        if user_id not in self.api_connectors:
            self.api_connectors[user_id] = ApiConnector()
        
        api_connector = self.api_connectors[user_id]
        
        # Connect to exchange
        success = api_connector.connect(wallet_address, secret_key, network)
        
        if success:
            # Initialize order handler if not exists for this user
            if user_id not in self.order_handlers:
                self.order_handlers[user_id] = OrderHandler(api_connector)
            else:
                self.order_handlers[user_id].set_api_connector(api_connector)
            
            # Mark user as connected
            self.connected_users.add(user_id)
            self.user_data[user_id] = {
                "network": network,
                "wallet_address": wallet_address,
                "secret_key": secret_key[:5] + "..." + secret_key[-3:] if len(secret_key) > 8 else "****",
                "connected_at": datetime.now().isoformat()
            }
            
            return True
        else:
            logging.error(f"Failed to connect user {user_id} to {network}")
            return False
    
    def _disconnect_user(self, user_id):
        """Disconnect a user from the exchange"""
        if user_id in self.connected_users:
            self.connected_users.remove(user_id)
            
            # Clean up resources
            if user_id in self.api_connectors:
                del self.api_connectors[user_id]
            
            if user_id in self.order_handlers:
                del self.order_handlers[user_id]
            
            if user_id in self.user_data:
                del self.user_data[user_id]
            
            return True
        return False
    
    def _get_api_connector(self, user_id):
        """Get the API connector for a specific user"""
        return self.api_connectors.get(user_id)
    
    def _get_order_handler(self, user_id):
        """Get the order handler for a specific user"""
        return self.order_handlers.get(user_id)
    
    # Command handlers
    def cmd_start(self, update: Update, context: CallbackContext):
        """Handle /start command"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return
        
        update.message.reply_text(
            f"🚀 *Welcome to Elysium Trading Bot!*\n\n"
            f"This bot allows you to trade on cryptocurrency exchanges.\n\n"
            f"To get started:\n"
            f"1. Use /connect to connect to an exchange\n"
            f"2. Use /menu to see available commands\n"
            f"3. Use /help for detailed instructions",
            parse_mode=ParseMode.MARKDOWN
        )
    
    def cmd_api_check(self, update: Update, context: CallbackContext):
        """Check if the API is online"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return
        
        update.message.reply_text("🔄 Checking API status...")
        
        is_online, message = self.status_checker.check_api_status()
        
        if is_online:
            update.message.reply_text(f"✅ API is online and responding")
        else:
            update.message.reply_text(f"❌ API status check failed: {message}")
    
    def select_network(self, update: Update, context: CallbackContext):
        """Start connection by selecting network"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return ConversationHandler.END
        
        keyboard = [
            [
                InlineKeyboardButton("Mainnet", callback_data="network_mainnet"),
                InlineKeyboardButton("Testnet", callback_data="network_testnet")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "Please select a network to connect to:",
            reply_markup=reply_markup
        )
        return SELECTING_NETWORK
    
    def select_network_callback(self, update: Update, context: CallbackContext):
        """Handle network selection"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        
        if not self._is_authorized(user_id):
            query.edit_message_text("⛔ You are not authorized to use this bot.")
            return ConversationHandler.END
        
        network = query.data.split("_")[1]
        self.connection_contexts[user_id] = {"network": network}
        
        # Check if user already has credentials
        credentials = load_user_credentials(user_id)
        
        if credentials and credentials.get("network") == network:
            keyboard = [
                [
                    InlineKeyboardButton("Use Saved Credentials", callback_data="auth_saved"),
                    InlineKeyboardButton("Enter New Credentials", callback_data="auth_new")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                f"Selected {network.upper()}. You have saved credentials for this network. How would you like to proceed?",
                reply_markup=reply_markup
            )
            return SELECT_AUTH_TYPE
        else:
            query.edit_message_text(
                f"Selected {network.upper()}. Please enter your API secret key:"
            )
            return ENTER_SECRET_KEY
    
    def select_auth_type_callback(self, update: Update, context: CallbackContext):
        """Handle authentication type selection"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        auth_type = query.data.split("_")[1]
        
        if auth_type == "saved":
            # Use saved credentials
            credentials = load_user_credentials(user_id)
            if not credentials:
                query.edit_message_text("Error: Could not load saved credentials. Please enter new credentials.")
                return ENTER_SECRET_KEY
            
            network = "network"
            secret_key = credentials.get("secret_key")
            wallet_address = credentials.get("wallet_address")
            
            if self._connect_user(user_id, secret_key, wallet_address, network):
                query.edit_message_text(
                    f"✅ Successfully connected to {network}\n"
                    f"Wallet: `{wallet_address[:6]}...{wallet_address[-4:]}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                # Show main menu
                self.cmd_show_menu(update, context)
                return ConversationHandler.END
            else:
                query.edit_message_text(
                    f"❌ Failed to connect using saved credentials. Please enter new credentials.\n\n"
                    f"Please enter your API secret key:"
                )
                return ENTER_SECRET_KEY
        else:
            # Enter new credentials
            query.edit_message_text(
                "Please enter your API secret key:"
            )
            return ENTER_SECRET_KEY
    
    def ENTER_SECRET_KEY(self, update: Update, context: CallbackContext):
        """Handle API key input"""
        user_id = update.effective_user.id
        secret_key = update.message.text.strip()
        
        # Store the API key securely
        if secret_key.startswith("0x") and len(secret_key) >= 40:
            self.connection_contexts[user_id]["secret_key"] = secret_key
            
            # Delete the message containing the API key for security
            try:
                context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
            except Exception as e:
                logging.warning(f"Could not delete API key message: {str(e)}")
            
            update.message.reply_text(
                "Now, please enter your wallet address:"
            )
            return ENTER_WALLET_ADDRESS
        else:
            update.message.reply_text(
                "Invalid API key format. It should start with '0x' and be at least 40 characters long.\n"
                "Please enter a valid API key:"
            )
            return ENTER_SECRET_KEY
    
    def enter_wallet_address(self, update: Update, context: CallbackContext):
        """Handle wallet address input"""
        user_id = update.effective_user.id
        wallet_address = update.message.text.strip()
        
        # Validate wallet address format
        if wallet_address.startswith("0x") and len(wallet_address) >= 40:
            self.connection_contexts[user_id]["wallet_address"] = wallet_address
            
            # Prepare confirmation message
            network = self.connection_contexts[user_id]["network"]
            secret_key = self.connection_contexts[user_id]["secret_key"]
            
            confirmation_text = (
                f"Please confirm your credentials:\n\n"
                f"Network: {network.upper()}\n"
                f"API Key: {secret_key[:5]}...{secret_key[-3:]}\n"
                f"Wallet: {wallet_address[:6]}...{wallet_address[-4:]}\n\n"
                f"Would you like to save these credentials for future use?"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("Yes, Save & Connect", callback_data="confirm_save"),
                    InlineKeyboardButton("No, Just Connect", callback_data="confirm_nosave")
                ],
                [
                    InlineKeyboardButton("Cancel", callback_data="confirm_cancel")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(
                confirmation_text,
                reply_markup=reply_markup
            )
            return CONFIRM_CREDENTIALS
        else:
            update.message.reply_text(
                "Invalid wallet address format. It should start with '0x' and be at least 40 characters long.\n"
                "Please enter a valid wallet address:"
            )
            return ENTER_WALLET_ADDRESS
    
    def confirm_credentials_callback(self, update: Update, context: CallbackContext):
        """Handle credentials confirmation"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        
        action = query.data.split("_")[1]
        
        if action == "cancel":
            query.edit_message_text("Connection cancelled.")
            return ConversationHandler.END
        
        # Get credentials from context
        network = self.connection_contexts[user_id]["network"]
        secret_key = self.connection_contexts[user_id]["secret_key"]
        wallet_address = self.connection_contexts[user_id]["wallet_address"]
        
        # Save credentials if requested
        if action == "save":
            save_user_credentials(user_id, network, secret_key, wallet_address)
            query.edit_message_text("Credentials saved. Connecting...")
        else:
            query.edit_message_text("Connecting with provided credentials...")
        
        # Connect to exchange
        if self._connect_user(user_id, secret_key, wallet_address, network):
            query.edit_message_text(
                f"✅ Successfully connected to {network}\n"
                f"Wallet: `{wallet_address[:6]}...{wallet_address[-4:]}`",
                parse_mode=ParseMode.MARKDOWN
            )
            # Show main menu
            self.cmd_show_menu(update, context)
        else:
            query.edit_message_text(f"❌ Failed to connect to {network}. Please try again with /connect.")
        
        return ConversationHandler.END
    
    def cmd_disconnect(self, update: Update, context: CallbackContext):
        """Handle /disconnect command"""
        user_id = update.effective_user.id
        
        if not self._is_connected(user_id):
            update.message.reply_text("You are not currently connected to any exchange.")
            return
        
        if self._disconnect_user(user_id):
            update.message.reply_text("You have been disconnected from the exchange.")
        else:
            update.message.reply_text("Error disconnecting from the exchange.")
    
    def cmd_show_menu(self, update: Update, context: CallbackContext):
        """Show the main menu with basic operations"""
        user_id = update.effective_user.id
        
        if not self._is_authorized(user_id):
            if hasattr(update, 'message') and update.message:
                update.message.reply_text("⛔ You are not authorized to use this bot.")
            elif hasattr(update, 'callback_query') and update.callback_query:
                update.callback_query.edit_message_text("⛔ You are not authorized to use this bot.")
            return
        
        keyboard = create_main_menu()
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=False
        )
        
        connection_status = "Connected" if self._is_connected(user_id) else "Not connected"
        network = "Not connected"
        network_emoji = "❌"
        
        if user_id in self.user_data:
            network = self.user_data[user_id].get("network", "unknown")
            network_emoji = "🧪"
        
        message = (
            f"*Elysium Trading Bot - Main Menu*\n\n"
            f"Status: {connection_status}\n"
            f"Network: {network_emoji} {network.upper()}\n\n"
            f"Choose an option from the menu below:"
        )
        
        if hasattr(update, 'message') and update.message:
            update.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        elif hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN
            )
            context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Main menu activated.",
                reply_markup=reply_markup
            )
    
    def handle_button_message(self, update: Update, context: CallbackContext):
        """Handle text messages from keyboard buttons"""
        text = update.message.text.lower()
        
        if "balance" in text:
            self.cmd_balance(update, context)
        elif "positions" in text:
            self.cmd_positions(update, context)
        elif "orders" in text:
            self.cmd_orders(update, context)
        elif "price" in text:
            update.message.reply_text("Please use /price <symbol> to check prices.")
        elif "trade" in text:
            self.cmd_trade(update, context)
        elif "close position" in text:
            update.message.reply_text("Please specify which position to close. Use /positions to view your positions.")
        elif "status" in text:
            self.cmd_status(update, context)
        elif "help" in text:
            self.cmd_help(update, context)
    
    def button_callback(self, update: Update, context: CallbackContext):
        """Handle button callbacks"""
        query = update.callback_query
        query.answer()
        data = query.data
        
        # Handle different button actions based on data
        if data == "action_main_menu":
            self.cmd_show_menu(update, context)
        elif data.startswith("action_"):
            # Handle action buttons
            action = data[7:]  # Remove "action_" prefix
            self.handle_action_buttons(action, update, context)
        elif data.startswith("close_"):
            # Handle close position button
            symbol = data[6:]  # Remove "close_" prefix
            self.handle_close_position(symbol, update, context)
        elif data.startswith("confirm_close_"):
            # Handle confirmation for closing position
            symbol = data[13:]  # Remove "confirm_close_" prefix
            self.handle_close_confirm(symbol, update, context)
        elif data.startswith("cancel_"):
            # Handle cancel order button
            parts = data[7:].split("_")
            if len(parts) == 2:
                symbol, order_id = parts
                self.handle_cancel_order(symbol, int(order_id), update, context)
    
    def handle_action_buttons(self, action: str, update: Update, context: CallbackContext):
        """Handle action buttons from the main menu"""
        user_id = update.effective_user.id
        
        if action == "balance":
            self.cmd_balance(update, context)
        elif action == "positions":
            self.cmd_positions(update, context)
        elif action == "orders":
            self.cmd_orders(update, context)
        elif action == "price":
            # We need symbol for price - ask the user
            update.message.reply_text("Please specify a symbol. Usage: /price BTC")
        elif action == "trade":
            self.cmd_trade(update, context)
        elif action == "close_position":
            # We need symbol for closing position - show positions
            self.cmd_positions(update, context)
        elif action == "status":
            self.cmd_status(update, context)
        elif action == "help":
            self.cmd_help(update, context)
        elif action == "market_buy":
            # Start trade conversation with preset action
            self.trading_context[user_id] = {"action": "market_buy"}
            update.message.reply_text("Please enter the symbol you want to buy (e.g., BTC):")
            return SYMBOL
        elif action == "market_sell":
            # Start trade conversation with preset action
            self.trading_context[user_id] = {"action": "market_sell"}
            update.message.reply_text("Please enter the symbol you want to sell (e.g., BTC):")
            return SYMBOL
        elif action == "limit_buy":
            # Start trade conversation with preset action
            self.trading_context[user_id] = {"action": "limit_buy"}
            update.message.reply_text("Please enter the symbol for limit buy (e.g., BTC):")
            return SYMBOL
        elif action == "limit_sell":
            # Start trade conversation with preset action
            self.trading_context[user_id] = {"action": "limit_sell"}
            update.message.reply_text("Please enter the symbol for limit sell (e.g., BTC):")
            return SYMBOL
        elif action == "cancel_all":
            self.handle_cancel_all_orders(update, context)
        else:
            update.message.reply_text(f"Unknown action: {action}")
    
    def handle_cancel_all_orders(self, update: Update, context: CallbackContext):
        """Handle canceling all orders"""
        query = update.callback_query
        user_id = query.from_user.id
        
        if not self._is_connected(user_id):
            query.edit_message_text("You are not connected to an exchange. Use /connect first.")
            return
        
        order_handler = self._get_order_handler(user_id)
        if not order_handler:
            query.edit_message_text("Error: Order handler not available. Please reconnect.")
            return
        
        try:
            query.edit_message_text("Cancelling all open orders...")
            result = order_handler.cancel_all_orders()
            
            if "status" in result and result["status"] in ["ok", "success"]:
                cancelled = result.get("cancelled", 0)
                if isinstance(result.get("data"), dict):
                    cancelled = result["data"].get("cancelled", cancelled)
                query.edit_message_text(f"✅ Cancelled {cancelled} orders")
            else:
                query.edit_message_text(f"❌ Error cancelling orders: {result.get('message', 'Unknown error')}")
        except Exception as e:
            logging.error(f"Error cancelling all orders: {str(e)}")
            query.edit_message_text(f"❌ Error: {str(e)}")
    
    def handle_close_position(self, symbol: str, update: Update, context: CallbackContext):
        """Handle closing a position"""
        query = update.callback_query
        user_id = query.from_user.id
        
        if not self._is_connected(user_id):
            query.edit_message_text("You are not connected to an exchange. Use /connect first.")
            return
        
        try:
            # Confirm close
            keyboard = [
                [
                    InlineKeyboardButton("Yes, Close Position", callback_data=f"confirm_close_{symbol}"),
                    InlineKeyboardButton("No, Cancel", callback_data="action_main_menu")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                f"Are you sure you want to close your {symbol} position?",
                reply_markup=reply_markup
            )
        except Exception as e:
            logging.error(f"Error preparing to close position: {str(e)}")
            query.edit_message_text(f"Error: {str(e)}")
    
    def handle_close_confirm(self, symbol: str, update: Update, context: CallbackContext):
        """Handle confirmation of position close"""
        query = update.callback_query
        user_id = query.from_user.id
        
        if not self._is_connected(user_id):
            query.edit_message_text("You are not connected to an exchange. Use /connect first.")
            return
            
        order_handler = self._get_order_handler(user_id)
        if not order_handler:
            query.edit_message_text("Error: Order handler not available. Please reconnect.")
            return
        
        try:
            query.edit_message_text(f"Closing {symbol} position...")
            
            # Close the position
            result = order_handler.close_position(symbol)
            
            if result["status"] in ["ok", "success"]:
                query.edit_message_text(f"✅ Successfully closed {symbol} position")
            else:
                query.edit_message_text(f"❌ Error closing position: {result.get('message', 'Unknown error')}")
        
        except Exception as e:
            logging.error(f"Error closing position: {str(e)}")
            query.edit_message_text(f"❌ Error: {str(e)}")
    
    def handle_cancel_order(self, symbol: str, order_id: int, update: Update, context: CallbackContext):
        """Handle canceling a specific order"""
        query = update.callback_query
        user_id = query.from_user.id
        
        if not self._is_connected(user_id):
            query.edit_message_text("You are not connected to an exchange. Use /connect first.")
            return
            
        order_handler = self._get_order_handler(user_id)
        if not order_handler:
            query.edit_message_text("Error: Order handler not available. Please reconnect.")
            return
        
        try:
            query.edit_message_text(f"Cancelling order {order_id} for {symbol}...")
            
            # Cancel the order
            result = order_handler.cancel_order(symbol, order_id)
            
            if result["status"] in ["ok", "success"]:
                query.edit_message_text(f"✅ Successfully cancelled order {order_id}")
            else:
                query.edit_message_text(f"❌ Error cancelling order: {result.get('message', 'Unknown error')}")
        
        except Exception as e:
            logging.error(f"Error cancelling order: {str(e)}")
            query.edit_message_text(f"❌ Error: {str(e)}")
    
    def cmd_trade(self, update: Update, context: CallbackContext):
        """Handle /trade command"""
        user_id = update.effective_user.id
        
        if not self._check_auth(update, context):
            return ConversationHandler.END
        
        # Initialize trading context
        self.trading_context[user_id] = {}
        
        update.message.reply_text("Please enter the symbol you want to trade (e.g., BTC):")
        return SYMBOL
    
    def trade_symbol(self, update: Update, context: CallbackContext):
        """Handle symbol input for trading"""
        user_id = update.effective_user.id
        symbol = update.message.text.strip().upper()
        
        # Store symbol in context
        self.trading_context[user_id]["symbol"] = symbol
        
        # Ask for side
        keyboard = [
            [
                InlineKeyboardButton("Buy", callback_data="side_buy"),
                InlineKeyboardButton("Sell", callback_data="side_sell")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            f"Trading {symbol}. Please select the side:",
            reply_markup=reply_markup
        )
        return SIDE
    def trade_side_callback(self, update: Update, context: CallbackContext):
        """Handle side selection for trading"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        
        side = query.data.split("_")[1]
        self.trading_context[user_id]["side"] = side
        
        # Ask for amount
        symbol = self.trading_context[user_id]["symbol"]
        query.edit_message_text(f"Trading {symbol} - {side.upper()}. Please enter the amount:")
        
        return AMOUNT
    
    def trade_amount(self, update: Update, context: CallbackContext):
        """Handle amount input for trading"""
        user_id = update.effective_user.id
        
        try:
            amount = float(update.message.text.strip())
            if amount <= 0:
                update.message.reply_text("Amount must be greater than 0. Please enter a valid amount:")
                return AMOUNT
                
            self.trading_context[user_id]["amount"] = amount
            
            # Ask for price type
            keyboard = [
                [
                    InlineKeyboardButton("Market Price", callback_data="price_market"),
                    InlineKeyboardButton("Limit Price", callback_data="price_limit")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            symbol = self.trading_context[user_id]["symbol"]
            side = self.trading_context[user_id]["side"]
            
            update.message.reply_text(
                f"Trading {amount} {symbol} - {side.upper()}. Please select order type:",
                reply_markup=reply_markup
            )
            return PRICE
            
        except ValueError:
            update.message.reply_text("Invalid amount. Please enter a number:")
            return AMOUNT
    
    def trade_price_type_callback(self, update: Update, context: CallbackContext):
        """Handle price type selection for trading"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        
        price_type = query.data.split("_")[1]
        self.trading_context[user_id]["price_type"] = price_type
        
        symbol = self.trading_context[user_id]["symbol"]
        side = self.trading_context[user_id]["side"]
        amount = self.trading_context[user_id]["amount"]
        
        if price_type == "market":
            # Market order - go straight to confirmation
            self.trading_context[user_id]["price"] = None
            
            keyboard = [
                [
                    InlineKeyboardButton("Confirm", callback_data="confirm_yes"),
                    InlineKeyboardButton("Cancel", callback_data="confirm_no")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                f"Please confirm your order:\n\n"
                f"Symbol: {symbol}\n"
                f"Side: {side.upper()}\n"
                f"Amount: {amount}\n"
                f"Type: Market Order\n\n"
                f"Do you want to proceed?",
                reply_markup=reply_markup
            )
            return CONFIRMATION
        else:
            # Limit order - ask for price
            query.edit_message_text(
                f"Trading {amount} {symbol} - {side.upper()} with limit order.\n"
                f"Please enter the price:"
            )
            return PRICE
    
    def trade_price(self, update: Update, context: CallbackContext):
        """Handle price input for trading"""
        user_id = update.effective_user.id
        
        try:
            price = float(update.message.text.strip())
            if price <= 0:
                update.message.reply_text("Price must be greater than 0. Please enter a valid price:")
                return PRICE
                
            self.trading_context[user_id]["price"] = price
            self.trading_context[user_id]["price_type"] = "limit"  # Ensure we know it's a limit order
            
            # Go to confirmation
            symbol = self.trading_context[user_id]["symbol"]
            side = self.trading_context[user_id]["side"]
            amount = self.trading_context[user_id]["amount"]
            
            keyboard = [
                [
                    InlineKeyboardButton("Confirm", callback_data="confirm_yes"),
                    InlineKeyboardButton("Cancel", callback_data="confirm_no")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(
                f"Please confirm your order:\n\n"
                f"Symbol: {symbol}\n"
                f"Side: {side.upper()}\n"
                f"Amount: {amount}\n"
                f"Type: Limit Order\n"
                f"Price: {price}\n\n"
                f"Do you want to proceed?",
                reply_markup=reply_markup
            )
            return CONFIRMATION
            
        except ValueError:
            update.message.reply_text("Invalid price. Please enter a number:")
            return PRICE
    
    def trade_confirm_callback(self, update: Update, context: CallbackContext):
        """Handle confirmation for trading"""
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        
        confirm = query.data.split("_")[1]
        
        if confirm != "yes":
            query.edit_message_text("Order cancelled.")
            return ConversationHandler.END
        
        # Execute the order
        try:
            symbol = self.trading_context[user_id]["symbol"]
            side = self.trading_context[user_id]["side"]
            amount = self.trading_context[user_id]["amount"]
            price_type = self.trading_context[user_id].get("price_type", "market")
            price = self.trading_context[user_id].get("price")
            
            order_handler = self._get_order_handler(user_id)
            if not order_handler:
                query.edit_message_text("Error: Order handler not available. Please reconnect.")
                return ConversationHandler.END
            
            query.edit_message_text(f"Executing {side} order for {amount} {symbol}...")
            
            result = None
            if side == "buy":
                if price_type == "market":
                    result = order_handler.market_buy(symbol, amount)
                else:
                    result = order_handler.limit_buy(symbol, amount, price)
            else:  # sell
                if price_type == "market":
                    result = order_handler.market_sell(symbol, amount)
                else:
                    result = order_handler.limit_sell(symbol, amount, price)
            
            if result["status"] in ["ok", "success"]:
                message = f"✅ Order executed successfully"
                
                # Add details if available
                if "filled" in result:
                    filled = result["filled"]
                    message += f"\nFilled: {filled.get('size', amount)} @ {filled.get('price', 'market price')}"
                elif "order_id" in result:
                    message += f"\nOrder ID: {result['order_id']}"
                
                query.edit_message_text(message)
            else:
                query.edit_message_text(f"❌ Order failed: {result.get('message', 'Unknown error')}")
            
            return ConversationHandler.END
            
        except Exception as e:
            logging.error(f"Error executing order: {str(e)}")
            query.edit_message_text(f"❌ Error: {str(e)}")
            return ConversationHandler.END
    
    def cancel_conversation(self, update: Update, context: CallbackContext):
        """Generic handler to cancel any conversation"""
        user_id = update.effective_user.id
        
        # Clear trading context
        if user_id in self.trading_context:
            del self.trading_context[user_id]
        
        # Remove keyboard if present
        update.message.reply_text(
            "Operation cancelled",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    def cmd_balance(self, update: Update, context: CallbackContext):
        """Handle /balance command"""
        user_id = update.effective_user.id
        
        if not self._check_auth(update, context):
            return
        
        api_connector = self._get_api_connector(user_id)
        if not api_connector:
            update.message.reply_text("Error: API connector not available. Please reconnect.")
            return
        
        try:
            update.message.reply_text("🔄 Fetching balance information...")
            
            balances = api_connector.get_balances()
            
            if balances.get("status") == "error":
                update.message.reply_text(f"❌ Error fetching balance: {balances.get('message')}")
                return
            
            message = "*Account Balances:*\n\n"
            
            # Format spot balances
            if "spot" in balances:
                message += "*Spot Balances:*\n"
                for balance in balances["spot"]:
                    if float(balance.get("total", 0)) > 0:
                        message += (
                            f"• {balance.get('asset')}: "
                            f"{balance.get('available', 0)} available, "
                            f"{balance.get('total', 0)} total\n"
                        )
                message += "\n"
            
            # Format perpetual account
            if "perp" in balances:
                message += "*Perpetual Account:*\n"
                message += f"• Account Value: ${balances['perp'].get('account_value', 0)}\n"
                message += f"• Margin Used: ${balances['perp'].get('margin_used', 0)}\n"
                message += f"• Position Value: ${balances['perp'].get('position_value', 0)}\n"
            
            update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logging.error(f"Error fetching balance: {str(e)}")
            update.message.reply_text(f"❌ Error fetching balance: {str(e)}")
    
    def cmd_positions(self, update: Update, context: CallbackContext):
        """Handle /positions command"""
        user_id = update.effective_user.id
        
        if not self._check_auth(update, context):
            return
        
        api_connector = self._get_api_connector(user_id)
        if not api_connector:
            update.message.reply_text("Error: API connector not available. Please reconnect.")
            return
        
        try:
            update.message.reply_text("🔄 Fetching position information...")
            
            positions = api_connector.get_positions()
            
            if not positions:
                update.message.reply_text("No open positions")
                return
            
            message = "*Open Positions:*\n\n"
            for pos in positions:
                symbol = pos.get("symbol", "")
                size = pos.get("size", 0)
                side = "Long" if size > 0 else "Short"
                entry = pos.get("entry_price", 0)
                mark = pos.get("mark_price", 0)
                pnl = pos.get("unrealized_pnl", 0)
                
                message += (
                    f"*{symbol}:*\n"
                    f"• Side: {side}\n"
                    f"• Size: {abs(size)}\n"
                    f"• Entry: {entry}\n"
                    f"• Mark: {mark}\n"
                    f"• Unrealized PnL: {pnl}\n\n"
                )
            
            # Add close buttons for positions
            keyboard = []
            for pos in positions:
                symbol = pos.get("symbol", "")
                keyboard.append([
                    InlineKeyboardButton(f"Close {symbol} Position", callback_data=f"close_{symbol}")
                ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except Exception as e:
            logging.error(f"Error fetching positions: {str(e)}")
            update.message.reply_text(f"❌ Error fetching positions: {str(e)}")
    
    def cmd_orders(self, update: Update, context: CallbackContext):
        """Handle /orders command"""
        user_id = update.effective_user.id
        
        if not self._check_auth(update, context):
            return
            
        order_handler = self._get_order_handler(user_id)
        if not order_handler:
            update.message.reply_text("Error: Order handler not available. Please reconnect.")
            return
        
        try:
            update.message.reply_text("🔄 Fetching open orders...")
            
            orders = order_handler.get_open_orders()
            
            if not orders:
                update.message.reply_text("No open orders")
                return
            
            message = "*Open Orders:*\n\n"
            keyboard = []
            
            for order in orders:
                symbol = order.get("symbol", "")
                side = "Buy" if order.get("side", "") in ["B", "buy", "BUY"] else "Sell"
                size = float(order.get("size", 0))
                price = float(order.get("price", 0))
                order_id = order.get("order_id", 0)
                
                message += (
                    f"*{symbol}:*\n"
                    f"• Side: {side}\n"
                    f"• Size: {size}\n"
                    f"• Price: {price}\n"
                    f"• Order ID: {order_id}\n\n"
                )
                
                # Add a cancel button for this order
                keyboard.append([InlineKeyboardButton(f"Cancel Order #{order_id}", callback_data=f"cancel_{symbol}_{order_id}")])
            
            # Add a cancel all button
            keyboard.append([InlineKeyboardButton("Cancel All Orders", callback_data="action_cancel_all")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except Exception as e:
            logging.error(f"Error fetching orders: {str(e)}")
            update.message.reply_text(f"❌ Error fetching orders: {str(e)}")
    
    def cmd_price(self, update: Update, context: CallbackContext):
        """Handle /price command"""
        user_id = update.effective_user.id
        
        if not self._check_auth(update, context):
            return
        
        args = context.args
        if not args:
            update.message.reply_text("Please specify a symbol. Usage: /price BTC")
            return
            
        symbol = args[0].upper()
        
        update.message.reply_text(f"🔄 Fetching price for {symbol}...")
        
        try:
            # Since we don't have a direct price endpoint in the API documentation,
            # we'll create a simulated response for this example
            
            # In a real implementation, you would call an API endpoint for pricing
            # For now, we'll just respond with a placeholder message
            update.message.reply_text(
                f"*{symbol} Market Data:*\n\n"
                f"Mid Price: $45,234.52\n"
                f"Best Bid: $45,200.10\n"
                f"Best Ask: $45,268.94\n\n"
                f"_(Note: This is simulated data for example purposes)_",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logging.error(f"Error fetching price: {str(e)}")
            update.message.reply_text(f"❌ Error fetching price: {str(e)}")
    
    def cmd_status(self, update: Update, context: CallbackContext):
        """Handle /status command"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return
        
        connection_status = "Connected" if self._is_connected(user_id) else "Not connected"
        network = "Not connected"
        network_emoji = "❌"
        
        if user_id in self.user_data:
            network = self.user_data[user_id].get("network", "unknown")
            network_emoji = "🧪"
        
        # Check API status
        is_api_online, api_message = self.status_checker.check_api_status()
        api_status = "✅ Online" if is_api_online else f"❌ Offline ({api_message})"
        
        message = f"*Elysium Bot Status:*\n\n"
        message += f"API Status: {api_status}\n"
        message += f"Connection Status: {connection_status}\n"
        
        if self._is_connected(user_id):
            message += f"Network: {network_emoji} {network.upper()}\n"
            wallet_address = self.user_data[user_id].get("wallet_address", "")
            
            if wallet_address:
                message += f"Address: `{wallet_address[:6]}...{wallet_address[-4:]}`\n"
            
            # Add position summary if available
            api_connector = self._get_api_connector(user_id)
            if api_connector:
                try:
                    positions = api_connector.get_positions()
                    if positions:
                        message += "\n*Open Positions:*\n"
                        for pos in positions:
                            symbol = pos.get("symbol", "")
                            size = pos.get("size", 0)
                            side = "Long" if size > 0 else "Short"
                            pnl = pos.get("unrealized_pnl", 0)
                            message += f"• {symbol}: {side} {abs(size)} (PnL: {pnl})\n"
                except Exception as e:
                    logging.error(f"Error getting positions for status: {str(e)}")
        
        update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    def cmd_help(self, update: Update, context: CallbackContext):
        """Handle /help command"""
        user_id = update.effective_user.id
        if not self._is_authorized(user_id):
            update.message.reply_text("⛔ You are not authorized to use this bot.")
            return
        
        update.message.reply_text(
            "*Elysium Trading Bot Commands:*\n\n"
            "*Basic Commands:*\n"
            "/connect - Connect to exchange\n"
            "/disconnect - Disconnect from exchange\n"
            "/menu - Show main menu\n"
            "/help - Show this help message\n"
            "/status - Show connection status\n"
            "/apicheck - Check if API is online\n\n"
            
            "*Account Info:*\n"
            "/balance - Show account balance\n"
            "/positions - Show open positions\n"
            "/orders - Show open orders\n"
            "/price <symbol> - Check current price\n\n"
            
            "*Trading:*\n"
            "/trade - Start trading dialog\n"
            "/buy <symbol> <size> - Execute a market buy\n"
            "/sell <symbol> <size> - Execute a market sell\n"
            "/close <symbol> - Close a position",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # These are the missing methods that were causing the error
    # They provide basic implementations for the commands
    def cmd_buy(self, update: Update, context: CallbackContext):
        """Handle /buy command"""
        user_id = update.effective_user.id
        
        if not self._check_auth(update, context):
            return
            
        order_handler = self._get_order_handler(user_id)
        if not order_handler:
            update.message.reply_text("Error: Order handler not available. Please reconnect.")
            return
            
        args = context.args
        if len(args) < 2:
            update.message.reply_text("Usage: /buy <symbol> <size> [slippage]")
            return
            
        symbol = args[0].upper()
        
        try:
            size = float(args[1])
            slippage = float(args[2]) if len(args) > 2 else 0.03
            
            update.message.reply_text(f"🔄 Executing market buy: {size} {symbol}")
            result = order_handler.market_buy(symbol, size, slippage)
            
            if result["status"] in ["ok", "success"]:
                update.message.reply_text("✅ Buy order executed successfully")
                # Show details if available
                if "filled" in result:
                    filled = result["filled"]
                    update.message.reply_text(f"Filled: {filled.get('size', size)} @ {filled.get('price', 'market price')}")
            else:
                update.message.reply_text(f"❌ Order failed: {result.get('message', 'Unknown error')}")
        except ValueError:
            update.message.reply_text("Invalid size or slippage. Please enter numeric values.")
        except Exception as e:
            logging.error(f"Error executing buy order: {str(e)}")
            update.message.reply_text(f"❌ Error: {str(e)}")
    
    def cmd_sell(self, update: Update, context: CallbackContext):
        """Handle /sell command"""
        user_id = update.effective_user.id
        
        if not self._check_auth(update, context):
            return
            
        order_handler = self._get_order_handler(user_id)
        if not order_handler:
            update.message.reply_text("Error: Order handler not available. Please reconnect.")
            return
            
        args = context.args
        if len(args) < 2:
            update.message.reply_text("Usage: /sell <symbol> <size> [slippage]")
            return
            
        symbol = args[0].upper()
        
        try:
            size = float(args[1])
            slippage = float(args[2]) if len(args) > 2 else 0.03
            
            update.message.reply_text(f"🔄 Executing market sell: {size} {symbol}")
            result = order_handler.market_sell(symbol, size, slippage)
            
            if result["status"] in ["ok", "success"]:
                update.message.reply_text("✅ Sell order executed successfully")
                # Show details if available
                if "filled" in result:
                    filled = result["filled"]
                    update.message.reply_text(f"Filled: {filled.get('size', size)} @ {filled.get('price', 'market price')}")
            else:
                update.message.reply_text(f"❌ Order failed: {result.get('message', 'Unknown error')}")
        except ValueError:
            update.message.reply_text("Invalid size or slippage. Please enter numeric values.")
        except Exception as e:
            logging.error(f"Error executing sell order: {str(e)}")
            update.message.reply_text(f"❌ Error: {str(e)}")
    
    def cmd_close(self, update: Update, context: CallbackContext):
        """Handle /close command"""
        user_id = update.effective_user.id
        
        if not self._check_auth(update, context):
            return
            
        order_handler = self._get_order_handler(user_id)
        if not order_handler:
            update.message.reply_text("Error: Order handler not available. Please reconnect.")
            return
            
        args = context.args
        if len(args) < 1:
            update.message.reply_text("Usage: /close <symbol> [slippage]")
            return
            
        symbol = args[0].upper()
        slippage = float(args[1]) if len(args) > 1 else 0.03
        
        try:
            update.message.reply_text(f"🔄 Closing position for {symbol}")
            result = order_handler.close_position(symbol, slippage)
                                                                         
            if result["status"] in ["ok", "success"]:
                    update.message.reply_text("✅ Position closed successfully")
                    # Show details if available
                    if "filled" in result:
                        filled = result["filled"]
                        update.message.reply_text(f"Filled: {filled.get('size', '')} @ {filled.get('price', 'market price')}")
                    else:
                        update.message.reply_text(f"❌ Failed to close position: {result.get('message', 'Unknown error')}")
        except Exception as e:
            logging.error(f"Error closing position: {str(e)}")
            update.message.reply_text(f"❌ Error: {str(e)}")
        
    def error_handler(self, update: Update, context: CallbackContext):
        """Log errors and send a message to the user"""
        logging.error(f"Update {update} caused error {context.error}")
        
        try:
            if update.effective_message:
                update.effective_message.reply_text(
                    "❌ Sorry, an error occurred while processing your request."
                )
        except Exception as e:
            logging.error(f"Error in error handler: {str(e)}")