import sqlite3, os, json, time, random
from pathlib import Path
from dotenv import load_dotenv

# Определяем абсолютный путь к папке data
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

default_features = [('who', 1), ('tag', 1), ('autovideo', 1), ('warn', 0), ('mute', 0), ('ban', 0)]

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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER,
            chat_id INTEGER,
            warns INTEGER DEFAULT 0,
            bans INTEGER DEFAULT 0,
            mutes INTEGER DEFAULT 0,
            reputation INTEGER DEFAULT 0,
            rank TEXT DEFAULT 'Участник',
            message_count INTEGER DEFAULT 0,
            history TEXT DEFAULT '',
            warn_limit INTEGER DEFAULT 3,
            PRIMARY KEY (user_id, chat_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS features (
            chat_id INTEGER,
            feature_name TEXT,
            is_enabled INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, feature_name)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    conn.commit()
    conn.close()

def sync_all():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    expected_tables = {
        'users': [
            ('user_id', 'INTEGER'),
            ('chat_id', 'INTEGER'),
            ('warns', 'INTEGER DEFAULT 0'),
            ('bans', 'INTEGER DEFAULT 0'),
            ('mutes', 'INTEGER DEFAULT 0'),
            ('reputation', 'INTEGER DEFAULT 0'),
            ('rank', "TEXT DEFAULT 'Участник'"),
            ('message_count', 'INTEGER DEFAULT 0'),
            ('history', "TEXT DEFAULT ''"),
            ('warn_limit', 'INTEGER DEFAULT 3'),
            ('first_name', "TEXT DEFAULT ''"),
            ('PRIMARY KEY', '(user_id, chat_id)'),
        ],
        'features': [
            ('chat_id', 'INTEGER'),
            ('feature_name', 'TEXT'),
            ('is_enabled', 'INTEGER DEFAULT 0'),
            ('PRIMARY KEY', '(chat_id, feature_name)'),
        ],
        'banned_users': [
            ('user_id', 'INTEGER PRIMARY KEY'),
        ]
    }

    for table_name, columns in expected_tables.items():
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        exists = cursor.fetchone()

        if not exists:
            column_defs = ',\n'.join([' '.join(col) if isinstance(col, tuple) else col for col in columns])
            cursor.execute(f"CREATE TABLE {table_name} (\n{column_defs}\n)")
        else:
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing = {row[1] for row in cursor.fetchall()}
            for col in columns:
                if isinstance(col, tuple) and col[0] not in existing and not col[0].startswith('PRIMARY'):
                    try:
                        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col[0]} {col[1]}")
                    except sqlite3.OperationalError as e:
                        print(f"[sync_all] Error adding column {col[0]}: {e}")

    # Синхронизация фич
    cursor.execute('SELECT DISTINCT chat_id FROM features')
    chat_ids = [row[0] for row in cursor.fetchall()]

    for chat_id in chat_ids:
        cursor.execute('SELECT feature_name FROM features WHERE chat_id = ?', (chat_id,))
        existing_features = {row[0] for row in cursor.fetchall()}

        for feature, enabled in default_features:
            if feature not in existing_features:
                cursor.execute('INSERT INTO features (chat_id, feature_name, is_enabled) VALUES (?, ?, ?)',
                               (chat_id, feature, enabled))

        # Удаление старых фич
        cursor.execute(
            f"DELETE FROM features WHERE chat_id = ? AND feature_name NOT IN ({','.join(['?'] * len(default_features))})",
            (chat_id, *[f[0] for f in default_features])
        )

    conn.commit()
    conn.close()

create_db()
sync_all()

def has_permission(user_id, chat_id, level):
    if str(user_id) == os.getenv("OWNER_ID"):
        return True

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT rank FROM users 
                      WHERE user_id = ? AND chat_id = ?''', (user_id, chat_id))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return False
    
    user_level = RANK_TO_LEVEL.get(result[0], -1)
    return user_level >= level

def set_rank(user_id, chat_id, rank):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO users 
                     (user_id, chat_id, rank) 
                     VALUES (?, ?, ?)''', 
                     (user_id, chat_id, rank))
    conn.commit()
    conn.close()

def user_exists(user_id, chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT 1 FROM users 
                     WHERE user_id = ? AND chat_id = ?''', 
                     (user_id, chat_id))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_user(user_id, chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''INSERT OR IGNORE INTO users 
                     (user_id, chat_id) VALUES (?, ?)''', 
                     (user_id, chat_id))
    conn.commit()
    conn.close()

def get_user_rank(user_id, chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT rank FROM users 
                     WHERE user_id = ? AND chat_id = ?''', 
                     (user_id, chat_id))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def update_count_messages(user_id, chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''UPDATE users 
                     SET message_count = message_count + 1 
                     WHERE user_id = ? AND chat_id = ?''', 
                     (user_id, chat_id))
    conn.commit()
    conn.close()

