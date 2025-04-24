# main.py
import os
import logging
import asyncio
from datetime import datetime, timedelta
from io import BytesIO
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from telegram import Bot
from telegram.error import TelegramError
import aiofiles
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
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
    stats_file: str = "stats.log"
    
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
    def __init__(self, counter_file: str, stats_file: str):
        self.counter_file = os.path.abspath(counter_file)
        self.stats_file = os.path.abspath(stats_file)
        self.count = 0
        self.timestamps = []
        self.lock = asyncio.Lock()

    def _sync_create_file(self, filename: str, default: str = ""):
        """Синхронное создание файла с проверкой"""
        try:
            if not os.path.exists(filename):
                logger.info(f"Creating file: {filename}")
                with open(filename, 'w') as f:
                    f.write(default)
                os.chmod(filename, 0o664)
                logger.info(f"Successfully created: {filename}")
            else:
                logger.debug(f"File exists: {filename}")
        except Exception as e:
            logger.error(f"File creation error: {str(e)}")
            raise

    async def initialize_files(self):
        """Инициализация файлов с гарантированным созданием"""
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: [
                self._sync_create_file(self.counter_file, "0"),
                self._sync_create_file(self.stats_file, "")
            ]
        )

    async def load(self):
        """Загрузка данных с гарантированной инициализацией"""
        await self.initialize_files()
        
        try:
            # Загрузка счетчика
            async with aiofiles.open(self.counter_file, "r") as f:
                content = await f.read()
                self.count = int(content.strip() or 0)
            
            # Загрузка статистики
            async with aiofiles.open(self.stats_file, "r") as f:
                lines = await f.readlines()
                self.timestamps = [
                    datetime.fromisoformat(line.strip())
                    for line in lines
                    if line.strip()
                ]
                
            logger.info(f"Loaded {self.count} requests from storage")
            
        except Exception as e:
            logger.error(f"Load error: {str(e)}")
            await self._save_counter()
            await self._save_stats()

    async def _save_counter(self):
        async with aiofiles.open(self.counter_file, "w") as f:
            await f.write(str(self.count))
            logger.debug("Counter saved")

    async def _save_stats(self):
        async with aiofiles.open(self.stats_file, "w") as f:
            await f.write("\n".join(ts.isoformat() for ts in self.timestamps))
            logger.debug("Stats saved")

    async def increment(self):
        async with self.lock:
            self.count += 1
            now = datetime.now()
            self.timestamps.append(now)
            current_count = self.count
        
        await self._save_counter()
        await self._save_stats()
        return current_count, now

counter = RequestCounter(settings.counter_file, settings.stats_file)

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing application...")
    try:
        await counter.load()
        await bot.initialize()
        bot_info = await bot.get_me()
        logger.info(f"Bot @{bot_info.username} initialized")
        asyncio.create_task(message_worker())
    except Exception as e:
        logger.critical(f"CRITICAL ERROR: {str(e)}", exc_info=True)
        raise

async def message_worker():
    logger.info("Starting message worker")
    while True:
        count, username = await request_queue.get()
        try:
            await bot.send_message(
                chat_id=settings.channel_id,
                text=f"👤 Пользователь: {username}\n🌐 Всего запросов: {count}",
                write_timeout=15,
                connect_timeout=15
            )
        except Exception as e:
            logger.error(f"Message error: {str(e)}")
        finally:
            request_queue.task_done()

@app.get("/count")
async def increment_counter(
    request: Request,
    username: str = Query(default="Аноним", max_length=50)
):
    try:
        count, timestamp = await counter.increment()
        request_queue.put_nowait((count, username))
        return {
            "status": "ok",
            "count": count,
            "username": username,
            "timestamp": timestamp.isoformat()
        }
    except Exception as e:
        logger.error(f"Count error: {str(e)}")
        return {"status": "error", "detail": str(e)}

@app.get("/stats", response_class=HTMLResponse)
async def stats_page():
    return f"""
    <html>
        <head>
            <title>Статистика запросов</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2rem; }}
                .graph {{ max-width: 800px; margin: 0 auto; }}
                .info {{ margin-top: 2rem; padding: 1rem; background: #f5f5f5; }}
            </style>
        </head>
        <body>
            <h1>Статистика запросов</h1>
            <div class="graph">
                <img src="data:image/png;base64,{await generate_plot()}" />
            </div>
            <div class="info">
                <p>Всего запросов: {counter.count}</p>
                <p>Последний запрос: {counter.timestamps[-1].strftime('%Y-%m-%d %H:%M') if counter.timestamps else '-'}</p>
            </div>
        </body>
    </html>
    """

async def generate_plot():
    now = datetime.now()
    hours = [now - timedelta(hours=i) for i in range(23, -1, -1)]
    buckets = {h.replace(minute=0, second=0, microsecond=0): 0 for h in hours}
    
    for ts in counter.timestamps:
        bucket = ts.replace(minute=0, second=0, microsecond=0)
        if bucket in buckets:
            buckets[bucket] += 1
    
    plt.figure(figsize=(12, 6))
    plt.bar(
        [h.strftime('%H:%M') for h in buckets.keys()],
        buckets.values(),
        color='#4CAF50',
        edgecolor='darkgreen'
    )
    plt.title('Запросы по часам (последние 24 часа)', fontsize=14)
    plt.xlabel('Время', fontsize=12)
    plt.ylabel('Количество', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    return base64.b64encode(buf.getvalue()).decode()

@app.get("/status")
async def status():
    return {
        "status": "OK",
        "requests_total": counter.count,
        "queue_size": request_queue.qsize(),
        "last_hour": sum(1 for ts in counter.timestamps if ts > datetime.now() - timedelta(hours=1)),
        "storage_path": os.path.abspath(settings.counter_file)
    }

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Saving final state...")
    await counter._save_counter()
    await counter._save_stats()
