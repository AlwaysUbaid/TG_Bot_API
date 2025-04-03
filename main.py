import asyncio
import logging
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ConversationHandler, filters
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

from config import TELEGRAM_TOKEN

from handlers import (
    start_command, connect_command, help_command,
    balance_command, orders_command, spot_command, perp_command, scaled_command,
    wallet_address_input, secret_key_input, network_selection,
    trading_action_handler, scaled_action_handler, symbol_input_handler, amount_input_handler,
    price_input_handler, leverage_input_handler, slippage_input_handler,
    confirm_order_handler, cancel_handler, status_command,
    min_price_input_handler, max_price_input_handler, num_orders_input_handler,
    min_distance_input_handler, max_distance_input_handler,
     # Grid trading handlers
    grid_command, grid_action_handler, grid_select_handler, grid_market_type_handler,
    grid_symbol_handler, grid_lower_price_handler, grid_upper_price_handler,
    grid_num_levels_handler, grid_investment_handler, grid_leverage_handler,
    grid_take_profit_handler, grid_stop_loss_handler, grid_confirm_handler,
    grid_start_now_handler, grid_list_handler, grid_status_handler,
    WALLET_ADDRESS, SECRET_KEY, NETWORK_SELECTION,
    SPOT_ACTION, PERP_ACTION, SCALED_ACTION,
    SYMBOL_INPUT, AMOUNT_INPUT, PRICE_INPUT, LEVERAGE_INPUT, SLIPPAGE_INPUT,
    MIN_PRICE_INPUT, MAX_PRICE_INPUT, NUM_ORDERS_INPUT, MIN_DISTANCE_INPUT, MAX_DISTANCE_INPUT,
    CONFIRM_ORDER,
    # Grid trading states
    GRID_ACTION, GRID_SELECT, GRID_MARKET_TYPE, GRID_SYMBOL, GRID_LOWER_PRICE, 
    GRID_UPPER_PRICE, GRID_NUM_LEVELS, GRID_INVESTMENT, GRID_LEVERAGE, 
    GRID_TAKE_PROFIT, GRID_STOP_LOSS, GRID_CONFIRM, GRID_START_NOW
)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main() -> None:
    """Start the bot"""
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("orders", orders_command))
    
    # Connection conversation handler
    connect_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("connect", connect_command)],
        states={
            NETWORK_SELECTION: [CallbackQueryHandler(network_selection, pattern=r"^network_")],
            WALLET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_address_input)],
            SECRET_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, secret_key_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    application.add_handler(connect_conv_handler)
    
    # Spot trading conversation handler
    spot_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("spot", spot_command)],
        states={
            SPOT_ACTION: [CallbackQueryHandler(trading_action_handler)],
            SYMBOL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, symbol_input_handler)],
            AMOUNT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_input_handler)],
            PRICE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_input_handler)],
            SLIPPAGE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, slippage_input_handler)],
            MIN_PRICE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, min_price_input_handler)],
            MAX_PRICE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, max_price_input_handler)],
            NUM_ORDERS_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, num_orders_input_handler)],
            CONFIRM_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    application.add_handler(spot_conv_handler)
    
    # Perpetual trading conversation handler
    perp_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("perp", perp_command)],
        states={
            PERP_ACTION: [CallbackQueryHandler(trading_action_handler)],
            SYMBOL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, symbol_input_handler)],
            AMOUNT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_input_handler)],
            PRICE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_input_handler)],
            LEVERAGE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, leverage_input_handler)],
            SLIPPAGE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, slippage_input_handler)],
            MIN_PRICE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, min_price_input_handler)],
            MAX_PRICE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, max_price_input_handler)],
            NUM_ORDERS_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, num_orders_input_handler)],
            CONFIRM_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    application.add_handler(perp_conv_handler)
    
    # Scaled orders conversation handler
    scaled_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("scaled", scaled_command)],
        states={
            SCALED_ACTION: [CallbackQueryHandler(scaled_action_handler)],
            SPOT_ACTION: [CallbackQueryHandler(trading_action_handler)],  # Reused for side selection
            PERP_ACTION: [CallbackQueryHandler(trading_action_handler)],  # Reused for market type selection
            SYMBOL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, symbol_input_handler)],
            AMOUNT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_input_handler)],
            MIN_PRICE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, min_price_input_handler)],
            MAX_PRICE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, max_price_input_handler)],
            NUM_ORDERS_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, num_orders_input_handler)],
            MIN_DISTANCE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, min_distance_input_handler)],
            MAX_DISTANCE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, max_distance_input_handler)],
            LEVERAGE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, leverage_input_handler)],
            CONFIRM_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    application.add_handler(scaled_conv_handler)

    # Grid trading conversation handler
    grid_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("grid", grid_command)],
        states={
            GRID_ACTION: [CallbackQueryHandler(grid_action_handler)],
            GRID_SELECT: [CallbackQueryHandler(grid_select_handler)],
            GRID_MARKET_TYPE: [CallbackQueryHandler(grid_market_type_handler)],
            GRID_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, grid_symbol_handler)],
            GRID_LOWER_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, grid_lower_price_handler)],
            GRID_UPPER_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, grid_upper_price_handler)],
            GRID_NUM_LEVELS: [MessageHandler(filters.TEXT & ~filters.COMMAND, grid_num_levels_handler)],
            GRID_INVESTMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, grid_investment_handler)],
            GRID_LEVERAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, grid_leverage_handler)],
            GRID_TAKE_PROFIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, grid_take_profit_handler)],
            GRID_STOP_LOSS: [MessageHandler(filters.TEXT & ~filters.COMMAND, grid_stop_loss_handler)],
            GRID_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, grid_confirm_handler)],
            GRID_START_NOW: [CallbackQueryHandler(grid_start_now_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    application.add_handler(grid_conv_handler)
    
    # Start the bot
    logger.info("Starting Elysium Trading Bot")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Run the bot until the user presses Ctrl-C
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot shutdown initiated")
    finally:
        # Close active API client sessions
        await application.stop()
        logger.info("Bot has stopped")

if __name__ == "__main__":
    asyncio.run(main())