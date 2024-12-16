import os
import asyncio
import logging
from dotenv import load_dotenv
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from notion_client import Client

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Retrieve tokens from environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
NOTION_INTEGRATION_TOKEN = os.getenv('NOTION_INTEGRATION_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')

# Validate that tokens are present
if not all([TELEGRAM_BOT_TOKEN, NOTION_INTEGRATION_TOKEN, NOTION_DATABASE_ID]):
    raise ValueError("Missing required environment variables. Check your .env file.")

# Initialize Notion client
notion = Client(auth=NOTION_INTEGRATION_TOKEN)

def parse_expense_message(message: str):
    """
    Parse expense message in format:
    Item, Price, Store, Category, Quantity
    """
    # Try parsing with optional date
    parts = [part.strip() for part in message.split(',')]
    
    # Determine if date is included
    if len(parts) == 6:
        try:
            # Validate date format
            date = datetime.strptime(parts[0], '%Y-%m-%d').date()
            item, price, store, category, quantity = parts[1:]
        except ValueError:
            # If date parsing fails, assume today's date
            date = datetime.now().date()
            item, price, store, category, quantity = parts
    elif len(parts) == 5:
        try:
            # Validate date format
            date = datetime.strptime(parts[0], '%Y-%m-%d').date()
            item, price, store, category = parts[1:]
            quantity = ''
        except ValueError:
            # If date parsing fails, assume today's date
            date = datetime.now().date()
            item, price, store, category, quantity = parts
    elif len(parts) == 4:
        date = datetime.now().date()
        item, price, store, category = parts
        quantity = ''
    else:
        raise ValueError("Invalid message format. Use: Item, Price, Store, Category")
    
    return {
        'date': date,
        'item': item,
        'price': float(price),
        'store': store,
        'category': category,
        'quantity': quantity
    }

async def start(update: Update, context):
    """Handler for /start command"""
    await update.message.reply_text(
        "Expense Tracker Bot 💰\n\n"
        "Send expenses in this format:\n"
        "Item, Price, Store, Category\n\n"
        "Optional: You can include a date (YYYY-MM-DD) at the start\nand quantity at the end\n\n"
        "Examples:\n"
        "• Eggs, 3.50, Walmart, Groceries\n"
        "• Milk, 2.25, Costco, Groceries, 2 gallons\n"
        "• 2024-01-15, Bread, 2.25, Kroger, Groceries"
    )

async def handle_expense(update: Update, context):
    """Process incoming expense messages and update Notion database"""
    try:
        # Parse the expense message
        expense = parse_expense_message(update.message.text)
        
        # Create a new page in the Notion database
        notion.pages.create(
            parent={"type": "database_id", "database_id": NOTION_DATABASE_ID},
            properties={
                "Date": {
                    "type": "date",
                    "date": {
                        "start": expense['date'].isoformat()
                    }
                },
                "Item": {
                    "type": "title",
                    "title": [
                        {
                            "type": "text",
                            "text": {
                                "content": expense['item']
                            }
                        }
                    ]
                },
                "Price": {
                    "type": "number",
                    "number": expense['price']
                },
                "Store": {
                    "type": "select",
                    "select": {
                        "name": expense['store']
                    }
                },
                "Category": {
                    "type": "select",
                    "select": {
                        "name": expense['category']
                    }
                },
                "Quantity": {
                    "type": "rich_text",
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": expense['quantity']
                            }
                        }
                    ]
                }
            }
        )
        
        # Confirm message
        await update.message.reply_text(
            f"✅ Expense added:\n"
            f"📅 Date: {expense['date']}\n"
            f"🛍️ Item: {expense['item']}\n"
            f"💲 Price: ${expense['price']:.2f}\n"
            f"🏪 Store: {expense['store']}\n"
            f"📦 Category: {expense['category']}\n"
            f"🔢 Quantity: {expense['quantity']}"
        )
    
    except ValueError as ve:
        # Handle parsing errors
        await update.message.reply_text(f"❌ Error: {str(ve)}\n\n"
            "Please use the format: Date (optional), Item, Price, Store, Category, Quantity (optional)\n"
            "Example: Milk, 3.50, Walmart, Groceries")
    except Exception as e:
        # Handle other potential errors
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ An unexpected error occurred: {str(e)}")

async def main():
    """Main bot application setup"""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_expense))
    
    # Start the bot
    await application.initialize()
    await application.start()
    
    # Run the bot until the user presses Ctrl-C
    await application.updater.start_polling(drop_pending_updates=True)
    
    # Keep the script running
    await asyncio.get_event_loop().create_future()

if __name__ == '__main__':
    asyncio.run(main())