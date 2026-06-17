from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import uuid
import re

from services.h1cloud import H1CloudAPI
from services.database import Database
from config import settings

router = Router()

class BuyStates(StatesGroup):
    choosing_tariff = State()
    choosing_node = State()
    confirming = State()

def get_api_for_node(node_name: str) -> H1CloudAPI:
    """Get H1CloudAPI instance for a node"""
    if node_name == "Master":
        return H1CloudAPI(settings.H1CLOUD_MASTER_API_URL, settings.H1CLOUD_MASTER_TOKEN)
    node_info = settings.nodes.get(node_name)
    if node_info:
        return H1CloudAPI(node_info["url"], node_info["token"])
    return None

@router.message(CommandStart())
async def cmd_start(message: Message, db: Database):
    args = message.text.split()
    referred_by = None
    
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referred_by = int(args[1].replace("ref_", ""))
        except:
            pass
    
    await db.get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        referred_by
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить подписку", callback_data="buy")],
        [InlineKeyboardButton(text="📋 Мои подписки", callback_data="my_subs")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    
    text = (
        "👋 <b>Добро пожаловать в H1Cloud VPN!</b>\n\n"
        "Автоматическая выдача VLESS (Reality + WS)\n\n"
        "Выбери действие:"
    )
    
    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "buy")
async def show_tariffs(callback: CallbackQuery, db: Database, state: FSMContext):
    tariffs = await db.get_all_tariffs()
    
    if not tariffs:
        await callback.answer("Тарифы временно недоступны", show_alert=True)
        return
    
    keyboard = []
    for tariff in tariffs:
        text = f"{tariff['name']} — {tariff['days']} дней"
        if tariff.get('traffic_limit_gb'):
            text += f" | {tariff['traffic_limit_gb']} GB"
        if tariff.get('device_limit'):
            text += f" | {tariff['device_limit']} устр."
        
        keyboard.append([InlineKeyboardButton(
            text=text,
            callback_data=f"tariff_{tariff['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")])
    
    await callback.message.edit_text(
        "📦 <b>Выберите тариф:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(BuyStates.choosing_tariff)

@router.callback_query(BuyStates.choosing_tariff, F.data.startswith("tariff_"))
async def choose_node(callback: CallbackQuery, state: FSMContext, db: Database):
    tariff_id = int(callback.data.split("_")[1])
    tariffs = await db.get_all_tariffs()
    tariff = next((t for t in tariffs if t['id'] == tariff_id), None)
    
    if not tariff:
        await callback.answer("Тариф не найден", show_alert=True)
        return
    
    await state.update_data(tariff=tariff)
    
    # Available nodes
    nodes = ["Master"] + list(settings.nodes.keys())
    
    keyboard = []
    for node in nodes:
        keyboard.append([InlineKeyboardButton(text=f"📍 {node}", callback_data=f"node_{node}")])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="buy")])
    
    await callback.message.edit_text(
        f"📍 <b>Выберите локацию</b> для тарифа <b>{tariff['name']}</b>:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(BuyStates.choosing_node)

@router.callback_query(BuyStates.choosing_node, F.data.startswith("node_"))
async def confirm_purchase(callback: CallbackQuery, state: FSMContext):
    node = callback.data.split("_")[1]
    data = await state.get_data()
    tariff = data['tariff']
    
    await state.update_data(node=node)
    
    text = (
        f"🛒 <b>Подтверждение покупки</b>\n\n"
        f"📦 Тариф: <b>{tariff['name']}</b>\n"
        f"📍 Локация: <b>{node}</b>\n"
        f"⏳ Срок: <b>{tariff['days']} дней</b>\n"
    )
    
    if tariff.get('traffic_limit_gb'):
        text += f"📊 Трафик: <b>{tariff['traffic_limit_gb']} GB</b>\n"
    if tariff.get('device_limit'):
        text += f"📱 Устройства: <b>{tariff['device_limit']}</b>\n"
    
    text += "\n⚠️ После создания клиента ты получишь subscription-ссылку."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Создать клиента", callback_data="confirm_buy")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(BuyStates.confirming)

@router.callback_query(BuyStates.confirming, F.data == "confirm_buy")
async def create_vpn_client(callback: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    tariff = data['tariff']
    node_name = data['node']
    user_id = callback.from_user.id
    
    api = get_api_for_node(node_name)
    if not api:
        await callback.message.edit_text("❌ Ошибка: узел не найден")
        await state.clear()
        return
    
    # Generate unique client name
    client_name = f"tg{user_id}_{uuid.uuid4().hex[:8]}"
    
    # Create client via H1Cloud API
    result = await api.create_client(
        name=client_name,
        days=tariff['days'],
        traffic_limit_gb=tariff.get('traffic_limit_gb'),
        device_limit=tariff.get('device_limit')
    )
    
    if not result.get("ok"):
        error = result.get("error", "Неизвестная ошибка")
        await callback.message.edit_text(f"❌ Ошибка создания клиента:\n<code>{error}</code>")
        await state.clear()
        return
    
    # Save to local database
    expires_at = datetime.now() + timedelta(days=tariff['days'])
    await db.create_subscription(
        user_id=user_id,
        client_name=client_name,
        node_name=node_name,
        expires_at=expires_at,
        traffic_limit_gb=tariff.get('traffic_limit_gb'),
        device_limit=tariff.get('device_limit')
    )
    
    # Get subscription link
    sub_url = f"{settings.master_sub_url}/sub/{result.get('uuid', 'UUID')}"
    
    text = (
        f"✅ <b>Клиент успешно создан!</b>\n\n"
        f"📛 Имя: <code>{client_name}</code>\n"
        f"📍 Локация: {node_name}\n"
        f"📅 Действует до: <b>{expires_at.strftime('%d.%m.%Y')}</b>\n\n"
        f"🔗 <b>Subscription ссылка:</b>\n"
        f"<code>{sub_url}</code>\n\n"
        f"Скопируй ссылку и добавь в приложение (v2rayN, Nekobox, Hiddify и т.д.)"
    )
    
    await callback.message.edit_text(text)
    await state.clear()

@router.callback_query(F.data == "my_subs")
async def show_my_subs(callback: CallbackQuery, db: Database):
    subs = await db.get_user_subscriptions(callback.from_user.id)
    
    if not subs:
        await callback.message.edit_text(
            "У тебя пока нет активных подписок.\n\n"
            "Нажми «Купить подписку», чтобы приобрести.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛒 Купить", callback_data="buy")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
            ])
        )
        return
    
    text = "📋 <b>Твои подписки:</b>\n\n"
    keyboard = []
    
    for sub in subs:
        expires = datetime.fromisoformat(sub['expires_at']) if isinstance(sub['expires_at'], str) else sub['expires_at']
        days_left = max(0, (expires - datetime.now()).days)
        
        status = "✅" if days_left > 0 else "❌"
        
        text += (
            f"{status} <b>{sub['client_name']}</b> ({sub['node_name']})\n"
            f"   До: {expires.strftime('%d.%m.%Y')} ({days_left} дн.)\n\n"
        )
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"🔗 Получить ссылку — {sub['client_name'][:12]}",
                callback_data=f"get_links_{sub['client_name']}_{sub['node_name']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("get_links_"))
