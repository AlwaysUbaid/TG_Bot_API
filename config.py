import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Bot Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# API Configuration
API_BASE_URL = "https://elysium-api-tg.onrender.com" 

# Bot Settings
SESSION_TIMEOUT = 3600  # Automatically clear credentials after 1 hour

# API Endpoints (based on the OpenAPI spec)
API_ENDPOINTS = {
    # Connection
    'connect': '/connect',
    
    # Account info
    'balances': '/balances',
    'open_orders': '/open-orders',
    
    # Spot trading
    'spot_market_buy': '/api/v1/spot/market-buy',
    'spot_market_sell': '/api/v1/spot/market-sell',
    'spot_limit_buy': '/api/v1/spot/limit-buy',
    'spot_limit_sell': '/api/v1/spot/limit-sell',
    'spot_cancel_order': '/api/v1/spot/cancel-order',
    'spot_cancel_all': '/api/v1/spot/cancel-all-orders',
    
    # Perpetual trading
    'perp_market_buy': '/api/v1/perp/market-buy',
    'perp_market_sell': '/api/v1/perp/market-sell',
    'perp_limit_buy': '/api/v1/perp/limit-buy',
    'perp_limit_sell': '/api/v1/perp/limit-sell',
    'perp_close_position': '/api/v1/perp/close-position',
    'perp_set_leverage': '/api/v1/perp/set-leverage',
}

# User messages
MESSAGES = {
    'welcome': "Welcome to the Elysium Trading Bot! Let's set up your connection.",
    'ask_network': "Please select the network to connect to:",
    'ask_wallet': "Please enter your wallet address (e.g., 0x123...):",
    'ask_secret': "Now, please provide your secret key (this will only be stored temporarily):",
    'warn_secret': "⚠️ CAUTION: Never share your secret key with anyone else! This bot stores it only in memory and clears it after timeout.",
    'conn_success': "Successfully connected to {}! You can now use trading commands.",
    'conn_error': "Failed to connect: {}. Please try again.",
    'session_expired': "Your session has expired. Please reconnect with /connect",
    'not_connected': "You're not connected. Please use /connect first.",
    'help': "Available commands:\n"
            "/start - Start the bot and see introduction\n"
            "/connect - Connect to the trading platform\n"
            "/balance - Check your account balances\n"
            "/orders - View your open orders\n"
            "/spot - Spot trading options\n"
            "/perp - Perpetual trading options\n"
            "/help - Show this help message",
}