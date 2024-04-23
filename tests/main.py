import os
import time
import string
import random
import asyncio
import unittest
import threading
import paho.mqtt.client as mqtt
from nio import AsyncClient, MatrixRoom, RoomMessageText
from dotenv import load_dotenv

# loading variables from .env file
load_dotenv() 

# get matrix settings
matrix_homeserver = os.environ['MATRIX_HOMESERVER']
matrix_room_id = os.environ['MATRIX_ROOMID']
matrix_user = os.environ['MATRIX_CLIENT_USERNAME']
matrix_password = os.environ['MATRIX_CLIENT_PASSWORD']

# get mqtt settings
mqtt_host = os.environ['MQTT_HOST']
mqtt_user = os.environ['MQTT_USERNAME']
mqtt_password = os.environ['MQTT_PASSWORD']
mqtt_port = int(os.environ['MQTT_PORT'])
mqtt_tls = os.environ['MQTT_TLS'].lower() in ['true']
mqtt_topic_to_bridge = os.environ['MQTT_TOPIC_TO_BRIDGE']
mqtt_topic_from_bridge = os.environ['MQTT_TOPIC_FROM_BRIDGE'] 

class TestMQTTMatrixIntegration(unittest.TestCase):
    def setUp(self):
        # Set up the MQTT client
        self.mqtt_client_id = "Matrix-MQTT-Bridge-CI-CD"
        self.mqtt_client = mqtt.Client(self.mqtt_client_id)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.username_pw_set(mqtt_user, mqtt_password)
        if (mqtt_tls):
            self.mqtt_client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
        self.mqtt_client.connect(mqtt_host, mqtt_port)
        self.mqtt_client.loop_start()
        
        self.matrix_client = None        
        self.loop = asyncio.new_event_loop()

        self.test_message = ''.join(random.choices(string.ascii_uppercase + string.digits, k=100))

        # Variables to store received messages
        self.received_mqtt_messages = []
        self.received_matrix_messages = []

    def tearDown(self):
        self.mqtt_client.loop_stop()
        self.loop.close()

    # Callback function on MQTT connect
    def on_mqtt_connect(self, client, userdata, flags, rc):
        print("[MQTT]", "Connected with result code " + str(rc))
        self.mqtt_client.subscribe(mqtt_topic_from_bridge)

    # Callback function when a MQTT message is received
    def on_mqtt_message(self, client, userdata, message):
        print("[MQTT]", "Received message '" + str(message.payload.decode("utf-8")) + "' on topic '" + message.topic + "'")
        self.received_mqtt_messages.append(message.payload.decode("utf-8"))

    async def matrix_message_callback(self, room: MatrixRoom, event: RoomMessageText) -> None:
        if room.room_id == matrix_room_id and event.sender != matrix_user and (int(time.time() * 1000) - event.server_timestamp) <= 30 * 1000:
            print("[MTRX]", f"Message received in room {room.display_name}: {event.body}")
            self.received_matrix_messages.append(event.body)

    async def matrix_login(self, loop):
        print("[MTRX]", await self.matrix_client.login(matrix_password))
        # "Logged in as @alice:example.org device id: RANDOMDID"
        await self.matrix_client.join(matrix_room_id)
    
    async def send_matrix_message(self, loop):
        await self.matrix_client.room_send(
            room_id=matrix_room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": self.test_message},
        )
    
    async def matrix_sync(self, loop):
        try:
            await asyncio.wait_for(self.matrix_client.sync_forever(timeout=30000), timeout=10)
        except asyncio.TimeoutError:
            # Timeout error is expected, nothing to care about
            pass

    # 1) publish a mqtt message
    # 2) Matrix-MQTT-Bridge will recieve the MQTT message and publish a Matrix Message
    # 3) Recieve Matrix message(s) and check if it matches the original MQTT message payload 
    def test_publish_mqtt_and_recieve_matrix_message(self):
        # Publish a message
        client_id = "Matrix-MQTT-Bridge-CI-CD-PUBLISHER"
        client = mqtt.Client(client_id)
        #client.on_connect = self.on_connect
        client.username_pw_set(mqtt_user, mqtt_password)
        if (mqtt_tls):
            client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
        client.connect(mqtt_host, mqtt_port)
        
        client.publish(mqtt_topic_to_bridge, payload=self.test_message)

        # bridge transmits the mqtt message to matrix room
        self.matrix_client = AsyncClient(matrix_homeserver, matrix_user)
        self.matrix_client.add_event_callback(self.matrix_message_callback, RoomMessageText)

        self.loop.run_until_complete(self.matrix_login(self.loop))
        self.loop.run_until_complete(self.matrix_sync(self.loop))

        # Check if the Matrix message was recieved 
        self.assertTrue(self.test_message in self.received_matrix_messages)
       
    def test_publish_matrix_and_recieve_mqtt_message(self):
        self.matrix_client = AsyncClient(matrix_homeserver, matrix_user)

        self.loop.run_until_complete(self.matrix_login(self.loop))
        self.loop.run_until_complete(self.send_matrix_message(self.loop))
        self.loop.run_until_complete(self.matrix_sync(self.loop))
        
        # Check if the MQTT message was received
        self.assertTrue(self.test_message in self.received_mqtt_messages)

if __name__ == "__main__":
    unittest.main()

