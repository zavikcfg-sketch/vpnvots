# H1Cloud VPN Telegram Bot

Полноценный Telegram-бот для **автоматической выдачи VLESS VPN** через H1Cloud панель.

## ✨ Возможности

- ✅ Автоматическое создание клиентов через официальный HTTP API
- ✅ Поддержка нескольких локаций (federation)
- ✅ Реферальная программа (+7 дней за приглашение)
- ✅ Личный кабинет с подписками
- ✅ Subscription-ссылки (самый удобный способ подключения)
- ✅ Админ-панель
- ✅ SQLite база данных

## 🚀 Быстрый старт

### 1. Подготовка H1Cloud

На **мастер-сервере** выполни:

```bash
# Запусти API (если ещё не запущен)
vpn api 25626

# Посмотри токен
vpn api token

# Посмотри статус
vpn api status
```

Запомни:
- `MASTER_IP` и порт API
- Токен из `vpn api token`
- Порт subscription (обычно `API_PORT + 1`)

### 2. Настройка бота

```bash
git clone <repo>
cd h1cloud_vpn_bot

pip install -r requirements.txt

cp .env.example .env
nano .env
```

### 3. Заполни `.env`

```env
BOT_TOKEN=твой_токен_бота

H1CLOUD_MASTER_API_URL=https://твой_ip:25626/api
H1CLOUD_MASTER_TOKEN=токен_из_vpn_api_token
H1CLOUD_MASTER_SUB_URL=https://твой_ip:25627

ADMIN_IDS=твой_telegram_id
```

### 4. Запусти бота

```bash
python main.py
```

## 📋 Команды

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню |
| `/admin` | Админ-панель (только для админов) |

## 🔧 Настройка тарифов

Тарифы хранятся в SQLite. По умолчанию создаются:

- 1 месяц — 30 дней
- 3 месяца — 90 дней  
- 6 месяцев — 180 дней
- 12 месяцев — 365 дней

Редактировать можно через SQL или добавив код в `database.py`.

## 📍 Добавление новых локаций

В `.env`:

```env
H1CLOUD_NODES=Germany:https://de_ip:25626/api:токен_de,Netherlands:https://nl_ip:25626/api:токен_nl
```

## 🔗 Как это работает

1. Клиент покупает подписку → бот создаёт клиента на мастере через `POST /create`
2. Если настроен federation — ноды автоматически получают клиента
3. Клиент получает **одну subscription-ссылку** мастера
4. Внутри ссылки — Reality + WS со всех подключённых локаций

## 🛠️ Структура проекта

```
h1cloud_vpn_bot/
├── main.py
├── config.py
├── services/
│   ├── h1cloud.py          # Полный клиент H1Cloud API
│   └── database.py
├── handlers/
│   ├── user.py
│   └── admin.py
└── data/vpn_bot.db
```

## 📌 Важные эндпоинты H1Cloud API

- `POST /create` — создать клиента
- `GET /clients` — список клиентов
- `GET /keys` — все ссылки (key.txt)
- `GET /status` — статус сервера
- `PATCH /edit` — продление

## ❓ Частые вопросы

**Q: Self-signed сертификат?**  
A: При первом обращении к API в браузере прими предупреждение или используй `-k` в curl.

**Q: Где взять SUB порт?**  
A: Обычно `API_PORT + 1`. Посмотри `vpn sub status`.

**Q: Можно ли создавать клиентов на нодах напрямую?**  
A: Лучше всегда на мастере. Ноды подтянут клиентов через federation.

---

Сделано специально под H1Cloud VLESS (https://vlesshelp.h1cloud.su/)