async def get_client_links(callback: CallbackQuery, db: Database):
    parts = callback.data.split("_", 2)
    if len(parts) < 3:
        await callback.answer("Ошибка", show_alert=True)
        return
    
    client_name = parts[2].split("_")[0] if "_" in parts[2] else parts[2]
    # Better parsing
    match = re.search(r"get_links_(.+)_(.+)", callback.data)
    if not match:
        await callback.answer("Ошибка парсинга", show_alert=True)
        return
    
    client_name = match.group(1)
    node_name = match.group(2)
    
    api = get_api_for_node(node_name)
    if not api:
        await callback.answer("Узел не найден", show_alert=True)
        return
    
    # Get client info
    client_info = await api.get_client(client_name)
    
    # Get all keys (more reliable for links)
    keys_result = await api.get_keys()
    
    text = f"🔗 <b>Ссылки для {client_name}</b>\n\n"
    
    if client_info and client_info.get("ok"):
        uuid_val = client_info.get("uuid")
        if uuid_val:
            sub_link = f"{settings.master_sub_url}/sub/{uuid_val}"
            text += f"📥 <b>Subscription:</b>\n<code>{sub_link}</code>\n\n"
    
    # Try to find links in keys
    if keys_result.get("ok") and "raw" in keys_result:
        raw_keys = keys_result["raw"]
        # Simple search for the client
        lines = raw_keys.split("\n")
        found = False
        for line in lines:
            if client_name in line and "vless://" in line:
                text += f"<code>{line}</code>\n\n"
                found = True
        
        if not found:
            text += "Полные VLESS-ссылки (Reality/WS) доступны в subscription.\n"
    else:
        text += "Subscription ссылка выше — самый удобный способ.\n"
    
    text += "\n💡 Рекомендуется использовать subscription-ссылку в приложении."
    
    await callback.message.answer(text)

@router.callback_query(F.data == "referral")
async def show_referral(callback: CallbackQuery, db: Database):
    stats = await db.get_referral_stats(callback.from_user.id)
    bot_username = (await callback.bot.get_me()).username
    
    ref_link = f"https://t.me/{bot_username}?start=ref_{callback.from_user.id}"
    
    text = (
        "👥 <b>Реферальная программа</b>\n\n"
        f"Твоя реферальная ссылка:\n"
        f"<code>{ref_link}</code>\n\n"
        f"👥 Приглашено: <b>{stats['referrals']}</b> человек\n"
        f"🎁 Получено бонусных дней: <b>{stats['bonus_days']}</b>\n\n"
        f"За каждого приглашённого +<b>{settings.REFERRAL_BONUS_DAYS}</b> дней к следующей подписке!"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
        ])
    )

@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "• <b>Купить подписку</b> — выбор тарифа и локации\n"
        "• <b>Мои подписки</b> — просмотр и получение ссылок\n"
        "• <b>Рефералка</b> — приглашай друзей и получай бонусы\n\n"
        "Поддержка: @your_support_username"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
        ])
    )

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить подписку", callback_data="buy")],
        [InlineKeyboardButton(text="📋 Мои подписки", callback_data="my_subs")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])
    
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "cancel_buy")
async def cancel_buy(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Покупка отменена.")