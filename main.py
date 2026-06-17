import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from config import settings
from services.database import Database
from handlers import user, admin

# Logging
logging.basicConfig(level=logging.INFO)
logger.add("bot.log", rotation="10 MB")

async def main():
    # Initialize database
    db = Database(settings.DATABASE_PATH)
    await db.init()
    logger.info("Database initialized")
    
    # Bot setup
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register routers
    dp.include_router(user.router)
    dp.include_router(admin.router)
    
    # Inject dependencies
    dp["db"] = db
    
    logger.info("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())