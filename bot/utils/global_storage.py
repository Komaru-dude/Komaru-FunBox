import asyncio

argue_active_chats = []
argue_active_chats_lock = asyncio.Lock()

onlysq_models = {}
