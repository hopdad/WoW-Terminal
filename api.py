import requests
import base64
from datetime import datetime, timedelta
from typing import Dict, Optional, List

class BlizzardAPI:
    def __init__(self, client_id: str, client_secret: str, region: str = 'us'):
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self.token = None
        self.token_expiry = None

    def _get_token(self) -> str:
        if self.token and self.token_expiry > datetime.now():
            return self.token
        url = f"https://oauth.battle.net/token"
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}
        data = {"grant_type": "client_credentials"}
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()
        self.token = token_data["access_token"]
        self.token_expiry = datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600) - 60)
        return self.token

    def fetch(self, endpoint: str, namespace: str = "dynamic-us", locale: str = "en_US") -> dict:
        token = self._get_token()
        url = f"https://{self.region}.api.blizzard.com{endpoint}?namespace={namespace}&locale={locale}"
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def get_connected_realm_id(self, realm_name: str) -> Optional[int]:
        """Find connected_realm_id by partial realm name match."""
        index_data = self.fetch("/data/wow/connected-realm/index")
        for cr in index_data.get("connected_realms", []):
            try:
                details = self.fetch(f"/data/wow/connected-realm/{cr['href'].split('/')[-1]}")
                for realm in details.get("realms", []):
                    if realm_name.lower() in realm["name"].lower():
                        print(f"Found {realm['name']} in connected_realm {cr['id']}")
                        return details["id"]
            except:
                continue
        return None

    def get_item_details(self, item_id: int) -> Dict:
        """Get item name and media."""
        data = self.fetch(f"/data/wow/item/{item_id}", namespace="static-us")
        return {
            "name": data["name"],
            "icon": data["media"]["key"]["href"] if "media" in data else None
        }

    def get_auctions(self, connected_realm_id: int) -> dict:
        return self.fetch(f"/data/wow/connected-realm/{connected_realm_id}/auctions")

    def get_commodities(self) -> dict:
        return self.fetch("/data/wow/auctions/commodities")
