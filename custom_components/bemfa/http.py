"""Bemfa http apis."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CREATE_TOPIC_URL,
    DEL_TOPIC_URL,
    FETCH_TOPICS_URL,
    RENAME_TOPIC_URL,
    TOPIC_PREFIX,
)

_LOGGING = logging.getLogger(__name__)


class BemfaHttp:
    """Send http requests to bemfa service."""

    def __init__(self, hass: HomeAssistant, uid: str) -> None:
        """Initialize."""
        self._hass = hass
        self._uid = uid

    async def _post(self, url: str, data: dict[str, str | int]) -> None:
        """POST JSON to the bemfa API and raise on errors."""
        session = async_get_clientsession(self._hass)
        async with session.post(url, json=data) as res:
            res.raise_for_status()
            res_dict = await res.json(content_type=None)
            if res_dict.get("code") != 0:
                raise HomeAssistantError(f"bemfa API error: {res_dict}")

    async def async_fetch_all_topics(self) -> dict[str, str]:
        """Fetch all topics created by us from bemfa service."""
        session = async_get_clientsession(self._hass)
        async with session.get(
            FETCH_TOPICS_URL.format(uid=self._uid),
        ) as res:
            res.raise_for_status()
            res_dict = await res.json(content_type=None)
            if res_dict.get("code") != 0:
                _LOGGING.warning("Unexpected response from bemfa API: %s", res_dict)
                return {}
            return {
                topic["topic"]: topic["name"]
                for topic in res_dict.get("data", [])
                if topic.get("topic", "").startswith(TOPIC_PREFIX)
            }

    async def async_create_topic(self, topic: str, name: str) -> None:
        """Create a topic to bemfa service."""
        if not topic.startswith(TOPIC_PREFIX):
            return
        await self._post(
            CREATE_TOPIC_URL,
            data={
                "uid": self._uid,
                "topic": topic,
                "type": 1,
                "name": name,
            },
        )

    async def async_rename_topic(self, topic: str, name: str) -> None:
        """Rename a topic in bemfa service."""
        if not topic.startswith(TOPIC_PREFIX):
            return
        await self._post(
            RENAME_TOPIC_URL,
            data={
                "uid": self._uid,
                "topic": topic,
                "type": 1,
                "name": name,
            },
        )

    async def async_del_topic(self, topic: str) -> None:
        """Delete a topic from bemfa service."""
        if not topic.startswith(TOPIC_PREFIX):
            return
        await self._post(
            DEL_TOPIC_URL,
            data={
                "uid": self._uid,
                "topic": topic,
                "type": 1,
            },
        )
