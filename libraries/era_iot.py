import json
from mqtt_as import MQTTClient, config, match_mqtt_topic

ERA_BASE_TOPIC                                      = 'eoh/chip/%s'
ERA_PREFIX_LWT_TOPIC                                = '/is_online'
ERA_ONLINE_MESSAGE                                  = '{"ol":1, "wifi_ssid":"%s", "ask_configuration":1}'
ERA_OFFLINE_MESSAGE                                 = '{"ol":0}'
ERA_PUBLISH_MESSAGE                                 = '{"v": %d}'

# Subscribe topic
ERA_SUB_PREFIX_DOWN_TOPIC                           = '/down'
ERA_SUB_PREFIX_VIRTUAL_TOPIC                        = '/virtual_pin/+'

# Publish topic
ERA_PUB_PREFIX_INFO_TOPIC                           = '/info'
ERA_PUB_PREFIX_MODBUS_DATA_TOPIC                    = '/data'
ERA_PUB_PREFIX_CONFIG_DATA_TOPIC                    = '/config/%d/value'
ERA_PUB_PREFIX_MULTI_CONFIG_DATA_TOPIC              = '/config_value'

ERA_MQTT_SERVER                                     = 'mqtt1.eoh.io'
ERA_MQTT_PORT                                       = 1883

class EraIoT:
    def __init__(self, ssid, password, token):
        self._virtual_pins = {}
        self._token = token
        self._config = config.copy()
        self._config['ssid'] = ssid
        self._config['wifi_pw'] = password
        self._config['server'] = ERA_MQTT_SERVER
        self._config['port'] = ERA_MQTT_PORT
        
        self._config['user'] = self._token
        self._config['password'] = self._token
        self._config["will"] = [self._get_topic(ERA_PREFIX_LWT_TOPIC), ERA_OFFLINE_MESSAGE, True, 1]
        
        self._config['topics'] = []
        self._config["topics"].append((self._get_topic(ERA_SUB_PREFIX_DOWN_TOPIC), self._on_config_down_message))
        self._config["topics"].append((self._get_topic(ERA_SUB_PREFIX_VIRTUAL_TOPIC), self._on_virtual_pin_message))
        

        MQTTClient.DEBUG = True  # Optional: print diagnostic messages
    
    async def connect(self):
        self._client = MQTTClient(self._config)
        await self._client.connect()
        # get config
        await self._client.publish(self._get_topic(ERA_PREFIX_LWT_TOPIC), ERA_ONLINE_MESSAGE % self._config['ssid'], retain=True, qos=1)
    
    def _get_topic(self, topic):
        return ERA_BASE_TOPIC % self._token + topic

    async def _on_config_down_message(self, topic, payload):
        payload = json.loads(payload)
        devices = payload['configuration']['arduino_pin']['devices']
        #print(devices)
        # save config id from server
        if len(devices):
            for d in devices:
                v_pins = d['virtual_pins']
                if len(v_pins):
                    for v in v_pins:
                        self._virtual_pins[int(v['pin_number'])] = v['config_id']
        #print(self._virtual_pins)
    
    async def _on_virtual_pin_message(self, topic, payload):
        payload = json.loads(payload)
        value = int(payload['value'])
        # split topic to get virtual pin
        pin = match_mqtt_topic(topic, self._get_topic(ERA_SUB_PREFIX_VIRTUAL_TOPIC))

        if pin != None and len(pin) == 1:
            pin = int(pin[0])
        else:
            return
        #print('Receive virtual pin command: V', pin, '=', value)

        if self._virtual_pins[str(pin) + '_cb']:
            await self._virtual_pins[str(pin) + '_cb'](topic, value)
    
    async def virtual_write(self, pin, value, qos=1):
        config_id = self._virtual_pins.get(int(pin))
        if config_id == None:
           return
        topic = self._get_topic(ERA_PUB_PREFIX_CONFIG_DATA_TOPIC % config_id)
        await self._client.publish(topic, ERA_PUBLISH_MESSAGE % value, retain=True, qos=qos)
    
    def on_virtual_read(self, pin, callback):
        self._virtual_pins[str(pin) + '_cb'] = callback

    
# Example usage
'''
era = EraIoT('wifi', 'pass', 'xxxxxxx-yyyy-41f0-b078-9f5beb306aae')

from pins import *
led_d13 = Pins(D13_PIN)

async def on_v0_message(topic, value):
    #print('Topic received: ', topic, ' = ', value)
    await era.virtual_write(0, value)
    if value == 1:
       neopix.show(0, (0, 255, 0))
    else:
       neopix.show(0, (0, 0, 0))

async def on_v2_message(topic, value):
    #print('Topic received: ', topic, ' = ', value)
    await era.virtual_write(2, value)
    if value == 1:
       led_d13.write_digital(1)
    else:
       led_d13.write_digital(0)

async def task_dht():
  n = 1
  while True:
    print('Sending: ', n)
    await era.virtual_write(3, n)
    await era.virtual_write(4, n*2)
    n = n + 1
    await asyncio.sleep_ms(5000)

### setup ###
async def setup():
  print('App started')
  neopix.show(0, (255, 0, 0))
  await era.connect()
  neopix.show(0, (0, 255, 0))
  era.on_virtual_read(0, on_v0_message)
  era.on_virtual_read(2, on_v2_message)
  asyncio.create_task(task_dht())

### loop ###
async def main():
  await setup()
  while True:
    await asyncio.sleep_ms(100)

run_loop(main())

'''