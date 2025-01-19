#python
# 
 # This file is part of the mqttBH1750Client distribution (https://github.com/olialb/mqttBH1750Client).
 # Copyright (c) 2025 Oliver Albold.
 # 
 # This program is free software: you can redistribute it and/or modify  
 # it under the terms of the GNU General Public License as published by  
 # the Free Software Foundation, version 3.
 #
 # This program is distributed in the hope that it will be useful, but 
 # WITHOUT ANY WARRANTY; without even the implied warranty of 
 # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
 # General Public License for more details.
 #
 # You should have received a copy of the GNU General Public License 
 # along with this program. If not, see <http://www.gnu.org/licenses/>.
 #
 
import configparser
import logging
import os
import time
import smbus
from paho.mqtt import client as mqtt_client

#
#initialize logger
#
log = logging.getLogger('MQTTClient')
logging.basicConfig()

#
#global constants
#
SWVERSION='V0.1'
CONFIG_FILE = 'mqttBH1750Client.ini' #name of the ini file
    
#
#global settings
#
class MqttBH1750Client:    
    def __init__(self, configFile):
        #Global config:
        self.configFile = configFile        
        
        #other global attributes
        self.reconnect_delay=5 #retry in seconds to try to reconnect mgtt broker
        self.publish_delay=3 #delay between two publish loops in seconds
        self.full_publish_cycle=20 #Every publishcycle*fullPublishCycle will be all topics published even if no data changed:
        self.topicRoot = None#Root path for all topics
        self.unpublished=True #set to true if the topics are not published yet
        self.client =None #mqtt client
        self.lux = None #last published lux value
        
        #broker config:
        self.broker=None
        self.port=1883
        self.username=""
        self.password=""
        
        #topic configuration
        self.tConfig = { 
            'bh1750' : {'topic':'lux', 'publish' : self.publish_lux },
            'status' : {'topic':'status', 'publish' : self.publish_status }
            }
        self.read_config_file()
        
    def read_config_file(self):
        #read ini file
        config = configparser.ConfigParser()
        #try to open ini file
        try:
            if os.path.exists(self.configFile) == False:
                log.critical(f"Config file not found '{self.configFile}'!")
            else:
                config.read(self.configFile)
        except:
            log.error(f"Error while reading ini file: {self.configFile}")
            exit()
        
        #read ini file values
        try:
            #read server config
            self.broker = config['global']['broker']
            self.port = int(config['global']['port']) 
            self.username = config['global']['username']
            self.password = config['global']['password']
            self.topicRoot = config['global']['topicRoot']+'/'+config['global']['deviceName']
            self.reconnect_delay = int(config['global']['reconnectDelay'])
            self.publish_delay = int(config['global']['publishDelay'])
            self.full_publish_cycle = int(config['global']['fullPublishCycle'])
            
            #read bh1750 config
            self.tConfig['bh1750']['mode'] = int(config['bh1750']['mode'],0)
            self.tConfig['bh1750']['addr'] = int(config['bh1750']['i2cAddr'],0)
                               
        except Exception as inst:
            log.error(f"Error while reading ini file: {inst}")
            exit()        
 
    @classmethod
    def on_connect(cls, client, inst, flags, rc, properties):
        if rc == 0:
            log.info("Connected to MQTT Broker!")
            #make the subscritions at the broker
            inst.subscribe()
        else:
            log.warning(f"Failed to connect, return code {rc}")

    @classmethod
    def on_disconnect(cls, client, inst, flags, rc, properties):
        log.info(f"Disconnected with result code: {rc}")
        inst.unpublished=True
        inst.brightness=-1
        while True:
            log.info(f"Reconnecting in {inst.reconnect_delay} seconds...")
            time.sleep(inst.reconnect_delay)

            try:
                client.reconnect()
                log.info("Reconnected successfully!")
                return
            except Exception as err:
                log.warning(f"{err}. Reconnect failed. Retrying...")

    @classmethod
    def on_message(cls, client, inst, msg):
        log.info(f"Received `{msg.payload.decode().strip()}` from `{msg.topic}` topic")
        
        #check received topic syntax
        if msg.topic[0:len(inst.topicRoot)] == inst.topicRoot:
            topic = msg.topic[len(inst.topicRoot):len(msg.topic)]
            topic = topic.split('/')
            if topic[2] != 'set':
                log.info(f"Wrong topic syntax received from broker {msg.topic}")
                return
            #search for topic:
            topicKey = None
            for key,t in inst.tConfig.items():
                if t['topic'] == topic[1]:
                    topicKey = key
                    break
                    
            if topicKey != None:
                #call the configured command
                if 'set' in inst.tConfig[topicKey]:
                    inst.tConfig[topicKey]['set'](inst.tConfig[topicKey],msg.payload.decode())
                else:
                    log.info(f"Command for topic without command received from broker {msg.topic}")                    
            else:
                log.info(f"Command for unknown topic received from broker {msg.topic}")
        else:
            log.info(f"Wrong topic syntax received from broker {msg.topic}")                    

    def connect(self) -> mqtt_client:    
        self.client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        if self.username != "":
            self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = MqttBH1750Client.on_connect
        self.client.on_disconnect = MqttBH1750Client.on_disconnect
        while True:
            try:
                self.client.connect(self.broker, self.port)
            except Exception as inst:
                log.warning(f"Error while connect to server {broker}:{port}: {inst}")
                time.sleep(self.reconnect_delay)
                continue
            break
        #set user data for call backs
        self.client.user_data_set( self )
    
        #start main loop of mqtt client
        self.client.loop_start()
        
    def subscribe(self):
        #Subscribe to all configured topics
        for key in self.tConfig:
            if 'topic' in self.tConfig[key]:
                topic = self.topicRoot + f"/{self.tConfig[key]['topic']}/set"
                self.client.subscribe(topic)
                log.debug(f"Subscribe to: {topic}")
        self.client.on_message = MqttBH1750Client.on_message


    def publish_status(self, topic, myConfig):
        #publich online status
        #send message to broker
        if self.unpublished == True:
            result = self.client.publish(topic, "online")
            # result: [0, 1]
            status = result[0]
            if status == 0:
                log.debug(f"Send 'online' to topic {topic}")
            else:
                log.error(f"Failed to send message to topic {topic}")

    def publish_lux(self, topic, myConfig):
        #publich online status
        #send message to broker
        #read i2c data from sensor
        bus = smbus.SMBus(1)
        data = bus.read_i2c_block_data(myConfig['addr'], myConfig['mode'])
        lux = (data[1] + (256 * data[0])) / 1.2
        if self.unpublished == True or self.lux != lux:
            result = self.client.publish(topic, f"{lux:.4}")
            # result: [0, 1]
            status = result[0]
            if status == 0:
                log.debug(f"Send {lux} to topic {topic}")
                self.lux = lux
            else:
                log.error(f"Failed to send message to topic {topic}")

    def publish_loop(self):
        #endless publish loop
        self.unpublished=True
        loopCounter=0
        while True:
            for key in self.tConfig:
                if 'publish' in self.tConfig[key]:
                    topic = f"{self.topicRoot}/{self.tConfig[key]['topic']}"
                    self.tConfig[key]['publish'](topic, self.tConfig[key])
            #mark the topics as published
            self.unpublished=False
            #delay until next loo starts
            time.sleep(self.publish_delay)
            loopCounter += 1
            if loopCounter > self.full_publish_cycle:
                loopCounter = 0
                self.unpublished=True
            
        
def mqtt_BH1750_client():
    mqttBH1750Client = MqttBH1750Client( CONFIG_FILE )
    mqttBH1750Client.connect()
    mqttBH1750Client.publish_loop()

if __name__ == '__main__':
    mqtt_BH1750_client()
