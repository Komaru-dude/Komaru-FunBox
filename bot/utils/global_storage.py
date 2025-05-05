import asyncio

active_chats = []
active_chats_lock = asyncio.Lock()

onlysq_models = {}
