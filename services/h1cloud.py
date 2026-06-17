import aiohttp
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class H1CloudAPI:
    def __init__(self, base_url: str, token: str, verify_ssl: bool = False):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.verify_ssl = verify_ssl
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(
                    method,
                    url,
                    headers=self.headers,
                    json=data,
                    ssl=self.verify_ssl
                ) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        logger.error(f"H1Cloud API error {resp.status}: {text}")
                        return {"ok": False, "error": text, "status": resp.status}
                    try:
                        return await resp.json()
                    except:
                        return {"ok": True, "raw": text}
            except Exception as e:
                logger.exception(f"Request failed to {url}: {e}")
                return {"ok": False, "error": str(e)}

    # ==================== CLIENT MANAGEMENT ====================

    async def create_client(
        self,
        name: str,
        days: int,
        traffic_limit_gb: Optional[int] = None,
        device_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create new client. Returns client data including links if available."""
        payload = {
            "name": name,
            "days": days
        }
        if traffic_limit_gb is not None:
            payload["traffic_limit_gb"] = traffic_limit_gb
        if device_limit is not None:
            payload["device_limit"] = device_limit

        return await self._request("POST", "/create", payload)

    async def get_clients(self) -> List[Dict]:
        """Get all clients"""
        result = await self._request("GET", "/clients")
        if result.get("ok"):
            return result.get("clients", [])
        return []

    async def get_client(self, name: str) -> Optional[Dict]:
        """Get single client by name"""
        result = await self._request("GET", f"/clients/{name}")
        if result.get("ok"):
            return result
        return None

    async def renew_client(self, name: str, days: int) -> Dict[str, Any]:
        """Renew client subscription"""
        return await self._request("PATCH", "/edit", {
            "name": name,
            "days": days
        })

    async def delete_client(self, name: str) -> Dict[str, Any]:
        """Delete client"""
        return await self._request("DELETE", f"/clients/{name}")

    async def ban_client(self, name: str, reason: str = "") -> Dict[str, Any]:
        """Ban client"""
        return await self._request("PATCH", f"/clients/{name}/ban", {"reason": reason})

    async def unban_client(self, name: str) -> Dict[str, Any]:
        """Unban client"""
        return await self._request("PATCH", f"/clients/{name}/unban")

    async def get_keys(self) -> Dict[str, Any]:
        """Get all clients with full VLESS links (from key.txt)"""
        return await self._request("GET", "/keys")

    async def get_key_txt(self) -> str:
        """Get raw key.txt content"""
        result = await self._request("GET", "/key.txt")
        return result.get("raw", "") if result.get("ok") else ""

    # ==================== NODE & SYSTEM ====================

    async def get_status(self) -> Dict[str, Any]:
        """Get server status"""
        return await self._request("GET", "/status")

    async def get_node_name(self) -> str:
        """Get current node name"""
        result = await self._request("GET", "/node")
        return result.get("node_name", "Unknown") if result.get("ok") else "Unknown"

    async def set_node_name(self, name: str) -> Dict[str, Any]:
        """Set node name (affects link tags)"""
        return await self._request("PATCH", "/node", {"node_name": name})

    # ==================== FEDERATION ====================

    async def set_federation_upstream(self, api_url: str, token: str) -> Dict[str, Any]:
        """Connect node to master (federation)"""
        return await self._request("PATCH", "/federation", {
            "api_url": api_url,
            "token": token
        })

    async def sync_federation(self) -> Dict[str, Any]:
        """Force sync with upstream"""
        return await self._request("GET", "/federation/sync")

    async def get_federation(self) -> Dict[str, Any]:
        """Get current federation config"""
        return await self._request("GET", "/federation")

    # ==================== PEERS (for master) ====================

    async def add_peer(self, name: str, url: str) -> Dict[str, Any]:
        """Add remote node to subscription aggregator"""
        return await self._request("POST", "/peers", {
            "name": name,
            "url": url
        })

    async def get_peers(self) -> List[Dict]:
        """Get all peers"""
        result = await self._request("GET", "/peers")
        if result.get("ok"):
            return result.get("peers", [])
        return []

    # ==================== SUBSCRIPTION ====================

    async def get_subscription_url(self, client_uuid: str, base_sub_url: str) -> str:
        """Build subscription URL for client"""
        return f"{base_sub_url}/sub/{client_uuid}"

    # ==================== UTILS ====================

    async def health_check(self) -> bool:
        """Check if API is reachable"""
        result = await self._request("GET", "/health")
        return result.get("ok", False)