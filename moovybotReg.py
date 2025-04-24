# main.py
import os
import logging
import asyncio
from fastapi import FastAPI, Request, Query
from telegram import Bot
from telegram.error import TelegramError
import aiofiles
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    bot_token: str = Field(..., alias="BOT_TOKEN")
    channel_id: str = Field(..., alias="CHANNEL_ID")
    counter_file: str = "counter.txt"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
app = FastAPI()
bot = Bot(token=settings.bot_token)
request_queue = asyncio.Queue()

class RequestCounter:
    def __init__(self, filename: str):
        self.filename = filename
        self.count = 0
        self.lock = asyncio.Lock()
    
    async def load(self):
        try:
            async with aiofiles.open(self.filename, "r") as f:
                content = await f.read()
                self.count = int(content)
                logger.info(f"Loaded counter: {self.count}")
        except FileNotFoundError:
            logger.info("Counter file not found, init new")
            self.count = 0
            await self._save(0)
        except Exception as e:
            logger.error(f"Load error: {e}, resetting")
            self.count = 0
            await self._save(0)
    
    async def _save(self, count: int):
        try:
            async with aiofiles.open(self.filename, "w") as f:
                await f.write(str(count))
                logger.debug(f"Saved count: {count}")
        except Exception as e:
            logger.error(f"Save failed: {e}")

    async def increment(self):
        async with self.lock:
            self.count += 1
            current_count = self.count
        
        await self._save(current_count)
        logger.info(f"Incremented to: {current_count}")
        return current_count

counter = RequestCounter(settings.counter_file)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting server...")
    try:
        await counter.load()
        await bot.initialize()
        logger.info(f"Bot: @{(await bot.get_me()).username}")
        asyncio.create_task(message_worker())
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

async def message_worker():
    logger.info("Message worker started")
    while True:
        # Получаем кортеж (count, username) из очереди
        count, username = await request_queue.get()
        logger.debug(f"Processing count: {count} from {username}")
        try:
            await bot.send_message(
                chat_id=settings.channel_id,
                text=f"👤 Пользователь: {username}\n"
                     f"🌐 Всего запросов: {count}",
                write_timeout=10,
                connect_timeout=10
            )
        except Exception as e:
            logger.error(f"Send message failed: {e}")
        finally:
            request_queue.task_done()
            logger.debug(f"Completed processing: {count}")

@app.get("/count")
async def increment_counter(
    request: Request,
    username: str = Query(
        default="Анонимный пользователь",
        max_length=50,
        description="Имя пользователя для статистики"
    )
):
    try:
        new_count = await counter.increment()
        # Добавляем в очередь кортеж (count, username)
        request_queue.put_nowait((new_count, username))
        return {
            "status": "ok",
            "count": new_count,
            "username": username,
            "queue_size": request_queue.qsize()
        }
    except Exception as e:
        logger.error(f"Count error: {e}")
        return {"status": "error", "detail": str(e)}

@app.get("/status")
async def status():
    return {
        "status": "running",
        "counter": counter.count,
        "queue": request_queue.qsize()
    }
