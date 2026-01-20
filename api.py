# wow_terminal/api.py (Added try-except for fetches, token)
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
        try:
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
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Token fetch failed: {str(e)}")
        except KeyError:
            raise ValueError("Invalid token response structure")

    def fetch(self, endpoint: str, namespace: str = "dynamic-classic-us", locale: str = "en_US") -> dict:
        try:
            token = self._get_token()
            url = f"https://{self.region}.api.blizzard.com{endpoint}?namespace={namespace}&locale={locale}"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ValueError(f"API fetch failed for {endpoint}: {str(e)}")
        except ValueError as ve:
            raise ve  # Propagate token errors

    def get_connected_realm_id(self, realm_name: str) -> Optional[int]:
        try:
            index_data = self.fetch("/data/wow/connected-realm/index")
            for cr in index_data.get("connected_realms", []):
                href = cr["href"]
                cr_id = href.split("/")[-1]
                details = self.fetch(f"/data/wow/connected-realm/{cr_id}")
                for realm in details.get("realms", []):
                    if realm_name.lower() in realm["name"].lower():
                        print(f"Found {realm['name']} in connected_realm {details['id']}")
                        return details["id"]
            return None
        except ValueError as e:
            print(f"Error finding realm {realm_name}: {e}")
            return None

    def get_item_details(self, item_id: int) -> Dict:
        try:
            data = self.fetch(f"/data/wow/item/{item_id}", namespace="static-classic-us")
            return {
                "name": data.get("name", f"Item {item_id}"),
                "icon": data.get("media", {}).get("key", {}).get("href") if "media" in data else None
            }
        except ValueError as e:
            print(f"Error fetching item {item_id}: {e}")
            return {"name": f"Item {item_id}", "icon": None}

    def get_auctions(self, connected_realm_id: int) -> dict:
        try:
            return self.fetch(f"/data/wow/connected-realm/{connected_realm_id}/auctions")
        except ValueError as e:
            print(f"Error fetching auctions for realm {connected_realm_id}: {e}")
            return {"auctions": []}
