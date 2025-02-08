# python
# because of smbus usage:
# pylint: disable=c-extension-no-member
#
# This file is part of the mqttDisplayClient distribution
# (https://github.com/olialb/mqttDisplayClient).
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
"""
Module implements a MQTT client for FullPageOS
"""

import configparser
import logging
import logging.handlers
import os
import signal
import sys
import time
import smbus
from paho.mqtt import client as mqtt_client
from ha_discover import HADiscovery

#
# initialize logger
#
LOG = logging.getLogger("MQTTClient")
logging.basicConfig()

#
# global constants
#
CONFIG_FILE = "mqttBH1750Client.ini"  # name of the ini file
MANUFACTURER = "githab olialb"
MODEL = "FullPageOS"
LOG_ROTATE_WHEN = "midnight"
LOG_BACKUP_COUNT = 5
LOG_FILE_PATH = "log"
LOG_FILE_NAME = None
LOG_FILE_HANDLER = None

# import from the configuration file only the feature configuraion
LOG_CFG = configparser.ConfigParser()

# try to open ini file
try:
    if os.path.exists(CONFIG_FILE) is False:
        LOG.critical("Config file not found '%s'!", CONFIG_FILE)
    else:
        LOG_CFG.read(CONFIG_FILE)
except OSError:
    LOG.error("Error while reading ini file: %s", CONFIG_FILE)
    sys.exit()

# read ini file values
try:
    # read logging config
    LOG_LEVEL = LOG_CFG["logging"]["level"]
    if LOG_LEVEL.upper() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        LOG.setLevel(LOG_LEVEL.upper())
    else:
        raise KeyError(LOG_LEVEL)

    if "path" in LOG_CFG["logging"]:
        LOG_FILE_PATH = LOG_CFG["logging"]["path"]
    if "file" in LOG_CFG["logging"]:
        LOG_FILE_NAME = LOG_CFG["logging"]["file"]
    try:
        os.makedirs(LOG_FILE_PATH)
        LOG.debug("Logging directory created: ./%s", LOG_FILE_PATH)
    except FileExistsError:
        LOG.info("Logging directory exist already: ./%s", LOG_FILE_PATH)
    except OSError:
        LOG.error("Can not create Logging directory: ./%s", LOG_FILE_PATH)

    if LOG_FILE_NAME is not None and LOG_FILE_NAME != "":
        # create time rotating logger for log files
        LOG_FILE_HANDLER = logging.handlers.TimedRotatingFileHandler(
            os.path.join(LOG_FILE_PATH, LOG_FILE_NAME),
            when=LOG_ROTATE_WHEN,
            backupCount=LOG_BACKUP_COUNT,
        )
        # Set the formatter for the logging handler
        LOG_FILE_HANDLER.setFormatter(
            logging.Formatter("%(asctime)s-%(name)s-%(levelname)s-%(message)s")
        )
        LOG.addHandler(LOG_FILE_HANDLER)

except KeyError as error:
    LOG.error("Error while reading ini file: %s", error)
    sys.exit()


