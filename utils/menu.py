# Menu generation for interfaces
"""Menu helpers for Elysium Trading Platform"""

from typing import List, Dict
from telegram import KeyboardButton

def create_main_menu() -> List[List[KeyboardButton]]:
    """
    Create the main menu keyboard layout
    
    Returns:
        List of keyboard button rows
    """
    return [
        [KeyboardButton("💰 Balance"), KeyboardButton("📊 Positions")],
        [KeyboardButton("📝 Orders"), KeyboardButton("📈 Price")],
        [KeyboardButton("🛒 Trade"), KeyboardButton("❌ Close Position")],
        [KeyboardButton("🔄 Status"), KeyboardButton("❔ Help")]
    ]

def create_trade_menu() -> List[List[KeyboardButton]]:
    """
    Create the trading submenu keyboard layout
    
    Returns:
        List of keyboard button rows
    """
    return [
        [KeyboardButton("📈 Market Buy"), KeyboardButton("📉 Market Sell")],
        [KeyboardButton("📊 Limit Buy"), KeyboardButton("📋 Limit Sell")],
        [KeyboardButton("🏗️ Advanced Orders"), KeyboardButton("↩️ Back to Main Menu")]
    ]

def create_advanced_menu() -> List[List[KeyboardButton]]:
    """
    Create the advanced orders submenu keyboard layout
    
    Returns:
        List of keyboard button rows
    """
    return [
        [KeyboardButton("📊 Scaled Orders"), KeyboardButton("⏱️ TWAP Orders")],
        [KeyboardButton("🔄 Market Aware Orders"), KeyboardButton("↩️ Back to Trading")]
    ]

def create_admin_menu() -> List[List[KeyboardButton]]:
    """
    Create the admin menu keyboard layout
    
    Returns:
        List of keyboard button rows
    """
    return [
        [KeyboardButton("👥 Manage Users"), KeyboardButton("🔧 Bot Settings")],
        [KeyboardButton("📊 Usage Statistics"), KeyboardButton("🔄 API Status")],
        [KeyboardButton("↩️ Back to Main Menu")]
    ]