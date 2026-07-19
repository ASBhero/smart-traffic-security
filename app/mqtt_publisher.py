"""
MQTT Publisher for FOTA notifications
Publishes firmware availability notifications to devices
Optional enhancement layer - notifications only, not security-critical
"""
import json
import os
from datetime import datetime
from typing import Optional
import logging

# Try to import paho-mqtt, but don't fail if not available
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None

logger = logging.getLogger(__name__)

class FOTAMQTTPublisher:
    def __init__(self, broker_host: str = "mqtt-broker", broker_port: int = 1883, 
                 enabled: bool = True):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.enabled = enabled and MQTT_AVAILABLE
        self.client = None
        self.connected = False

    def connect(self):
        """Connect to MQTT broker (non-blocking, optional)"""
        if not self.enabled:
            logger.info("[MQTT] MQTT disabled or paho-mqtt not installed")
            return
        
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish
            
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            logger.info(f"[MQTT] Connecting to broker {self.broker_host}:{self.broker_port}")
        except Exception as e:
            logger.warning(f"[MQTT] Failed to connect to broker: {e} (MQTT notifications disabled)")
            self.connected = False

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("[MQTT] Disconnected from broker")
            except Exception as e:
                logger.warning(f"[MQTT] Disconnect error: {e}")
            self.connected = False

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties=None):
        logger.info(f"[MQTT] Connected to broker with result code {reason_code}")
        self.connected = True

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        logger.warning(f"[MQTT] Disconnected from broker with result code {reason_code}")
        self.connected = False

    def _on_publish(self, client, userdata, mid, reason_codes=None, properties=None):
        logger.debug(f"[MQTT] Message {mid} published successfully")

    def publish_firmware_available(self, hardware_target: str, version: str, 
                                   urgency: str = "recommended", 
                                   release_notes: str = None,
                                   binary_hash: str = None):
        """
        Publish firmware availability notification
        
        Args:
            hardware_target: e.g., "ESP32-S3"
            version: e.g., "1.0.0"
            urgency: "recommended" or "critical"
            release_notes: Optional release notes
            binary_hash: SHA-256 hash of firmware binary
        """
        if not self.connected:
            logger.debug("[MQTT] Broker not connected, skipping firmware notification")
            return False

        topic = f"fota/notifications/{hardware_target}/firmware_available"
        
        payload = {
            "version": version,
            "urgency": urgency,
            "release_notes": release_notes or "",
            "binary_hash": binary_hash or "",
            "release_date": datetime.utcnow().isoformat() + "Z",
            "download_endpoint": f"/api/v1/firmware/{version}/binary"
        }

        try:
            result = self.client.publish(topic, json.dumps(payload), qos=1, retain=True)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"[MQTT] Published firmware notification: {topic} v{version}")
                return True
            else:
                logger.error(f"[MQTT] Publish failed with code {result.rc}")
                return False
        except Exception as e:
            logger.error(f"[MQTT] Publish error: {e}")
            return False

    def publish_maintenance_window(self, hardware_target: str, 
                                  start_time: str, end_time: str,
                                  reason: str = "Scheduled maintenance"):
        """Publish maintenance window notification"""
        if not self.connected:
            logger.debug("[MQTT] Broker not connected, skipping maintenance notification")
            return False

        topic = f"fota/notifications/{hardware_target}/maintenance_window"
        payload = {
            "event": "server_maintenance",
            "reason": reason,
            "start_time": start_time,
            "end_time": end_time
        }

        try:
            self.client.publish(topic, json.dumps(payload), qos=1, retain=False)
            logger.info(f"[MQTT] Published maintenance notification: {topic}")
            return True
        except Exception as e:
            logger.error(f"[MQTT] Maintenance notification error: {e}")
            return False

    def publish_rollback_available(self, hardware_target: str, version: str,
                                  reason: str = "If needed"):
        """Publish rollback availability notification"""
        if not self.connected:
            logger.debug("[MQTT] Broker not connected, skipping rollback notification")
            return False

        topic = f"fota/notifications/{hardware_target}/rollback_available"
        payload = {
            "version": version,
            "reason": reason,
            "available_at": datetime.utcnow().isoformat() + "Z"
        }

        try:
            self.client.publish(topic, json.dumps(payload), qos=1, retain=False)
            logger.info(f"[MQTT] Published rollback notification: {topic} v{version}")
            return True
        except Exception as e:
            logger.error(f"[MQTT] Rollback notification error: {e}")
            return False

    def get_status(self):
        """Get MQTT publisher status"""
        return {
            "enabled": self.enabled,
            "connected": self.connected,
            "broker": f"{self.broker_host}:{self.broker_port}" if self.enabled else "disabled"
        }
