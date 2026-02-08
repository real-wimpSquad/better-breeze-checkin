from __future__ import annotations

import httpx
from typing import Any

from .config import get_settings


class BreezeClient:
    def __init__(self):
        settings = get_settings()
        self.subdomain = settings.breeze_subdomain
        self.base_url = f"https://{self.subdomain}.breezechms.com/api"
        self.ajax_url = f"https://{self.subdomain}.breezechms.com/ajax"
        self.api_key = settings.breeze_api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"Api-Key": self.api_key},
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> Any:
        client = await self._get_client()
        url = f"{self.base_url}/{endpoint}"
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    async def get_events(
        self,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        """Get list of events, optionally filtered by date range."""
        params: dict[str, str] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return await self._request("GET", "events", params=params or None)

    async def get_event_instances(self, event_id: str) -> list[dict]:
        """Get instances for an event."""
        return await self._request(
            "GET", "events", params={"details": "1", "event_id": event_id}
        )

    async def get_eligible_people(self, instance_id: str) -> list[dict]:
        """Get people eligible for check-in at an event instance."""
        return await self._request(
            "POST",
            "events/attendance/eligible",
            params={"instance_id": instance_id},
        )

    async def add_attendance(self, instance_id: str, person_id: str) -> bool:
        """Check in a person to an event instance."""
        result = await self._request(
            "POST",
            "events/attendance/add",
            params={"instance_id": instance_id, "person_id": person_id},
        )
        return result is True or result == "true"

    async def delete_attendance(self, instance_id: str, person_id: str) -> bool:
        """Check out a person from an event instance."""
        result = await self._request(
            "POST",
            "events/attendance/delete",
            params={"instance_id": instance_id, "person_id": person_id},
        )
        return result is True or result == "true"

    async def list_attendance(self, instance_id: str) -> list[dict]:
        """List who is checked in to an event instance."""
        return await self._request(
            "POST",
            "events/attendance/list",
            params={"instance_id": instance_id},
        )

    async def get_person(self, person_id: str) -> dict:
        """Get full person details."""
        result = await self._request(
            "GET", "people", params={"details": "1", "filter_json": f'{{"id":"{person_id}"}}'}
        )
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result

    async def get_family(self, person_id: str) -> list[dict]:
        """
        Get family members for a person via /people/{id} endpoint.
        Returns list of family member records.
        """
        result = await self._request("GET", f"people/{person_id}")
        if isinstance(result, dict):
            return result.get("family", [])
        return []

    async def get_person_with_family(self, person_id: str) -> dict:
        """Get a person and their family members in one call."""
        person = await self.get_person(person_id)
        family = await self.get_family(person_id)
        person["family"] = family
        return person

    async def search_people(self, query: str) -> list[dict]:
        """Search for people by name."""
        client = await self._get_client()
        url = f"{self.ajax_url}/search_checkin_people"
        try:
            response = await client.post(url, data={"query": query})
            response.raise_for_status()
            return response.json()
        except Exception:
            return await self._request(
                "GET", "people", params={"details": "0", "filter_json": f'{{"name":"{query}"}}'}
            )


# Singleton instance
_client: BreezeClient | None = None


def get_breeze_client() -> BreezeClient:
    global _client
    if _client is None:
        _client = BreezeClient()
    return _client
