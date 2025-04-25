#  1. Подключение к серверу 

```bash
ssh user@your_server_ip
```


# 2. Установка необходимых зависимостей 

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv nginx -y
```

# 3. Создаём директорию проекта и виртуальное окружение проекта

```bash
mkdir -p /home/ubuntu/counter-bot && cd /home/ubuntu/counter-bot

python3 -m venv venv
source venv/bin/activate
```

# 4. Устанавливаем необходимые пакеты в виртуальном окружении

```bash
python3 -m pip install fastapi uvicorn python-telegram-bot aiofiles pydantic pydantic-settings

или 

pip install fastapi uvicorn python-telegram-bot aiofiles pydantic pydantic-settings
```

# 5. Переменные окружения

```bash
nano .env
```

Содержимое создаваемого файла:
```ini
BOT_TOKEN=ваш_токен_бота
CHANNEL_ID=@ваш_канал

# формат токена бота BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
# формат id канала CHANNEL_ID (должен быть вида `@channelname` или `-100123456789`) обязательно с -
```

Для работы бота соответственно нужно создать нового бота через botfather, а также новый канал, куда бот будет постить сообщения. Бот должен быть администратором канала

# 6. Конфигурационный файл NginX

```bash
sudo nano /etc/nginx/sites-available/counter-bot
```
Содержимое файла
```nginx
server {
    listen 80;
    server_name example.ru; #Тут необходимо указать Ваш домен

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```
После сохранения файла конфигурации необходимо активировать конфигурацию и перезагрузить сервисы
```bash
sudo ln -s /etc/nginx/sites-available/counter-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```
# 7. Создание сервиса systemd
```bash
sudo nano /etc/systemd/system/counter-bot.service
```
Содержимое файла конфигурации
```ini
[Unit]
Description=Counter Bot Service
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/counter-bot
Environment="PATH=/home/ubuntu/counter-bot/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/ubuntu/counter-bot/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target

# путь /home/ubuntu может быть Вашим, мы задаём его в пункте 3
```

# 8. Запуск и активация сервиса. Остановка сервиса
```bash
sudo systemctl daemon-reload
sudo systemctl start counter-bot
sudo systemctl enable counter-bot
```
Проверка статуса сервиса
```bash
sudo systemctl status counter-bot
```


Перезапуск сервиса
```bash
sudo systemctl stop counter-bot
sudo systemctl daemon-reload
sudo systemctl start counter-bot
#проверка работоспособности (ворнингов и ошибок быть не должно, должны быть фрагменты тестовых обращений к боту и каналу)
sudo journalctl -u counter-bot.service -f
```
Тестовое воздействие
```bash
curl http://localhost:8000/status
#должны отобразиться статусные параменты
curl http://localhost:8000/count
#должно отобразиться сообщение в канале
```

Соответственно, если Вы настроили VPS или любой другой сервер, у него есть статичный IP или Вы привязали домен:

```bash
curl http://10.10.10.10:8000/status
#должны отобразиться статусные параменты
curl http://10.10.10.10:8000/count
#должно отобразиться сообщение в канале
#соответственно вместо 10.10.10.10 будет Ваш IP
#или
curl http://example.ru/status
#должны отобразиться статусные параменты
curl http://example.ru/count
#где вместо example.ru Ваш домен 
```
Тест с разными именами регистрируемых пользователей 
```bash
# Тест с разными именами
curl "http://localhost:8000/count?username=Тестовый%20Юзер"
curl "http://localhost:8000/count?username=Alice%20%26%20Bob"
curl "http://localhost:8000/count?username=%F0%9F%91%BE%20Emoji%20User"
```
# Дополнительные проверки в случае проблем

```bash
#Проверка прав доступа к файлам
sudo chown -R ubuntu:ubuntu /home/ubuntu/counter-bot
sudo chmod 600 /home/ubuntu/counter-bot/.env
sudo chmod 755 /home/ubuntu/counter-bot

#Проверка пакетов в виртуальном окружении
pip list
# Должны получить примерно следующий результат:
# fastapi >=0.68.0
# python-telegram-bot >=20.0
# uvicorn >=0.15.0
# pydantic-settings >=2.0.3
# pydantic >=2.0

```
