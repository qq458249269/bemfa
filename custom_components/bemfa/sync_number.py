"""Support for bemfa service."""
from __future__ import annotations

from homeassistant.components.number import DOMAIN
from homeassistant.core import HomeAssistant

from .const import TopicSuffix
from .sync import SYNC_TYPES, Sync


@SYNC_TYPES.register("number")
class Number(Sync):
    """Sync a hass number entity to bemfa sensor device.

    Numbers are read-only: bemfa receives the current value whenever
    the number entity changes.
    """

    @staticmethod
    def get_config_step_id() -> str:
        return "sync_config_number"

    @staticmethod
    def _get_topic_suffix() -> TopicSuffix:
        return TopicSuffix.SENSOR

    @classmethod
    def collect_supported_syncs(cls, hass: HomeAssistant):
        return [
            cls(hass, state.entity_id, state.name)
            for state in hass.states.async_all(DOMAIN)
        ]

    def get_watched_entity_ids(self) -> list[str]:
        return [self._entity_id]

    def _generate_msg_parts(self) -> list[str]:
        state = self._hass.states.get(self._entity_id)
        if state is None:
            return []
        return ["", "", "", state.state]
