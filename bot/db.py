import sqlite3, os
from pathlib import Path
from dotenv import load_dotenv

# Определяем абсолютный путь к папке data
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Абсолютный путь к базе данных
DB_PATH = DATA_DIR / "users.db"

RANK_TO_LEVEL = {
    "Участник": 0,
    "Модератор": 1,
    "Администратор": 2,
    "Владелец": 3,
    "Персонал": 4
}

load_dotenv()

def create_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        reputation INTEGER DEFAULT 0,
                        rank TEXT DEFAULT 'Участник',
                        message_count INTEGER DEFAULT 0,
                        first_name TEXT DEFAULT ''
                    )''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS features (
            chat_id INTEGER,
            feature_name TEXT,
            is_enabled INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, feature_name)
        )
    ''')
    conn.commit()
    conn.close()

create_db()

def has_permission(user_id, level):
    if str(user_id) == os.getenv("OWNER_ID"):
        return True

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Извлекаем ранг пользователя
    cursor.execute('''SELECT rank FROM users WHERE user_id = ?''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result is None:
        return False
    
    user_rank = result[0]
    user_level = RANK_TO_LEVEL.get(user_rank)
    
    if user_level is None:
        return False

    return user_level >= level

def set_rank(user_id, rank):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''UPDATE users SET rank = ? WHERE user_id = ?''', (rank, user_id))
    conn.commit()
    conn.close()

def user_exists(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT 1 FROM users WHERE user_id = ?''', (user_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''INSERT OR IGNORE INTO users (user_id) VALUES (?)''', (user_id,))
    conn.commit()
    conn.close()

def get_user_rank(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT rank FROM users WHERE user_id = ?''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result is None:
        return None
    return result[0]

def update_count_messges(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''UPDATE users SET message_count = message_count + 1 WHERE user_id =?''', (user_id,))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Проверяем, существует ли пользователь
    cursor.execute('''SELECT * FROM users WHERE user_id = ?''', (user_id,))
    user_data = cursor.fetchone()
    
    if user_data is None:
        add_user(user_id)
        cursor.execute('''SELECT * FROM users WHERE user_id = ?''', (user_id,))
        user_data = cursor.fetchone()
    
    conn.close()
    return user_data

def update_user_id(user_id, new_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''UPDATE users SET user_id = ? WHERE user_id = ?''', (new_id, user_id))
    conn.commit()
    
    conn.close()

def set_param(user_id, param, value):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = f"UPDATE users SET {param} = ? WHERE user_id = ?"
    try:
        cursor.execute(query, (value, user_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка при обновлении параметра: {e}")
    conn.close()

def init_chat_features(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    default_features = [('who', 1)]
    for feature, enabled in default_features:
        cursor.execute('''INSERT OR IGNORE INTO features (chat_id, feature_name, is_enabled) VALUES (?, ?, ?)''', (chat_id, feature, enabled))
    conn.commit()
    conn.close()

def is_init(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT 1 FROM features WHERE chat_id = ? LIMIT 1''', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    return True if result else False

def is_feature_enabled(chat_id: int, feature_name: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT is_enabled FROM features WHERE chat_id = ? AND feature_name = ?''', (chat_id, feature_name))
    result = cursor.fetchone()
    conn.close()
    return bool(result[0]) if result else False

def enable_feature(chat_id: int, feature_name: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''UPDATE features SET is_enabled = 1 WHERE chat_id = ? AND feature_name = ?''', (chat_id, feature_name))
    conn.commit()
    conn.close()

def disable_feature(chat_id: int, feature_name: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''UPDATE features SET is_enabled = 0 WHERE chat_id = ? AND feature_name = ?''', (chat_id, feature_name))
    conn.commit()
    conn.close()