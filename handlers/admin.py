from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from datetime import datetime

from services.h1cloud import H1CloudAPI
from services.database import Database
from config import settings

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS

@router.message(Command("admin"))
async def admin_panel(message: Message, db: Database):
    if not is_admin(message.from_user.id):
        return
    
    stats = await db.get_admin_stats()
    
    text = (
        "👑 <b>Админ-панель</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"📱 Активных подписок: <b>{stats['active_subscriptions']}</b>\n\n"
        "Выбери действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика по нодам", callback_data="admin_nodes")],
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="admin_sync")]
    ])
    
    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "admin_nodes")
async def admin_nodes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    nodes = ["Master"] + list(settings.nodes.keys())
    
    text = "📍 <b>Статус нод:</b>\n\n"
    
    for node_name in nodes:
        if node_name == "Master":
            api = H1CloudAPI(settings.H1CLOUD_MASTER_API_URL, settings.H1CLOUD_MASTER_TOKEN)
        else:
            node_info = settings.nodes.get(node_name)
            if not node_info:
                continue
            api = H1CloudAPI(node_info['url'], node_info['token'])
        
        try:
            status = await api.get_status()
            if status.get("ok"):
                text += f"✅ <b>{node_name}</b>\n"
                text += f"   Клиенты: {status.get('clients_count', 'N/A')}\n"
            else:
                text += f"❌ <b>{node_name}</b> — недоступна\n"
        except:
            text += f"❌ <b>{node_name}</b> — ошибка подключения\n"
    
    await callback.message.edit_text(text)

@router.callback_query(F.data == "admin_sync")
async def admin_sync(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.answer("Синхронизация... (в разработке)", show_alert=True)