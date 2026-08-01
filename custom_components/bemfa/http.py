"""Bemfa http apis."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CREATE_TOPIC_URL,
    CREATE_TOPIC_URL_LEGACY,
    DEL_TOPIC_URL,
    FETCH_TOPICS_URL,
    RENAME_TOPIC_URL,
    RENAME_TOPIC_URL_LEGACY,
    TOPIC_PREFIX,
)

_LOGGING = logging.getLogger(__name__)


class BemfaHttp:
    """Send http requests to bemfa service."""

    def __init__(self, hass: HomeAssistant, uid: str) -> None:
        """Initialize."""
        self._hass = hass
        self._uid = uid

    async def _post(
        self, url: str, data: dict[str, str | int]
    ) -> dict[str, Any] | None:
        """POST JSON to the bemfa API. Return the parsed response, or None on failure."""
        session = async_get_clientsession(self._hass)
        try:
            async with session.post(url, json=data) as res:
                res.raise_for_status()
                return await res.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            _LOGGING.warning("Failed to POST %s: %s", url, err)
            return None

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
            data = res_dict.get("data", [])
            if not isinstance(data, list):
                _LOGGING.warning("Unexpected response from bemfa API: %s", res_dict)
                return {}
            return {
                topic.get("topic"): topic.get("name")
                for topic in data
                if isinstance(topic, dict)
                and topic.get("topic", "").startswith(TOPIC_PREFIX)
            }

    async def async_create_topic(self, topic: str, name: str) -> None:
        """Create a topic to bemfa service."""
        if not topic.startswith(TOPIC_PREFIX):
            return
        payload = {
            "uid": self._uid,
            "topic": topic,
            "type": 1,
            "name": name,
        }
        res_dict = await self._post(CREATE_TOPIC_URL, payload)
        if res_dict is None or res_dict.get("code") != 0:
            _LOGGING.warning(
                "createTopic via %s failed (%s), trying legacy endpoint",
                CREATE_TOPIC_URL,
                res_dict,
            )
            await self._post(CREATE_TOPIC_URL_LEGACY, payload)

    async def async_rename_topic(self, topic: str, name: str) -> None:
        """Rename a topic in bemfa service."""
        if not topic.startswith(TOPIC_PREFIX):
            return
        payload = {
            "uid": self._uid,
            "topic": topic,
            "type": 1,
            "name": name,
        }
        res_dict = await self._post(RENAME_TOPIC_URL, payload)
        if res_dict is None or res_dict.get("code") != 0:
            _LOGGING.warning(
                "modifyName via %s failed (%s), trying legacy endpoint",
                RENAME_TOPIC_URL,
                res_dict,
            )
            await self._post(RENAME_TOPIC_URL_LEGACY, payload)

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