def get_user_data(user_id, chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''SELECT * FROM users 
                     WHERE user_id = ? AND chat_id = ?''', 
                     (user_id, chat_id))
    user_data = cursor.fetchone()
    
    if not user_data:
        add_user(user_id, chat_id)
        cursor.execute('''SELECT * FROM users 
                         WHERE user_id = ? AND chat_id = ?''', 
                         (user_id, chat_id))
        user_data = cursor.fetchone()
    
    conn.close()
    return user_data

def set_param(user_id, chat_id, param, value):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f'''UPDATE users 
                         SET {param} = ? 
                         WHERE user_id = ? AND chat_id = ?''', 
                         (value, user_id, chat_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка при обновлении параметра: {e}")
    conn.close()

def init_chat_features(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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

def is_feature_exists(chat_id: int, feature_name: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        result = conn.execute('''SELECT 1 FROM features WHERE chat_id = ? AND feature_name = ? LIMIT 1''', (chat_id, feature_name)).fetchone()
    return True if result else False

def enable_feature(chat_id: int, feature_name: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''UPDATE features SET is_enabled = 1 WHERE chat_id = ? AND feature_name = ?''', (chat_id, feature_name))

def disable_feature(chat_id: int, feature_name: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''UPDATE features SET is_enabled = 0 WHERE chat_id = ? AND feature_name = ?''', (chat_id, feature_name))

def mediaban_user(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)", (user_id,))

def mediaunban_user(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))

def is_user_mediabanned(user_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None

def update_user_warns(user_id, chat_id, reason):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''SELECT history, warns FROM users WHERE user_id = ? AND chat_id = ?''', (user_id, chat_id))
    result = cursor.fetchone()

    if result is None:
        history = []
        warns = 0
    else:
        history = json.loads(result[0]) if result[0] else []
        warns = result[1]

    punishment = {
        "type": "warn",
        "reason": reason,
        "timestamp": int(time.time()),
    }

    history.append(punishment)
    warns += 1
    cursor.execute('''UPDATE users SET history = ?, warns = ? WHERE user_id = ? AND chat_id = ?''', (json.dumps(history), warns, user_id, chat_id))
    conn.commit()
    conn.close()

def update_user_bans(user_id, chat_id, reason):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''SELECT history, bans FROM users WHERE user_id = ? AND chat_id = ?''', (user_id, chat_id))
    result = cursor.fetchone()

    if result is None or not result[0]:
        history = []
        bans = 0
    else:
        history = json.loads(result[0])
        bans = result[1]

    punishment = {
        "type": "ban",
        "reason": reason,
        "timestamp": int(time.time()),
    }

    history.append(punishment)
    bans += 1
    cursor.execute('''UPDATE users SET history = ?, bans = ? WHERE user_id = ? AND chat_id = ?''', (json.dumps(history), bans, user_id, chat_id))
    conn.commit()
    conn.close()

def update_user_mutes(user_id, chat_id, reason):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''SELECT history, mutes FROM users WHERE user_id = ? AND chat_id = ?''', (user_id, chat_id))
    result = cursor.fetchone()

    if result is None or not result[0]:
        history = []
        mutes = 0
    else:
        history = json.loads(result[0])
        mutes = result[1]

    punishment = {
        "type": "mute",
        "reason": reason,
        "timestamp": int(time.time()),
    }

    history.append(punishment)
    mutes += 1
    cursor.execute('''UPDATE users SET history = ?, mutes = ? WHERE user_id = ? AND chat_id = ?''', (json.dumps(history), mutes, user_id, chat_id))
    conn.commit()
    conn.close()

def get_history(user_id, chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''SELECT history FROM users WHERE user_id = ? AND chat_id = ?''', (user_id, chat_id))
    result = cursor.fetchone()
    conn.close()
    
    if result is None or not result[0]:
        return []
    
    return json.loads(result[0])

def update_user_warn_limit(user_id, chat_id, limit):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''UPDATE users SET warn_limit = warn_limit + ? WHERE user_id = ? AND chat_id = ?''', (limit, user_id, chat_id))
    conn.commit()
    conn.close()

def update_rep(user_id, chat_id, mode, value=None):
    if not user_id or not isinstance(user_id, int):
        raise ValueError("Неверный user_id. Он должен быть целым числом.")
    if mode not in ["auto_add", "manual_add", "manual_rem"]:
        raise ValueError(f"Режим {mode} некорректен, доступные режимы: auto_add, manual_add, manual_rem.")
    if mode in ["manual_add", "manual_rem"] and (not value or not isinstance(value, int)):
        raise ValueError("Для режимов manual_add и manual_rem необходимо указать целое значение для value.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if value is None and mode == "auto_add":
        value = random.randint(1, 6)

    if mode == "auto_add":
        cursor.execute('''UPDATE users SET reputation = reputation + ? WHERE user_id = ? AND chat_id = ?''', (value, user_id, chat_id))
    elif mode == "manual_add":
        cursor.execute('''UPDATE users SET reputation = reputation + ? WHERE user_id = ? AND chat_id = ?''', (value, user_id, chat_id))
    elif mode == "manual_rem":
        cursor.execute('''UPDATE users SET reputation = reputation - ? WHERE user_id = ? AND chat_id = ?''', (value, user_id, chat_id))

    conn.commit()
    conn.close()

def update_need_msg(user_id, chat_id, count_msg):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''UPDATE users SET message_count = ? WHERE user_id = ? AND chat_id = ?''', (count_msg, user_id, chat_id))
    conn.commit()
    conn.close()