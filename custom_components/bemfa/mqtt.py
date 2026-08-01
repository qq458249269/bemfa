"""Support for bemfa service."""
from __future__ import annotations
import asyncio

import logging
from typing import Any

import paho.mqtt.client as mqtt

from homeassistant.const import (
    EVENT_STATE_CHANGED,
)
from homeassistant.core import HomeAssistant

from .const import (
    INTERVAL_PING_RECEIVE,
    INTERVAL_PING_SEND,
    MAX_PING_LOST,
    MQTT_HOST,
    MQTT_KEEPALIVE,
    MQTT_PORT,
    TOPIC_PING,
    TOPIC_PUBLISH,
)

from .sync import Sync

_LOGGING = logging.getLogger(__name__)


class BemfaMqtt:
    """Set up mqtt connections to bemfa service, subscribe topcs and publish messages."""

    def __init__(
        self, hass: HomeAssistant, uid: str
    ) -> None:
        """Initialize."""
        self._hass = hass

        # Init MQTT connection
        self._mqttc = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1, uid, protocol=mqtt.MQTTv311
        )

        self._topic_to_sync: dict[str, Sync] = {}

        self._remove_listener: Any = None
        self._ping_publish_timer: Any = None
        self._ping_receive_timer: Any = None
        self._ping_lost: int = 0

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
        # Send heartbeat packages to check the connection first in case we failed to make mqtt connection
        self._ping()

        self._mqttc.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)
        self._mqttc.on_message = self._mqtt_on_message

        self._mqttc.loop_start()

        # Listen for state changes
        self._remove_listener = self._hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._state_listener
        )

        # Listen for heartbeat packages
        self._mqttc.subscribe(TOPIC_PING, 1)

    def _ping(self):
        async def _receive_job():
            await asyncio.sleep(INTERVAL_PING_RECEIVE)
            self._ping_lost += 1
            if self._ping_lost == MAX_PING_LOST:
                self._ping_lost = 0
                self._reconnect()

        async def _publish_job():
            await asyncio.sleep(INTERVAL_PING_SEND)
            self._mqttc.publish(TOPIC_PING, "ping")
            self._ping_receive_timer = asyncio.ensure_future(_receive_job())
            self._ping()

        self._ping_publish_timer = asyncio.ensure_future(_publish_job())

    def _reconnect(self):
        try:
            self.disconnect()
            self.connect()
        except Exception:
            _LOGGING.exception(
                "Failed to reconnect to bemfa MQTT server, will retry after a heartbeat cycle"
            )
            # Keep the heartbeat running so a later retry can succeed
            self._ping()
            return
        for sync in self._topic_to_sync.values():
            self.create_sync(sync)

    def disconnect(self) -> None:
        """Disconnect from Bamfa service."""

        # Remove timers
        if self._ping_publish_timer is not None:
            self._ping_publish_timer.cancel()
        if self._ping_receive_timer is not None:
            self._ping_receive_timer.cancel()

        # Unlisten for state changes
        if self._remove_listener is not None:
            self._remove_listener()

        # Destroy MQTT connection
        self._mqttc.loop_stop()
        self._mqttc.disconnect()

    def _state_listener(self, event):
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        entity_id = new_state.entity_id
        for (topic, sync) in self._topic_to_sync.items():
            if entity_id in sync.get_watched_entity_ids():
                self._mqttc.publish(
                    TOPIC_PUBLISH.format(topic=topic),
                    sync.generate_msg(),
                )

    def _mqtt_on_message(self, _mqtt_client, _userdata, message) -> None:
        if message.topic == TOPIC_PING:
            if self._ping_receive_timer is not None:
                self._ping_receive_timer.cancel()
                self._ping_lost = 0
            return

        sync = self._topic_to_sync.get(message.topic)
        if sync is None:
            return

        # paho callbacks run on its network thread; hop to the event loop
        # to keep state/service calls off the network thread
        self._hass.loop.call_soon_threadsafe(self._handle_message, sync, message.payload)

    def _handle_message(self, sync: Sync, payload: bytes) -> None:
        """Handle a message from a sync topic on the event loop."""
        try:
            sync.resolve_msg(payload.decode())
        except Exception:
            _LOGGING.exception("Failed to handle message for topic %s", sync.topic)
