import time
import threading
import asyncio
import configparser 
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
matrix_homeserver = config.get("MATRIX", "homeserver")
matrix_user = config.get("MATRIX", "user")
matrix_password = config.get("MATRIX", "password")
matrix_room_id = config.get("MATRIX", "room_id")

# get mqtt settings
mqtt_host = config.get("MQTT", "host")
mqtt_user = config.get("MQTT", "user")
mqtt_password = config.get("MQTT", "password")
mqtt_port = config.get("MQTT", "port")
mqtt_topic_sub = config.get("MQTT", "topic_sub")
mqtt_topic_pub = config.get("MQTT", "topic_pub")

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


# when a MQTT message is recieved
def on_message(client, userdata, msg):
    message = msg.payload.decode("utf-8") 
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

# using MQTT version 5 here, for 3.1.1: MQTTv311, 3.1: MQTTv31
# userdata is user defined data of any type, updated by user_data_set()
# client_id is the given name of the client
mqtt_client = paho.Client(client_id="Matrix-MQTT-Bridge", userdata=None, protocol=paho.MQTTv5)
mqtt_client.on_connect = on_connect

# enable TLS for secure MQTT connection
mqtt_client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)

mqtt_client.username_pw_set(mqtt_user, mqtt_password)
mqtt_client.connect(mqtt_host, int(mqtt_port))

# setting callbacks, use separate functions like above for better visibility
mqtt_client.on_subscribe = on_subscribe
mqtt_client.on_message = on_message
mqtt_client.on_publish = on_publish

mqtt_client.loop_start()

matrix_client = None
event_loop = asyncio.new_event_loop()
event_loop.run_until_complete(main())
