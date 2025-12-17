import json
import time
from asyncpg import Pool

async def get_top_list(pool: Pool, limit: int = 10) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, money, bank, (money + bank) AS total
            FROM global_users
            ORDER BY total DESC LIMIT $1
            """, limit
        )
    return [dict(row) for row in rows]

async def give_item(pool: Pool, user_id: int, shop_item: dict):
    now = int(time.time())
    item = {
        "id": shop_item["id"],
        "name": shop_item.get("name"),
        "desc": shop_item.get("desc"),
    }
    
    # Обработка expires
    expires_raw = shop_item.get("expires", "False")
    if expires_raw == "False" or expires_raw is False:
        item["expires"] = False
    else:
        try:
            duration = int(expires_raw)
            item["expires"] = now + duration
        except:
            item["expires"] = False

    # Обработка uses
    try: item["uses"] = int(shop_item.get("uses", 1))
    except: item["uses"] = 1

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT items FROM global_users WHERE user_id = $1", user_id)
        if not row:
            await conn.execute("INSERT INTO global_users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)
            items = []
        else:
            items_raw = row["items"] or "[]"
            try: items = json.loads(items_raw) if isinstance(items_raw, str) else (items_raw if items_raw else [])
            except: items = []

        items.append(item)
        
        await conn.execute(
            "UPDATE global_users SET items = $1::jsonb WHERE user_id = $2",
            json.dumps(items), user_id
        )

async def check_item(pool: Pool, user_id: int, item_id: str) -> bool:
    now = int(time.time())
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT items FROM global_users WHERE user_id = $1", user_id)
        if not row: return False
        
        items_raw = row["items"]
        try: items = json.loads(items_raw) if isinstance(items_raw, str) else (items_raw or [])
        except: items = []

        for item in items:
            if item.get("id") == item_id:
                expires = item.get("expires")
                if expires and expires is not False and expires <= now:
                    continue
                
                uses = item.get("uses")
                if uses is not None and uses != -1 and int(uses) <= 0:
                    continue
                
                return True
        return False

async def consume_item(pool: Pool, user_id: int, item_id: str) -> bool:
    now = int(time.time())
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT items FROM global_users WHERE user_id = $1", user_id)
        if not row: return False
        
        items_raw = row["items"]
        try: items = json.loads(items_raw) if isinstance(items_raw, str) else (items_raw or [])
        except: items = []

        changed = False
        for i, item in enumerate(items):
            if item.get("id") == item_id:
                # Проверка просрочки
                expires = item.get("expires")
                if expires and expires is not False and expires <= now:
                    continue # Просрочен
                
                uses = item.get("uses", 0)
                if uses == -1:
                    return True # Бесконечный
                elif int(uses) <= 0:
                    continue # Кончился
                
                # Используем
                items[i]["uses"] = int(uses) - 1
                changed = True
                
                if items[i]["uses"] <= 0:
                    items.pop(i)
                break
        
        if changed:
            await conn.execute(
                "UPDATE global_users SET items = $1::jsonb WHERE user_id = $2",
                json.dumps(items), user_id
            )
            return True
        return False