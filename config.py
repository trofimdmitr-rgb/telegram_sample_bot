import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "")

WORK_START = int(os.getenv("WORK_START", "9"))
WORK_END = int(os.getenv("WORK_END", "20"))
SLOT_INTERVAL = int(os.getenv("SLOT_INTERVAL", "60"))

# Прокси для доступа к api.telegram.org (если без VPN не подключается)
# Примеры: socks5://127.0.0.1:1080  или  http://127.0.0.1:7890
PROXY_URL = os.getenv("PROXY_URL", "").strip() or None

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан. Создайте файл .env на основе .env.example")
