# Matrix-MQTT-Bridge

This project was created to create bridge between the Matrix Messenger and the MQTT protocol. I'm using this to control a microcontroller / Raspberry Pi Pico over a Matrix chat. Using this project the microcontroller is able to recieve the messages posted into the Matrix chat (like in the graphic). MQTT Messages which get published by the microcontroller get also forwarded into the Matrix chat by the Matrix-MQTT-Bridge.

![Matrix-MQTT-Bridge](docs/phone_to_pico.png?raw=true)

-----

## Setup
Matrix-MQTT-Bridge can be run both via Docker or manually on the host as a systemd service

### Via Docker
You can run the Matrix-MQTT-Bridge via Docker, e.g. by using this `docker-compose.yaml` file. You will have to create a `config.ini` file to configure the connection to the MQTT broker and to the Matrix server. I'm using this project in combination with a **free private** [HiveMQ cloud instance](https://console.hivemq.cloud/), which acts as my MQTT broker.

```yaml
version: "3.9"

services:
  matrix-mqtt-bridge:
    image: ghcr.io/rubenhoenle/matrix-mqtt-bridge:latest
    container_name: matrix-mqtt-bridge
    restart: always
    volumes:
      - ./config.ini:/config.ini
```

### Via Systemd
This repository includes an [example systemd unit file](matrix-mqtt-bridge.service) that allows to run the Matrix-MQTT-Bridge as a systemd service directly on the host. To use the systemd unit file, follow these steps:

1. Clone the repository to `/opt/Matrix-MQTT-Bridge/`
2. Install the `nio` and `paho` Python packages, e.g. using `pip` or your system package manager
3. Copy the [`config.ini.example`](config.ini.example) to `config.ini` and fill in your configuration
4. Copy the [`matrix-mqtt-bridge.service`](matrix-mqtt-bridge.service) to `/etc/systemd/system/`
5. Create an unprivileged user `mqtt-bridge` (or edit the username in the [`matrix-mqtt-bridge.service`](matrix-mqtt-bridge.service))
6. Optionally use `chown -R mqtt-bridge:mqtt-bridge /opt/Matrix-MQTT-Bridge` and `chmod 600 /opt/Matrix-MQTT-Bridge/config.ini` to protect your configuration from reading by other users
7. Run `systemd daemon-reload` as root to add the new unit file to its index
8. Run `systemctl enable --now matrix-mqtt-bridge` as root to start the bridge now and on each reboot
9. Use `systemctl status matrix-mqtt-bridge` or `journalctl -eu matrix-mqtt-bridge` to view the log output of the bridge

-----

## Config file
The `config.ini` is split into two parts: The Matrix configuration and the configuration for the MQTT connection.

### Matrix configuration
You will need two Matrix accounts: The one you are using on e.g. your phone (I'm using my regular, personal Matrix Account for this) and this Matrix-MQTT-Bridge will require it's own account. After you have created a seperate Matrix account for the Matrix-MQTT-Bridge, create a new chatroom and with one of your accounts and add the other account to this room. Now, check if your able to write / recieve messages in this chatroom using your two different accounts.

**Important: Matrix room has to be unencrypted. Do not enable encryption when creating the Matrix chatroom!**

### MQTT configuration
Is actually self-explanatory. Enter your Host (for me it's my HiveMQ cloud instance), the port and the credentials to connect to the MQTT message broker (username / password).     
- The `topic_sub` is the MQTT topic the Matrix-MQTT-Bridge will **subscribe** to. All MQTT messages recieved on this topic will be sent into the Matrix chatroom by the bridge.
- When the Matrix-MQTT-Bridge recieves a message via Matrix, it will publish this message to the MQTT broker using the topic specified in `topic_pub`.
- Enable `allow_escaped_unicode` to allow support for escaped unicode characters like `\u00fc` for german umlaut ü in the MQTT messages
- Enable `filter_duplicates` to filter subsequent duplicate messages in MQTT (only the first will be forwarded to Matrix)

```ini
[MATRIX]
homeserver = https://matrix.org
user = @YOUR_USERNAME:matrix.org
password = YOUR_PASSWORD_USED_TO_LOGIN_INTO_MATRIX
room_id = !YOUR_ROOM_ID:matrix.org

[MQTT]
host = YOUR_HOST.hivemq.cloud
user = YOUR_MQTT_USER
password = YOUR_MQTT_PASSWORD
port = 8883
tls = true
topic_sub = mqttbridge/sub
topic_pub = mqttbridge/pub
allow_escaped_unicode = false
filter_duplicates = false
```
