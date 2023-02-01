FROM python:3.9

ADD matrix_mqtt_bridge.py .

RUN pip3 install configparser paho-mqtt matrix-nio

CMD ["python3", "-u", "./matrix_mqtt_bridge.py"] 
