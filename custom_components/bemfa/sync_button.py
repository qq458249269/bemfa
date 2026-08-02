"""Support for bemfa service."""
from __future__ import annotations

from collections.abc import Mapping, Callable
from typing import Any

from homeassistant.components.button import DOMAIN, SERVICE_PRESS
from homeassistant.util.read_only_dict import ReadOnlyDict

from .const import MSG_OFF, MSG_ON, TopicSuffix
from .sync import SYNC_TYPES, ControllableSync


@SYNC_TYPES.register("button")
class Button(ControllableSync):
    """Sync a hass button entity to bemfa switch device.

    A button has no persistent state: bemfa always reports it as ``off``.
    Every ``on`` command received from bemfa triggers one press.
    """

    @staticmethod
    def get_config_step_id() -> str:
        return "sync_config_button"

    @staticmethod
    def _get_topic_suffix() -> TopicSuffix:
        return TopicSuffix.SWITCH

    @staticmethod
    def _supported_domain() -> str:
        return DOMAIN

    def _msg_generators(
        self,
    ) -> list[Callable[[str, ReadOnlyDict[Mapping[str, Any]]], str | int]]:
        return [lambda state, attributes: MSG_OFF]

    def _msg_resolvers(
        self,
    ) -> list[
        (
            int,
            int,
            Callable[
                [list[str | int], ReadOnlyDict[Mapping[str, Any]]],
                (str, str, dict[str, Any]),
            ],
        )
    ]:
        return [
            (
                0,
                1,
                lambda msg, attributes: (
                    (DOMAIN, SERVICE_PRESS, {}) if msg[0] == MSG_ON else None
                ),
            )
        ]
