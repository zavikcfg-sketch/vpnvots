import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import json

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    referred_by INTEGER,
                    referral_bonus_claimed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    client_name TEXT UNIQUE,
                    node_name TEXT,
                    expires_at TIMESTAMP,
                    traffic_limit_gb INTEGER,
                    device_limit INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER,
                    referred_id INTEGER,
                    bonus_days INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tariffs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    days INTEGER,
                    price_stars INTEGER,
                    traffic_limit_gb INTEGER,
                    device_limit INTEGER,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # Default tariffs
            await db.execute("""
                INSERT OR IGNORE INTO tariffs (name, days, price_stars, traffic_limit_gb, device_limit)
                VALUES 
                ('1 месяц', 30, 300, 100, 2),
                ('3 месяца', 90, 800, 300, 3),
                ('6 месяцев', 180, 1400, 600, 5),
                ('12 месяцев', 365, 2500, 1200, 10)
            """)
            
            await db.commit()

    async def get_or_create_user(self, user_id: int, username: str = None, first_name: str = None, referred_by: int = None):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            user = await cursor.fetchone()
            
            if not user:
                await db.execute(
                    "INSERT INTO users (user_id, username, first_name, referred_by) VALUES (?, ?, ?, ?)",
                    (user_id, username, first_name, referred_by)
                )
                await db.commit()
                
                # Give referral bonus if applicable
                if referred_by:
                    await self.give_referral_bonus(referred_by, user_id)
            
            return user

    async def give_referral_bonus(self, referrer_id: int, referred_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            # Check if already referred
            cursor = await db.execute(
                "SELECT id FROM referrals WHERE referred_id = ?", (referred_id,)
            )
            if await cursor.fetchone():
                return
            
            bonus_days = 7  # TODO: брать из config.settings.REFERRAL_BONUS_DAYS
            await db.execute(
                "INSERT INTO referrals (referrer_id, referred_id, bonus_days) VALUES (?, ?, ?)",
                (referrer_id, referred_id, bonus_days)
            )
            
            # Add bonus to referrer's next subscription
            await db.execute(
                "UPDATE users SET referral_bonus_claimed = referral_bonus_claimed + ? WHERE user_id = ?",
                (bonus_days, referrer_id)
            )
            await db.commit()

    async def create_subscription(
        self, 
        user_id: int, 
        client_name: str, 
        node_name: str,
        expires_at: datetime,
        traffic_limit_gb: Optional[int] = None,
        device_limit: Optional[int] = None
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO subscriptions 
                (user_id, client_name, node_name, expires_at, traffic_limit_gb, device_limit)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, client_name, node_name, expires_at, traffic_limit_gb, device_limit))
            await db.commit()

    async def get_user_subscriptions(self, user_id: int) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT * FROM subscriptions 
                WHERE user_id = ? AND is_active = 1 
                ORDER BY expires_at DESC
            """, (user_id,))
            rows = await cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "client_name": row[2],
                    "node_name": row[3],
                    "expires_at": row[4],
                    "traffic_limit_gb": row[5],
                    "device_limit": row[6]
                }
                for row in rows
            ]

    async def get_all_tariffs(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM tariffs WHERE is_active = 1")
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "days": row[2],
                    "price_stars": row[3],
                    "traffic_limit_gb": row[4],
                    "device_limit": row[5]
                }
                for row in rows
            ]

    async def get_referral_stats(self, user_id: int) -> Dict:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,)
            )
            count = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                "SELECT SUM(bonus_days) FROM referrals WHERE referrer_id = ?", (user_id,)
            )
            total_bonus = (await cursor.fetchone())[0] or 0
            
            return {"referrals": count, "bonus_days": total_bonus}

    async def get_admin_stats(self) -> Dict:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM subscriptions WHERE is_active = 1")
            active_subs = (await cursor.fetchone())[0]
            
            return {
                "total_users": total_users,
                "active_subscriptions": active_subs
            }