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

import signal
import sys
import smbus
from base_mqtt_client import base_mqtt_client as BMC

#
# global constants
#
CONFIG_FILE = "mqttBH1750Client.ini"  # name of the ini file

#
# main class
#
class MqttBH1750Client(BMC.BaseMqttClient): #pylint: disable=too-many-instance-attributes
    """Implements an mqtt client to publish lux state of a connected bhl1750 sensor"""
    def __init__(self, config_file):
        """
        Constructor takes config file as parameter (ini file) and defines global atrributes
        """
        # Global config:
        BMC.BaseMqttClient.__init__(self, config_file)

        #additional class attributes
        self.lux = None  # last published lux value

    def read_client_config(self, config):
        """
        Reads the configured ini file and sets attributes based on the config
        """
        # topic configuration
        self.topic_config = {"bh1750": {"topic": "lux", "publish": self.publish_lux}}

        try:
            # read bh1750 config
            self.topic_config["bh1750"]["mode"] = int(config["bh1750"]["mode"], 0)
            self.topic_config["bh1750"]["addr"] = int(config["bh1750"]["i2cAddr"], 0)

        except KeyError as inst:
            self.log.error("Error while reading ini file: %s", inst)
            sys.exit()

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
                self.log.debug("Send %s to topic %s", lux, topic)
                self.lux = lux
            else:
                self.log.error("Failed to send message to topic %s", topic)

    def ha_discover(self):
        """
        piblish all ropics needed for the home assistant mqtt discovery
        """
        # cpu temperature
        topic, payload = self.ha.sensor(
            "Light sensor",
            self.topic_root + "/lux",
            device_class="illuminance",
            unit="lx",
        )
        self.ha_publish(topic, payload)


def mqtt_bh1750_client():
    """main function"""
    def signal_term_handler(sig, frame):  # pylint: disable=unused-argument
        """
        Call back to handle OS SIGTERM signal to terminate client.
        """
        client.log.warning("Received SIGTERM. Stop client...")
        sys.exit(0)

    client = MqttBH1750Client(CONFIG_FILE)
    signal.signal(signal.SIGTERM, signal_term_handler)
    client.connect()
    client.ha_discover()
    client.publish_loop()


if __name__ == "__main__":
    mqtt_bh1750_client()
