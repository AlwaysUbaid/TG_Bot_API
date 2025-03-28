# API URLs and constants
"""Constants for the Elysium API"""

# Base API URL
BASE_API_URL = "https://elysium-api-tg.onrender.com"

# Endpoints
ENDPOINTS = {
    # Root/Health check
    "root": "/",
    
    # Connect
    "connect": "/connect",
    
    # Account info
    "balances": "/balances",
    "open_orders": "/open-orders",
    
    # Spot endpoints
    "market_buy": "/api/v1/spot/market-buy",
    "market_sell": "/api/v1/spot/market-sell",
    "limit_buy": "/api/v1/spot/limit-buy",
    "limit_sell": "/api/v1/spot/limit-sell",
    "cancel_order": "/api/v1/spot/cancel-order",
    "cancel_all_orders": "/api/v1/spot/cancel-all-orders",
    
    # Perpetual endpoints
    "perp_market_buy": "/api/v1/perp/market-buy",
    "perp_market_sell": "/api/v1/perp/market-sell",
    "perp_limit_buy": "/api/v1/perp/limit-buy",
    "perp_limit_sell": "/api/v1/perp/limit-sell",
    "close_position": "/api/v1/perp/close-position",
    "set_leverage": "/api/v1/perp/set-leverage",
    
    # Scaled order endpoints
    "scaled_orders": "/api/v1/scaled/scaled-orders",
    "perp_scaled_orders": "/api/v1/scaled/perp-scaled-orders",
    "market_aware_scaled_buy": "/api/v1/scaled/market-aware-scaled-buy",
    "market_aware_scaled_sell": "/api/v1/scaled/market-aware-scaled-sell",
}

# Default parameters
DEFAULT_SLIPPAGE = 0.03  # 3% slippage
DEFAULT_LEVERAGE = 1     # 1x leverage

# User data directory
DATA_DIR = "user_data"

# States for conversation handlers
# Auth states
SELECTING_NETWORK, SELECT_AUTH_TYPE, ENTER_CREDENTIALS = range(3)
ENTER_SECRET_KEY, ENTER_WALLET_ADDRESS, CONFIRM_CREDENTIALS = range(3, 6)

# Trading states
SYMBOL, SIDE, AMOUNT, PRICE, CONFIRMATION = range(6, 11)