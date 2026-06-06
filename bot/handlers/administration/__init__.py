from aiogram import Router

from .moderation import admin_mods_router
from .premium import admin_premium_router
from .service import admin_service_router

admin_router = Router()

admin_router.include_routers(
    admin_mods_router, admin_premium_router, admin_service_router
)