#
# global settings
#
class MqttBH1750Client: #pylint: disable=too-many-instance-attributes
    """Implements an mqtt client to publish lux state of a connected bhl1750 sensor"""
    def __init__(self, config_file):
        """
        Constructor takes config file as parameter (ini file) and defines global atrributes
        """
        # Global config:
        self.config_file = config_file

        # other global attributes
        self.reconnect_delay = 5  # retry in seconds to try to reconnect mgtt broker
        self.publish_delay = 3  # delay between two publish loops in seconds
        self.full_publish_cycle = 20  # Every publishcycle*fullPublishCycle
        self.topic_root = None  # Root path for all topics
        self.unpublished = True  # set to true if the topics are not published yet
        self.client = None  # mqtt client
        self.lux = None  # last published lux value

        # broker config:
        self.broker = None
        self.port = 1883
        self.username = ""
        self.password = ""

        # topic configuration
        self.topic_config = {"bh1750": {"topic": "lux", "publish": self.publish_lux}}
        self.read_config_file()

    def read_config_file(self):
        """
        Reads the configured ini file and sets attributes based on the config
        """
        # read ini file
        config = configparser.ConfigParser()
        # try to open ini file
        try:
            if os.path.exists(self.config_file) is False:
                LOG.critical("Config file not found '%s'!", self.config_file)
            else:
                config.read(self.config_file)
        except OSError:
            LOG.error("Error while reading ini file: %s", self.config_file)
            sys.exit()

        # read ini file values
        try:
            # read server config
            self.broker = config["global"]["broker"]
            self.port = int(config["global"]["port"])
            self.username = config["global"]["username"]
            self.password = config["global"]["password"]
            self.topic_root = (
                config["global"]["topicRoot"] + "/" + config["global"]["deviceName"]
            )
            self.reconnect_delay = int(config["global"]["reconnectDelay"])
            self.publish_delay = int(config["global"]["publishDelay"])
            self.full_publish_cycle = int(config["global"]["fullPublishCycle"])

            # read bh1750 config
            self.topic_config["bh1750"]["mode"] = int(config["bh1750"]["mode"], 0)
            self.topic_config["bh1750"]["addr"] = int(config["bh1750"]["i2cAddr"], 0)

            # read config HADiscovery
            self.ha_dc = False
            if "haDiscover" in config["feature"]:
                if config["feature"]["haDiscover"].upper() == "ENABLED":
                    self.ha_dc = True
            self.ha_device_name = config["haDiscover"]["deviceName"]
            self.ha_base = config["haDiscover"]["base"]

        except KeyError as inst:
            LOG.error("Error while reading ini file: %s", inst)
            sys.exit()

    @classmethod
    def on_connect(cls, client, inst, flags, rc, properties): #pylint: disable=too-many-arguments,too-many-positional-arguments,unused-argument
        """Method called on connect to broker"""
        if rc == 0:
            LOG.info("Connected to MQTT Broker!")
            # make the subscritions at the broker
            inst.subscribe()
        else:
            LOG.warning("Failed to connect, return code %s", rc)

    @classmethod
    def on_disconnect(cls, client, inst, flags, rc, properties): #pylint: disable=too-many-arguments,too-many-positional-arguments,unused-argument
        """Method called on disconnect from broker"""
        LOG.info("Disconnected with result code: %s", rc)
        inst.unpublished = True
        inst.brightness = -1
        while True:
            LOG.info("Reconnecting in %s seconds...", inst.reconnect_delay)
            time.sleep(inst.reconnect_delay)

            try:
                client.reconnect()
                LOG.info("Reconnected successfully!")
                return
            except OSError as err:
                LOG.warning("%s. Reconnect failed. Retrying...", err)

    @classmethod
    def on_message(cls, client, inst, msg):  # pylint: disable=unused-argument
        """
        method is called when the cleint receives a message from the broker
        """
        LOG.info(
            "Received `%s` from `%s` topic", msg.payload.decode().strip(), msg.topic
        )

        # check received topic syntax
        if msg.topic[0 : len(inst.topic_root)] == inst.topic_root:
            topic = msg.topic[len(inst.topic_root) : len(msg.topic)]
            topic = topic.split("/")
            if topic[2] != "set":
                LOG.info("Wrong topic syntax received from broker %s", msg.topic)
                return
            # search for topic:
            topic_key = None
            for key, t in inst.topic_config.items():
                if t["topic"] == topic[1]:
                    topic_key = key
                    break

            if topic_key is not None:
                # call the configured command
                if "set" in inst.topic_config[topic_key]:
                    inst.topic_config[topic_key]["set"](
                        inst.topic_config[topic_key], msg.payload.decode()
                    )
                else:
                    LOG.info(
                        "Command for topic without command received from broker %s",
                        msg.topic,
                    )
            else:
                LOG.info("Command for unknown topic received from broker %s", msg.topic)
        else:
            LOG.info("Wrong topic syntax received from broker %s", msg.topic)

    def connect(self) -> mqtt_client:
        """
        Method to connect to the mqtt broker
        """
        self.client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        if self.username != "":
            self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = MqttBH1750Client.on_connect
        self.client.on_disconnect = MqttBH1750Client.on_disconnect
        while True:
            try:
                self.client.connect(self.broker, self.port)
            except OSError as error:
                LOG.warning(
                    "Error while connect to server %s:%s: %s",
                    self.broker,
                    self.port,
                    error,
                )
                time.sleep(self.reconnect_delay)
                continue
            break
        # set user data for call backs
        self.client.user_data_set(self)

        # start main loop of mqtt client
        self.client.loop_start()

    def subscribe(self):
        """
        method to subscribe to all the configured topics at the broker
        """
        # Subscribe to all configured topics
        for topic_config in self.topic_config.values():
            if "topic" in topic_config:
                topic = self.topic_root + f"/{topic_config['topic']}/set"
                self.client.subscribe(topic)
                LOG.debug("Subscribe to: %s", topic)
        self.client.on_message = MqttBH1750Client.on_message

    def publish_lux(self, topic, my_config):
        """
        publich lux status
        """
        bus = smbus.SMBus(1)
        data = bus.read_i2c_block_data(my_config["addr"], my_config["mode"])
        lux = (data[1] + (256 * data[0])) / 1.2
        if self.unpublished is True or self.lux != lux:
            result = self.client.publish(topic, f"{lux:.4}")
            # result: [0, 1]
            status = result[0]
            if status == 0:
                LOG.debug("Send %s to topic %s", lux, topic)
                self.lux = lux
            else:
                LOG.error("Failed to send message to topic %s", topic)

    def ha_publish(self, topic, payload):
        """Publish ha discovery topics"""
        if self.ha_dc is True:
            # publish new entity
            result = self.client.publish(topic, payload, retain=True)
        else:
            # delete entity
            result = self.client.publish(topic, "", retain=True)
        status = result[0]
        if status == 0:
            LOG.debug("Send '%s' to topic %s", payload, topic)
        else:
            LOG.error("Failed to send message to topic %s", topic)

    def ha_discover(self):
        """
        piblish all ropics needed for the home assistant mqtt discovery
        """
        # pubish all topics that home assisstant can discover them
        ha = HADiscovery(self.ha_device_name, self.ha_base, MANUFACTURER, MODEL)

        # cpu temperature
        topic, payload = ha.sensor(
            "Light sensor",
            self.topic_root + "/lux",
            device_class="illuminance",
            unit="lx",
        )
        self.ha_publish(topic, payload)

    def publish_loop(self):
        """
        endless main publish loop
        """
        # endless publish loop
        self.unpublished = True
        loop_counter = 0
        try:
            while True:
                for topic_config in self.topic_config.values():
                    if "publish" in topic_config:
                        topic = f"{self.topic_root}/{topic_config['topic']}"
                        topic_config["publish"](topic, topic_config)
                # mark the topics as published
                self.unpublished = False
                # delay until next loo starts
                time.sleep(self.publish_delay)
                # call time time tick of chrome pages
                loop_counter += 1
                if loop_counter > self.full_publish_cycle:
                    loop_counter = 0
                    self.unpublished = True
        except KeyboardInterrupt:
            LOG.warning("Keyboard interrupt receiced. Stop client...")


def signal_term_handler(sig, frame):  # pylint: disable=unused-argument
    """
    Call back to handle OS SIGTERM signal to terminate client.
    """
    LOG.warning("Received SIGTERM. Stop client...")
    sys.exit(0)


signal.signal(signal.SIGTERM, signal_term_handler)


def mqtt_bh1750_client():
    """main function"""
    client = MqttBH1750Client(CONFIG_FILE)
    client.connect()
    client.ha_discover()
    client.publish_loop()


if __name__ == "__main__":
    mqtt_bh1750_client()
