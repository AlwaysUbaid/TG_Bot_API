# Trading presets
"""Preset configurations for Elysium Trading Platform"""

from typing import Dict, Any, List

# Trading presets for quick access
TRADING_PRESETS = {
    # Market Buying Presets
    "buy_small": {
        "name": "Small Buy",
        "description": "Small market buy order",
        "side": "buy",
        "size": 0.001,
        "type": "market"
    },
    "buy_medium": {
        "name": "Medium Buy",
        "description": "Medium market buy order",
        "side": "buy",
        "size": 0.01,
        "type": "market"
    },
    "buy_large": {
        "name": "Large Buy",
        "description": "Large market buy order",
        "side": "buy",
        "size": 0.1,
        "type": "market"
    },
    
    # Market Selling Presets
    "sell_small": {
        "name": "Small Sell",
        "description": "Small market sell order",
        "side": "sell",
        "size": 0.001,
        "type": "market"
    },
    "sell_medium": {
        "name": "Medium Sell",
        "description": "Medium market sell order",
        "side": "sell",
        "size": 0.01,
        "type": "market"
    },
    "sell_large": {
        "name": "Large Sell",
        "description": "Large market sell order",
        "side": "sell",
        "size": 0.1,
        "type": "market"
    },
    
    # Limit Order Presets
    "limit_buy_1pct": {
        "name": "Limit Buy 1%",
        "description": "Limit buy order 1% below market price",
        "side": "buy",
        "size": 0.01,
        "type": "limit", 
        "price_offset": -0.01  # 1% below market
    },
    "limit_buy_2pct": {
        "name": "Limit Buy 2%",
        "description": "Limit buy order 2% below market price",
        "side": "buy",
        "size": 0.01,
        "type": "limit",
        "price_offset": -0.02  # 2% below market
    },
    "limit_sell_1pct": {
        "name": "Limit Sell 1%",
        "description": "Limit sell order 1% above market price",
        "side": "sell",
        "size": 0.01,
        "type": "limit",
        "price_offset": 0.01  # 1% above market
    },
    "limit_sell_2pct": {
        "name": "Limit Sell 2%",
        "description": "Limit sell order 2% above market price",
        "side": "sell",
        "size": 0.01,
        "type": "limit",
        "price_offset": 0.02  # 2% above market
    }
}

# Scaled order presets
SCALED_ORDER_PRESETS = {
    "dca_buy": {
        "name": "DCA Buy",
        "description": "Dollar-cost averaging buy",
        "side": "buy",
        "num_orders": 5,
        "total_size": 0.05, 
        "price_range_pct": 0.1,  # 10% below market
        "skew": 0  # Equal distribution
    },
    "take_profit": {
        "name": "Take Profit",
        "description": "Take profit with multiple sell orders",
        "side": "sell",
        "num_orders": 5,
        "total_size": 0.05,
        "price_range_pct": 0.1,  # 10% above market
        "skew": 0.5  # Weighted towards lower prices
    },
    "value_buy": {
        "name": "Value Buy",
        "description": "Buy more at lower prices",
        "side": "buy",
        "num_orders": 5,
        "total_size": 0.05,
        "price_range_pct": 0.1,  # 10% below market
        "skew": 0.5  # Weighted towards lower prices
    },
    "profit_ladder": {
        "name": "Profit Ladder",
        "description": "Sell more at higher prices",
        "side": "sell",
        "num_orders": 5,
        "total_size": 0.05,
        "price_range_pct": 0.15,  # 15% above market
        "skew": -0.5  # Weighted towards higher prices
    }
}

# Default configuration for new users
DEFAULT_USER_CONFIG = {
    "default_slippage": 0.02,  # 2% default slippage
    "default_leverage": 1,     # 1x default leverage
    "trading_pairs": ["BTC", "ETH", "SOL", "AVAX", "ARB"],  # Default trading pairs
    "notifications": {
        "order_filled": True,
        "position_closed": True,
        "price_alerts": False
    }
}

def get_preset(preset_id: str) -> Dict[str, Any]:
    """
    Get a preset configuration by ID
    
    Args:
        preset_id: ID of the preset
        
    Returns:
        Preset configuration dict or empty dict if not found
    """
    if preset_id in TRADING_PRESETS:
        return TRADING_PRESETS[preset_id]
    
    if preset_id in SCALED_ORDER_PRESETS:
        return SCALED_ORDER_PRESETS[preset_id]
    
    return {}

def get_all_presets() -> Dict[str, Dict[str, Any]]:
    """
    Get all presets
    
    Returns:
        Dict of all presets
    """
    return {
        "trading": TRADING_PRESETS,
        "scaled": SCALED_ORDER_PRESETS
    }

def get_preset_list() -> List[Dict[str, Any]]:
    """
    Get a list of all available presets
    
    Returns:
        List of presets with id and name
    """
    preset_list = []
    
    # Add trading presets
    for preset_id, preset in TRADING_PRESETS.items():
        preset_list.append({
            "id": preset_id,
            "name": preset["name"],
            "description": preset["description"],
            "type": "trading"
        })
    
    # Add scaled order presets
    for preset_id, preset in SCALED_ORDER_PRESETS.items():
        preset_list.append({
            "id": preset_id,
            "name": preset["name"],
            "description": preset["description"],
            "type": "scaled"
        })
    
    return preset_list