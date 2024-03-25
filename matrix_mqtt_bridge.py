import time
import threading
import asyncio
import configparser 
import re
import nio
import paho.mqtt.client as paho
from paho import mqtt
from nio import AsyncClient, MatrixRoom, RoomMessageText

# pip3 install configparser
# pip3 install paho-mqtt
# pip3 install matrix-nio
# https://github.com/poljar/matrix-nio

config = configparser.ConfigParser(interpolation=None)
config.read("config.ini")

# get matrix settings
matrix_homeserver = config["MATRIX"].get("homeserver")
matrix_user = config["MATRIX"].get("user")
matrix_password = config["MATRIX"].get("password")
matrix_room_id = config["MATRIX"].get("room_id")

# get mqtt settings
mqtt_host = config["MQTT"].get("host")
mqtt_user = config["MQTT"].get("user")
mqtt_password = config["MQTT"].get("password")
mqtt_port = config["MQTT"].get("port")
mqtt_tls = config.getboolean("MQTT", "tls")
mqtt_topic_sub = config["MQTT"].get("topic_sub")
mqtt_topic_pub = config["MQTT"].get("topic_pub")
mqtt_allow_escaped_unicode = config["MQTT"].get("allow_escaped_unicode", False)
mqtt_filter_duplicates = config["MQTT"].get("filter_duplicates", False)

last_message = ""

async def message_callback(room: MatrixRoom, event: RoomMessageText) -> None:
    if room.room_id == matrix_room_id and event.sender != matrix_user and (int(time.time() * 1000) - event.server_timestamp) <= 30 * 1000:
        print("[MTRX]", f"Message received in room {room.display_name} from {event.sender}: {event.body}")
        mqtt_client.publish(mqtt_topic_pub, payload=event.body, qos=1)


async def main() -> None:
    global matrix_client
    matrix_client = AsyncClient(matrix_homeserver, matrix_user)
    matrix_client.add_event_callback(message_callback, RoomMessageText)

    print("[MTRX]", await matrix_client.login(matrix_password))
    # "Logged in as @alice:example.org device id: RANDOMDID"

    await matrix_client.join(matrix_room_id)

    await matrix_client.room_send(
        room_id=matrix_room_id,
        message_type="m.room.message",
        content={"msgtype": "m.text", "body": "[Matrix-MQTT-Bridge]: Ready"},
    )
    
    # using MQTT version 5 here, for 3.1.1: MQTTv311, 3.1: MQTTv31
    # userdata is user defined data of any type, updated by user_data_set()
    # client_id is the given name of the client
    global mqtt_client
    mqtt_client = paho.Client(callback_api_version=paho.CallbackAPIVersion.VERSION1, client_id="Matrix-MQTT-Bridge", userdata=None, protocol=paho.MQTTv31)
    mqtt_client.on_connect = on_connect
    
    # enable TLS for secure MQTT connection
    if (mqtt_tls):
        mqtt_client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
    
    mqtt_client.username_pw_set(mqtt_user, mqtt_password)
    mqtt_client.connect(mqtt_host, int(mqtt_port))
    
    # setting callbacks, use separate functions like above for better visibility
    mqtt_client.on_subscribe = on_subscribe
    mqtt_client.on_message = on_message
    mqtt_client.on_publish = on_publish
    
    mqtt_client.loop_start()

    await matrix_client.sync_forever(timeout=30000)  # milliseconds


# setting callbacks for different events to see if it works, print the message etc.
def on_connect(client, userdata, flags, rc, properties=None):
    print("[MQTT]", "CONNACK received with code %s." % rc)
    # subscribe to MQTT topic
    mqtt_client.subscribe(mqtt_topic_sub, qos=1)


# with this callback you can see if your MQTT publish was successful
def on_publish(client, userdata, mid, properties=None):
    print("[MQTT]", "mid: " + str(mid))


# Prints a reassurance for successfully MQTT subscribing
def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    print("[MQTT]", "Subscribed: " + str(mid) + " " + str(granted_qos))

def unescapematch(match):
    escapesequence = match.group(0)
    digits = escapesequence[2:]
    ordinal = int(digits, 16)
    char = chr(ordinal)
    return char

# when a MQTT message is recieved
def on_message(client, userdata, msg):
    global last_message
    message = msg.payload.decode("utf-8") 
    if mqtt_allow_escaped_unicode:
        message = re.sub(r'(\\u[0-9A-Fa-f]{2,4})', unescapematch, message)
    
    for section in config.sections():
        if section.startswith("MQTT.replace."):
            replace_definition = config[section]
            pattern = replace_definition.get("pattern", None)
            substitution = replace_definition.get("substitution", None)
            if pattern != None and substitution != None:
                message = re.sub(pattern, substitution, message)
    
    if not mqtt_filter_duplicates or message != last_message:
        last_message = message
        print("[MQTT]", msg.topic + " " + str(msg.qos) + " " + str(message))
        
        global matrix_client, event_loop
        try:
            send_fut = asyncio.run_coroutine_threadsafe(
                matrix_client.room_send(
                    room_id=matrix_room_id,
                    message_type="m.room.message",
                    content={"msgtype": "m.text", "body": message},
                ),
                event_loop,
            )
            send_fut.result()
        except nio.exceptions.LocalProtocolError:
            print("[MTRX]", f"Could not send message to {room_id}, ignoring.")
    else:
        print(f"[MQTT] duplicate: {msg.topic} {msg.qos} {message}")

event_loop = asyncio.new_event_loop()
event_loop.run_until_complete(main())
