from pydantic_settings import BaseSettings
from typing import List, Dict, Optional
import os

class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: List[int] = []

    # H1Cloud Master API
    H1CLOUD_MASTER_API_URL: str
    H1CLOUD_MASTER_TOKEN: str

    # Subscription base URL (usually the same as API but on SUB port)
    H1CLOUD_MASTER_SUB_URL: Optional[str] = None

    # Additional nodes (name:url:token)
    H1CLOUD_NODES: str = ""

    DATABASE_PATH: str = "data/vpn_bot.db"
    REFERRAL_BONUS_DAYS: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def nodes(self) -> Dict[str, dict]:
        """Parse nodes from H1CLOUD_NODES"""
        nodes = {}
        if self.H1CLOUD_NODES:
            for item in self.H1CLOUD_NODES.split(","):
                if item.strip():
                    parts = item.strip().split(":")
                    if len(parts) >= 3:
                        name = parts[0]
                        url = ":".join(parts[1:-1])
                        token = parts[-1]
                        nodes[name] = {"url": url, "token": token}
        return nodes

    @property
    def master_sub_url(self) -> str:
        """Get subscription base URL"""
        if self.H1CLOUD_MASTER_SUB_URL:
            return self.H1CLOUD_MASTER_SUB_URL.rstrip('/')
        # Try to guess from API URL
        return self.H1CLOUD_MASTER_API_URL.replace("/api", "").rstrip('/')

settings = Settings()