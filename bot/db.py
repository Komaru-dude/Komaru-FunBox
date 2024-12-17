import sqlite3, os, json, time

# Получаем абсолютный путь к базе данных, относительно расположения бота
DB_PATH = os.path.join(os.path.expanduser("~"), 'Komaru-Tools', 'users.db')

def create_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username INTEGER DEFAULT '',
                        warns INTEGER DEFAULT 0,
                        bans INTEGER DEFAULT 0,
                        mutes INTEGER DEFAULT 0,
                        reputation INTEGER DEFAULT 0,
                        rank TEXT DEFAULT 'Участник',
                        prefix TEXT DEFAULT '',
                        message_count INTEGER DEFAULT 0,
                        demotivators INTEGER DEFAULT 0,
                        warn_limit INTEGER DEFAULT 3,
                        history TEXT DEFAULT '',
                        first_name TEXT DEFAULT ''
                    )''')
    conn.commit()
    conn.close()

# Проверяем существование базы данных и создаём её при необходимости
if not os.path.exists(DB_PATH):
    create_db()

# Функция для проверки ранга пользователя
def has_permission(user_id, level):
    # Словарь с уровнями и соответствующими рангами
    rank_to_level = {
        "Забанен": 0,
        "Замьючен": 0,
        "Участник": 1,
        "Модератор": 2,
        "Администратор": 3,
        "Владелец": 4
    }

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Извлекаем ранг пользователя
    cursor.execute('''SELECT rank FROM users WHERE user_id = ?''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result is None:
        return False
    
    user_rank = result[0]  # Получаем статус пользователя
    user_level = rank_to_level.get(user_rank)
    
    if user_level is None:
        return False  # Если ранг не найден в словаре, возвращаем False

    return user_level >= level  # Проверяем, соответствует ли уровень пользователя требуемому

def user_have_username(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
    exists = cursor.fetchone()
    conn.close()
    if not exists == '':
        return False
    else:
        return True
    
def add_username(user_id, username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET username = ? WHERE user_id = ?', (username, user_id))
    conn.commit()
    conn.close()

def get_username(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT history FROM users WHERE user_id = ?''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def get_user_id_by_username(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT user_id FROM users WHERE username = ?''', (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

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

def set_prefix(user_id, prefix):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''UPDATE users SET prefix = ? WHERE user_id = ?''', (prefix, user_id))
    conn.commit()
    conn.close()

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

def update_user_warns(user_id, reason):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получаем текущую историю и количество предупреждений
    cursor.execute('''SELECT history, warns FROM users WHERE user_id = ?''', (user_id,))
    result = cursor.fetchone()

    if result is None:
        history = []
        warns = 0  # Если пользователь не существует, начинаем с 0 предупреждений
    else:
        history = json.loads(result[0]) if result[0] else []  # Парсим историю, если она есть
        warns = result[1]  # Получаем количество предупреждений

    # Добавляем новое предупреждение
    punishment = {
        "type": "warn",
        "reason": reason,
        "timestamp": int(time.time()),  # Время наказания в формате Unix timestamp
    }

    history.append(punishment)

    # Обновляем только историю
    cursor.execute('''UPDATE users SET history = ? WHERE user_id = ?''', (json.dumps(history), user_id))

    # Увеличиваем количество предупреждений
    warns += 1
    cursor.execute('''UPDATE users SET warns = ? WHERE user_id = ?''', (warns, user_id))

    conn.commit()
    conn.close()

def update_user_bans(user_id, reason):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получаем текущую историю
    cursor.execute('''SELECT history, bans FROM users WHERE user_id = ?''', (user_id,))
    result = cursor.fetchone()

    if result is None or not result[0]:
        history = []  # Если истории нет, создаем новый список
        bans = 0
    else:
        history = json.loads(result[0])  # Парсим историю как JSON
        bans = result[1]

    # Добавляем наказание типа ban
    punishment = {
        "type": "ban",
        "reason": reason,  # Причина передается как аргумент
        "timestamp": int(time.time()),  # Время начала наказания в формате Unix timestamp
    }

    history.append(punishment)

    # Увеличиваем количество банов
    bans += 1
    cursor.execute('''UPDATE users SET bans = ? WHERE user_id = ?''', (bans, user_id))

    # Обновляем историю в базе данных
    cursor.execute('''UPDATE users SET history = ? WHERE user_id = ?''', (json.dumps(history), user_id))
    conn.commit()
    conn.close()

def update_user_mutes(user_id, reason):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получаем текущую историю
    cursor.execute('''SELECT history, mutes FROM users WHERE user_id = ?''', (user_id,))
    result = cursor.fetchone()

    if result is None or not result[0]:
        history = []  # Если истории нет, создаем новый список
        mutes = 0
    else:
        history = json.loads(result[0])  # Парсим историю как JSON
        mutes = result[1]

    # Добавляем наказание типа mute
    punishment = {
        "type": "mute",
        "reason": reason,  # Причина передается как аргумент
        "timestamp": int(time.time()),  # Время начала наказания в формате Unix timestamp
    }

    # Увеличиваем количество мутов
    mutes += 1
    cursor.execute('''UPDATE users SET mutes = ? WHERE user_id = ?''', (mutes, user_id))

    history.append(punishment)

    # Обновляем историю в базе данных
    cursor.execute('''UPDATE users SET history = ? WHERE user_id = ?''', (json.dumps(history), user_id))
    conn.commit()
    conn.close()

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
        # Если пользователя нет, создаём его
        add_user(user_id)
        # Повторно извлекаем данные для нового пользователя
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

def get_history(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Извлекаем историю наказания
    cursor.execute('''SELECT history FROM users WHERE user_id = ?''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result is None or not result[0]:
        return []
    
    return json.loads(result[0])

def update_user_warn_limit(user_id, limit):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''UPDATE users SET warn_limit = warn_limit + ? WHERE user_id = ?''', (limit, user_id))
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

def get_first_name_by_id(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT first_name FROM users WHERE user_id = ?''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def add_first_name(user_id, first_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''UPDATE users SET first_name = ? WHERE user_id = ?''', (first_name, user_id))
    conn.commit()
    conn.close()

def user_have_first_name(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT first_name FROM users WHERE user_id = ?', (user_id,))
    exists = cursor.fetchone()
    conn.close()
    if not exists == '':
        return False
    else:
        return True
