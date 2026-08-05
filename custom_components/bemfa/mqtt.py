"""Support for bemfa service."""
from __future__ import annotations

import logging
from typing import Any

import paho.mqtt.client as mqtt

from homeassistant.const import (
    EVENT_STATE_CHANGED,
)
from homeassistant.core import HomeAssistant

from .const import (
    MQTT_HOST,
    MQTT_KEEPALIVE,
    MQTT_PORT,
    TOPIC_PUBLISH,
)

from .sync import Sync

_LOGGING = logging.getLogger(__name__)


class BemfaMqtt:
    """Set up mqtt connections to bemfa service, subscribe topcs and publish messages."""

    def __init__(self, hass: HomeAssistant, uid: str) -> None:
        """Initialize."""
        self._hass = hass

        # Init MQTT connection
        self._mqttc = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1, uid, protocol=mqtt.MQTTv311
        )
        self._mqttc.on_connect = self._mqtt_on_connect
        self._mqttc.on_disconnect = self._mqtt_on_disconnect
        self._mqttc.on_message = self._mqtt_on_message

        self._topic_to_sync: dict[str, Sync] = {}

        self._remove_listener: Any = None

    def create_sync(self, sync: Sync):
        """Add an topic to our watching list."""
        self._topic_to_sync[sync.topic] = sync
        self._mqttc.publish(
            TOPIC_PUBLISH.format(topic=sync.topic),
            sync.generate_msg(),
        )
        self._mqttc.subscribe(sync.topic, 1)

    def modify_sync(self, sync: Sync):
        """Modify a sync."""
        if sync.topic in self._topic_to_sync:
            self._topic_to_sync[sync.topic] = sync
            self._mqttc.publish(
                TOPIC_PUBLISH.format(topic=sync.topic),
                sync.generate_msg(),
            )

    def destroy_sync(self, topic: str):
        """Remove an topic from our watching list."""
        if topic in self._topic_to_sync:
            self._topic_to_sync.pop(topic)
        self._mqttc.unsubscribe(topic)

    def connect(self) -> None:
        """Connect to Bamfa service."""
        # connect_async lets the network loop keep retrying until connected
        self._mqttc.connect_async(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)
        self._mqttc.loop_start()

        # Listen for state changes
        self._remove_listener = self._hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._state_listener
        )

    def disconnect(self) -> None:
        """Disconnect from Bamfa service."""

        # Unlisten for state changes
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None

        # Destroy MQTT connection
        self._mqttc.loop_stop()
        self._mqttc.disconnect()

    def _mqtt_on_connect(self, _mqtt_client, _userdata, _flags, rc) -> None:
        """Called on initial connection and every reconnection."""
        if rc != 0:
            _LOGGING.warning(
                "Failed to connect to bemfa MQTT server: %s, paho will keep retrying",
                rc,
            )
            return

        _LOGGING.info("Connected to bemfa MQTT server")

        # Subscriptions are lost on reconnection, subscribe them again
        for topic in list(self._topic_to_sync):
            self._mqttc.subscribe(topic, 1)

        # Re-publish current entity states on the hass event loop
        self._hass.loop.call_soon_threadsafe(self._republish_states)

    def _mqtt_on_disconnect(self, _mqtt_client, _userdata, rc) -> None:
        """Called when disconnected, unexpectedly or not."""
        if rc != 0:
            _LOGGING.warning(
                "Disconnected from bemfa MQTT server: %s, paho will reconnect", rc
            )

    def _republish_states(self):
        """Publish the current state of every sync, runs on the hass event loop."""
        for sync in list(self._topic_to_sync.values()):
            try:
                self._mqttc.publish(
                    TOPIC_PUBLISH.format(topic=sync.topic),
                    sync.generate_msg(),
                )
            except Exception:
                _LOGGING.exception("Failed to republish state for topic %s", sync.topic)

    def _state_listener(self, event):
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        entity_id = new_state.entity_id
        for (topic, sync) in self._topic_to_sync.items():
            if entity_id in sync.get_watched_entity_ids():
                try:
                    self._mqttc.publish(
                        TOPIC_PUBLISH.format(topic=topic),
                        sync.generate_msg(),
                    )
                except Exception:
                    _LOGGING.exception("Failed to publish state for topic %s", topic)

    def _mqtt_on_message(self, _mqtt_client, _userdata, message) -> None:
        try:
            if message.topic in self._topic_to_sync:
                self._topic_to_sync[message.topic].resolve_msg(message.payload.decode())
        except Exception:
            _LOGGING.exception("Failed to handle message for topic %s", message.topic)
