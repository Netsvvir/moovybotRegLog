from flask import Flask, request
from telegram import Bot
from telegram.ext import Updater
import threading
import os

app = Flask(__name__)
COUNTER_FILE = "counter.txt"

# Инициализация счётчика
def init_counter():
    if not os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, 'w') as f:
            f.write('0')
    
    try:
        with open(COUNTER_FILE, 'r') as f:
            return int(f.read().strip() or 0)
    except Exception as e:
        print(f"Error reading counter: {e}")
        return 0

counter = init_counter()

# Конфигурация SSL
SSL_CERT = '/etc/letsencrypt/live/ваш-домен/fullchain.pem'
SSL_KEY = '/etc/letsencrypt/live/ваш-домен/privkey.pem'

# Конфигурация бота
BOT_TOKEN = '8187209628:AAGmp2jeLZAs-CDxH3Rasui3M1wMwDdCMP8'
CHANNEL_ID = '1002682218447'  # Например: @my_channel или ID канала
WEBHOOK_URL = 'https://vvsavchenkoip.ru/count'

# Инициализация бота
bot = Bot(token=BOT_TOKEN)

@app.route('/count', methods=['GET'])
def handle_get():
    global counter
    counter += 1
    
    # Сохранение в файл
    try:
        with open(COUNTER_FILE, 'w') as f:
            f.write(str(counter))
    except Exception as e:
        print(f"Save error: {e}")
    
    # Отправка в канал
    try:
        bot.send_message(
            chat_id=CHANNEL_ID,
            text=f'🔐 HTTPS запрос! Всего: {counter}\n'
                 f'IP: {request.remote_addr}\n'
                 f'User-Agent: {request.headers.get("User-Agent")}'
        )
    except Exception as e:
        print(f"Telegram error: {e}")
    
    return f'Total: {counter}'

def run_bot():
    updater = Updater(BOT_TOKEN)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    # Запуск с SSL
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(
        host='0.0.0.0',
        port=443,
        ssl_context=(SSL_CERT, SSL_KEY),
        use_reloader=False
    )
