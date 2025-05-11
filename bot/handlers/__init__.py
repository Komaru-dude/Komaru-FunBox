from os import getenv
from dotenv import load_dotenv

load_dotenv()

required_vars = {
    "BOT_API_TOKEN": "Токен API бота",
    "OWNER_ID": "ID владельца бота",
    "API_ID": "Telegram API ID",
    "API_HASH": "Telegram API HASH",
    "API_URL": "URL апи для ИИ (почему бы не использовать onlysq?)",
    "JIGSAW_API_KEY": "Апи ключ для jigsaw функций",
    "ONLYSQ_API_KEY": "Апи ключ для onlysq",
    "OPENAI_SDK_API_URL": "Апи ключ для onlysq",
}

for var, description in required_vars.items():
    if not getenv(var):
        raise ValueError(
            f"Переменная {var} ({description}) не найдена. "
            "Убедитесь, что она присутствует в .env файле."
        )
