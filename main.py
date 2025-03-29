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
    balance_command, orders_command, spot_command, perp_command,
    wallet_address_input, secret_key_input, network_selection,
    trading_action_handler, symbol_input_handler, amount_input_handler,
    price_input_handler, leverage_input_handler, slippage_input_handler,
    confirm_order_handler, cancel_handler, status_command,  # Add status_command here
    WALLET_ADDRESS, SECRET_KEY, NETWORK_SELECTION,
    SPOT_ACTION, PERP_ACTION,
    SYMBOL_INPUT, AMOUNT_INPUT, PRICE_INPUT, LEVERAGE_INPUT, SLIPPAGE_INPUT,
    CONFIRM_ORDER
)

from config import TELEGRAM_TOKEN

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
            CONFIRM_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    application.add_handler(perp_conv_handler)
    
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