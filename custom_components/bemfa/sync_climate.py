"""Support for bemfa service."""
from __future__ import annotations
from typing import Any, Final

import logging
from collections.abc import Mapping, Callable
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    PRESET_ECO,
    PRESET_SLEEP,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_SET_SWING_MODE,
    SWING_OFF,
    SWING_HORIZONTAL,
    SWING_VERTICAL,
    SWING_BOTH,
    HVACMode,
    DOMAIN,
)

from homeassistant.const import (
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util.read_only_dict import ReadOnlyDict
from .const import (
    MSG_OFF,
    MSG_ON,
    MSG_SEPARATOR,
    OPTIONS_FAN_SPEED_0_VALUE,
    OPTIONS_FAN_SPEED_1_VALUE,
    OPTIONS_FAN_SPEED_2_VALUE,
    OPTIONS_FAN_SPEED_3_VALUE,
    OPTIONS_FAN_SPEED_4_VALUE,
    OPTIONS_FAN_SPEED_5_VALUE,
    OPTIONS_SWING_OFF_VALUE,
    OPTIONS_SWING_HORIZONTAL_VALUE,
    OPTIONS_SWING_VERTICAL_VALUE,
    OPTIONS_SWING_BOTH_VALUE,
    TopicSuffix,
)
from .utils import has_key
from .sync import SYNC_TYPES, ControllableSync

_LOGGING = logging.getLogger(__name__)

SUPPORTED_HVAC_MODES = [
    HVACMode.AUTO,
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.FAN_ONLY,
    HVACMode.DRY,
]

ATTR_OPTIONS_NAME: Final = "attr_options_name"
ATTR_NAME: Final = "attr_name"
CFG_KEYS: Final = "cfg_keys"
CFG_VALUES: Final = "cfg_values"
CFG_SUGGESTED = "cfg_suggested"
DETAILS_CFG = [
    {
        ATTR_OPTIONS_NAME: ATTR_FAN_MODES,
        ATTR_NAME: ATTR_FAN_MODE,
        CFG_KEYS: [
            OPTIONS_FAN_SPEED_0_VALUE,
            OPTIONS_FAN_SPEED_1_VALUE,
            OPTIONS_FAN_SPEED_2_VALUE,
            OPTIONS_FAN_SPEED_3_VALUE,
            OPTIONS_FAN_SPEED_4_VALUE,
            OPTIONS_FAN_SPEED_5_VALUE,
        ],
        CFG_VALUES: [0, 1, 2, 3, 4, 5],
        CFG_SUGGESTED: [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_HIGH, FAN_HIGH],
    },
    {
        ATTR_OPTIONS_NAME: ATTR_SWING_MODES,
        ATTR_NAME: ATTR_SWING_MODE,
        CFG_KEYS: [
            OPTIONS_SWING_OFF_VALUE,
            OPTIONS_SWING_HORIZONTAL_VALUE,
            OPTIONS_SWING_VERTICAL_VALUE,
            OPTIONS_SWING_BOTH_VALUE,
        ],
        CFG_VALUES: [
            MSG_SEPARATOR.join(["0", "0"]),
            MSG_SEPARATOR.join(["1", "0"]),
            MSG_SEPARATOR.join(["0", "1"]),
            MSG_SEPARATOR.join(["1", "1"]),
        ],
        CFG_SUGGESTED: [SWING_OFF, SWING_HORIZONTAL, SWING_VERTICAL, SWING_BOTH],
    },
]


def _get_detail_value(
    attributes: dict[str, Any], sync_config: dict[str, str], detail_cfg: Any
) -> str:
    if has_key(attributes, detail_cfg[ATTR_NAME]):
        for i in range(len(detail_cfg[CFG_KEYS])):
            key = detail_cfg[CFG_KEYS][i]
            if (
                key in sync_config
                and sync_config[key] == attributes[detail_cfg[ATTR_NAME]]
            ):
                return detail_cfg[CFG_VALUES][i]
    return detail_cfg[CFG_VALUES][0]


@SYNC_TYPES.register("climate")
class Climate(ControllableSync):
    """Sync a hass climate entity to bemfa climate device."""

    @staticmethod
    def get_config_step_id() -> str:
        return "sync_config_climate"

    @staticmethod
    def _get_topic_suffix() -> TopicSuffix:
        return TopicSuffix.CLIMATE

    @staticmethod
    def _supported_domain() -> str:
        return DOMAIN

    def generate_details_schema(self) -> dict[str, Any]:
        schema = super().generate_details_schema()
        state = self._hass.states.get(self._entity_id)
        if state is not None:
            for _dc in DETAILS_CFG:
                if _dc[ATTR_OPTIONS_NAME] in state.attributes:
                    options = state.attributes[_dc[ATTR_OPTIONS_NAME]]
                    if options:
                        selector = SelectSelector(
                            SelectSelectorConfig(
                                options=options, mode=SelectSelectorMode.DROPDOWN
                            )
                        )
                        for i in range(len(_dc[CFG_KEYS])):
                            _k = _dc[CFG_KEYS][i]
                            _s = _dc[CFG_SUGGESTED][i]
                            schema[
                                vol.Optional(
                                    _k,
                                    description={
                                        "suggested_value": self._config[_k]
                                        if _k in self._config
                                        and self._config[_k] in options
                                        else _s
                                        if _s in options
                                        else options[0]
                                    },
                                )
                            ] = selector
        return schema

    def _msg_generators(
        self,
    ) -> list[Callable[[str, ReadOnlyDict[Mapping[str, Any]]], str | int]]:
        return [
            lambda state, attributes: MSG_OFF if state == HVACMode.OFF else MSG_ON,
            lambda state, attributes: SUPPORTED_HVAC_MODES.index(state) + 1
            if state in SUPPORTED_HVAC_MODES
            else "",
            lambda state, attributes: round(attributes[ATTR_TEMPERATURE])
            if has_key(attributes, ATTR_TEMPERATURE)
            else "",
            lambda state, attributes: _get_detail_value(
                attributes, self._config, DETAILS_CFG[0]
            ),
            lambda state, attributes: _get_detail_value(
                attributes, self._config, DETAILS_CFG[1]
            ),
        ]

    def _resolve_onoff(
        self,
        msg: list[str | int],
        attributes: ReadOnlyDict[Mapping[str, Any]],
    ) -> (str, str, dict[str, Any]) | None:
        """Resolve the on/off + mode/preset part of a bemfa climate message.

        Message format: ``on#mode`` where mode is:
        - 1..5 -> HVAC mode (auto/cool/heat/fan_only/dry)
        - 6    -> sleep preset
        - 7    -> eco preset
        A bare ``on``/``off`` turns the climate on/off.
        """
        if len(msg) > 1 and isinstance(msg[1], int):
            if 1 <= msg[1] <= len(SUPPORTED_HVAC_MODES):
                return (
                    DOMAIN,
                    SERVICE_SET_HVAC_MODE,
                    {ATTR_HVAC_MODE: SUPPORTED_HVAC_MODES[msg[1] - 1]},
                )
            preset = {6: PRESET_SLEEP, 7: PRESET_ECO}.get(msg[1])
            if preset and has_key(attributes, ATTR_PRESET_MODES):
                if preset in attributes[ATTR_PRESET_MODES]:
                    return (
                        DOMAIN,
                        SERVICE_SET_PRESET_MODE,
                        {ATTR_PRESET_MODE: preset},
                    )
            # mode 6/7 but the entity does not support the preset:
            # fall back to turning the climate on without changing the mode
        if msg[0] == MSG_ON:
            return (DOMAIN, SERVICE_TURN_ON, {})
        if msg[0] == MSG_OFF:
            return (DOMAIN, SERVICE_TURN_OFF, {})
        return None

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
                2,
                self._resolve_onoff,
            ),
            (
                2,
                3,
                lambda msg, attributes: (
                    (
                        DOMAIN,
                        SERVICE_SET_TEMPERATURE,
                        {ATTR_TEMPERATURE: msg[0]},
                    )
                    if isinstance(msg[0], int)
                    else None
                ),
            ),
            (
                3,
                4,
                lambda msg, attributes: (
                    DOMAIN,
                    SERVICE_SET_FAN_MODE,
                    {
                        ATTR_FAN_MODE: self._config[
                            DETAILS_CFG[0][CFG_KEYS][
                                DETAILS_CFG[0][CFG_VALUES].index(msg[0])
                            ]
                        ]
                    },
                ),
            ),
            (
                4,
                6,
                lambda msg, attributes: (
                    DOMAIN,
                    SERVICE_SET_SWING_MODE,
                    {
                        ATTR_SWING_MODE: self._config[
                            DETAILS_CFG[1][CFG_KEYS][
                                DETAILS_CFG[1][CFG_VALUES].index(
                                    MSG_SEPARATOR.join(map(str, msg))
                                )
                            ]
                        ]
                    },
                ),
            ),
        ]
