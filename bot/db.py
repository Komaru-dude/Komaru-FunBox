import sqlite3, os, json, time

DB_PATH = "users.db"

def create_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username INTEGER DEFAULT '',
                        reputation INTEGER DEFAULT 0,
                        rank TEXT DEFAULT 'Участник',
                        message_count INTEGER DEFAULT 0,
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
        "Участник": 0,
        "Модератор": 1,
        "Администратор": 2,
        "Владелец": 3
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
