import paho.mqtt.client as mqtt
import time
import json
import threading
import datetime
import os
import socket


"""
Configurable MQTT client and publisher for meter readings.

Defaults are aligned to the local ingest script in simple-meter-dashboard/iot_scripts:
  - broker: localhost
  - port: 1883
  - topic: meter/readings
It enriches payloads with metadata fields that the ingest expects.
"""

# Defaults (can be overridden by config.jsonc or environment)
DEFAULTS = {
    "MQTT_BROKER": os.environ.get("MQTT_BROKER", "localhost"),
    "MQTT_PORT": int(os.environ.get("MQTT_PORT", "1883")),
    "MQTT_USERNAME": os.environ.get("MQTT_USER"),
    "MQTT_PASSWORD": os.environ.get("MQTT_PASS"),
    "MQTT_TOPIC": os.environ.get("MQTT_TOPIC", "meter/readings"),
    "MQTT_TLS": os.environ.get("MQTT_TLS", "0").lower() in ("1", "true", "yes"),
    "MQTT_QOS": int(os.environ.get("MQTT_QOS", "0")),
}

CONNECTION_CHECK_INTERVAL = 15  # seconds
LOG_FILE_NAME = "mqtt_log.txt"

published_msg = 0
client = None
logFile = None
mqtt_thread = None


def _read_jsonc(path):
    """Read a JSON-with-comments file (// line comments supported)."""
    try:
        with open(path, "r") as f:
            content = f.read()
        # strip // comments
        import re
        content = re.sub(r"//.*", "", content)
        return json.loads(content)
    except Exception:
        return {}


def _load_mqtt_config():
    cfg = dict(DEFAULTS)
    # Prefer project config file if present
    # Prefer externalized config at /home/pi/meter_config, then local project copy
    cfg_path = os.path.join("/home/pi/meter_config", "config.jsonc")
    if not os.path.exists(cfg_path):
        cfg_path = os.path.join(os.path.dirname(__file__), "config.jsonc")
    if os.path.exists(cfg_path):
        data = _read_jsonc(cfg_path)
        # Accept either top-level keys or nested MQTT section
        mqtt = data.get("MQTT", {})
        if not mqtt and any(k.startswith("MQTT_") for k in data.keys()):
            mqtt = {k: v for k, v in data.items() if k.startswith("MQTT_")}
        # Merge
        for k, v in mqtt.items():
            if k in cfg and v is not None:
                # cast types
                if k in ("MQTT_PORT", "MQTT_QOS"):
                    try:
                        cfg[k] = int(v)
                    except Exception:
                        pass
                elif k == "MQTT_TLS":
                    cfg[k] = bool(v) if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes")
                else:
                    cfg[k] = v
    return cfg


def _hostname_ip():
    host = socket.gethostname()
    ip = None
    try:
        # Attempt to get a sensible LAN IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            ip = socket.gethostbyname(host)
        except Exception:
            ip = "127.0.0.1"
    return host, ip


def on_connect(client_obj, userdata, flags, rc):
    now = datetime.datetime.now()
    if logFile:
        if rc == 0:
            logFile.write("[" + now.strftime("%Y-%m-%d %H:%M:%S") + "] Connected to MQTT broker\n")
        else:
            logFile.write("[" + now.strftime("%Y-%m-%d %H:%M:%S") + "] Failed to connect, rc=" + str(rc) + "\n")


def is_mqtt_connected():
    return bool(client and client.is_connected())


def mqtt_init():
    global client
    cfg = _load_mqtt_config()

    # Use callback API v1 for compatibility with (client, userdata, flags, rc) signature
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.v1)
    except Exception:
        client = mqtt.Client()
    # TLS if required
    if cfg.get("MQTT_TLS"):
        try:
            client.tls_set()
        except Exception:
            pass
    # Auth if provided
    if cfg.get("MQTT_USERNAME"):
        client.username_pw_set(cfg.get("MQTT_USERNAME"), cfg.get("MQTT_PASSWORD"))

    client.on_connect = on_connect

    try:
        client.connect(cfg.get("MQTT_BROKER"), int(cfg.get("MQTT_PORT", 1883)), 60)
    except Exception:
        now = datetime.datetime.now()
        if logFile:
            logFile.write("[" + now.strftime("%Y-%m-%d %H:%M:%S") + "] Not able to connect to MQTT broker\n")

    client.loop_start()


def mqtt_thread_func():
    mqtt_init()
    while True:
        time.sleep(CONNECTION_CHECK_INTERVAL)
        if not is_mqtt_connected():
            try:
                client.reconnect()
            except Exception:
                now = datetime.datetime.now()
                if logFile:
                    logFile.write("[" + now.strftime("%Y-%m-%d %H:%M:%S") + "] Unable to reconnect...\n")


def start_mqtt_thread():
    global mqtt_thread
    if mqtt_thread and mqtt_thread.is_alive():
        return
    mqtt_thread = threading.Thread(target=mqtt_thread_func, name="MQTT Thread", daemon=True)
    mqtt_thread.start()


def mqtt_main():
    global logFile
    logFile = open(LOG_FILE_NAME, "a")
    start_mqtt_thread()


def mqtt_close():
    if mqtt_thread:
        try:
            mqtt_thread.join(timeout=1)
        except Exception:
            pass
    if is_mqtt_connected():
        try:
            client.disconnect()
        except Exception:
            pass


def _construct_payload(parameters, reg_values, device_name, meta=None):
    """Build a JSON dict matching ingest expectations.

    parameters: list of parameter names (e.g., ['Time', 'Watts Total', ...])
    reg_values: list of values aligned to parameters
    device_name: human readable meter name
    meta: optional dict with keys like device_id, model, location
    """
    data = {}

    # Core list payload mapping parameter names -> values
    for i in range(min(len(parameters), len(reg_values))):
        data[parameters[i]] = reg_values[i]

    # Add ingest metadata
    host, ip = _hostname_ip()
    data["pi_name"] = host
    data["pi_ip"] = ip
    data["meter_name"] = device_name  # preferred by ingest

    # Duplicate a few keys in snake_case for ingest flexibility
    # Time
    if parameters and parameters[0].lower() == "time" and len(reg_values) > 0:
        data["time"] = reg_values[0]

    # Optional extra meta
    if isinstance(meta, dict):
        if meta.get("device_id") is not None:
            data["device_id"] = meta.get("device_id")
        if meta.get("model") is not None:
            data["model"] = meta.get("model")
        if meta.get("location") is not None:
            data["location"] = meta.get("location")

    return data


def publish_message(Parameters, regValue, deviceName, qos_level=0, meta=None):
    """Publish a meter reading.

    Parameters: list of parameter names
    regValue: list of values
    deviceName: meter name
    qos_level: MQTT QoS (0/1/2) if provided, else from config
    meta: optional dict {device_id, model, location}
    """
    global published_msg
    cfg = _load_mqtt_config()

    payload = _construct_payload(Parameters, regValue, deviceName, meta=meta)
    message = json.dumps(payload)

    if is_mqtt_connected():
        qos = qos_level if qos_level in (0, 1, 2) else int(cfg.get("MQTT_QOS", 0))
        try:
            client.publish(cfg.get("MQTT_TOPIC", "meter/readings"), message, qos=qos)
            published_msg += 1
        except Exception:
            # try to restart thread if needed
            if not (mqtt_thread and mqtt_thread.is_alive()):
                start_mqtt_thread()
    else:
        # ensure the thread is running to (re)connect
        if not (mqtt_thread and mqtt_thread.is_alive()):
            start_mqtt_thread()
    return published_msg