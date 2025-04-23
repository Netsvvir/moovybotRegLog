from flask import Flask, request
from telegram import Bot
import threading
import json
import os

app = Flask(__name__)

# Конфигурация
BOT_TOKEN = 'ВАШ_ТОКЕН_БОТА'
CHANNEL_ID = '@ВАШ_КАНАЛ'  # Или числовой ID канала
COUNTER_FILE = 'counter.json'

# Инициализация бота
bot = Bot(token=BOT_TOKEN)

def load_counter():
    """Загружает счетчик из файла"""
    try:
        if os.path.exists(COUNTER_FILE):
            with open(COUNTER_FILE, 'r') as f:
                data = json.load(f)
                return data.get('count', 0)
        return 0
    except Exception as e:
        print(f"Ошибка загрузки счетчика: {e}")
        return 0

def save_counter(count):
    """Сохраняет счетчик в файл"""
    try:
        with open(COUNTER_FILE, 'w') as f:
            json.dump({'count': count}, f)
    except Exception as e:
        print(f"Ошибка сохранения счетчика: {e}")

# Инициализация счетчика при запуске
COUNTER = load_counter()

@app.route('/webhook', methods=['GET'])
def handle_webhook():
    global COUNTER
    COUNTER += 1
    save_counter(COUNTER)  # Сохраняем после каждого обновления
    
    # Отправка сообщения в канал в отдельном потоке
    threading.Thread(
        target=send_update_notification,
        args=(COUNTER,)
    ).start()
    
    return f'OK - Count: {COUNTER}'

def send_update_notification(count):
    try:
        bot.send_message(
            chat_id=CHANNEL_ID,
            text=f'🔄 Новый GET-запрос! Всего запросов: {count}'
        )
    except Exception as e:
        print(f'Ошибка при отправке сообщения: {e}')

if __name__ == '__main__':
    # Создаем файл счетчика если его нет
    if not os.path.exists(COUNTER_FILE):
        save_counter(0)
    app.run(host='0.0.0.0', port=5000)
