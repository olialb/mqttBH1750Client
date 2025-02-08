# BH1750 MQTT client for raspberry pi

## Purpose of this project
[BH1750](https://www.mouser.com/datasheet/2/348/bh1750fvi-e-186247.pdf?srsltid=AfmBOoqC7uAiZBA6RoouOt9ByvvPM5Sy5M-yFMTtI5dfTa2-e7MJFZq5) is a Light Sensor. The light sensor can be connected to a raspberry pi using the i2c interface. This MQTT client is publishing the LUX value of the [BH1750](https://www.mouser.com/datasheet/2/348/bh1750fvi-e-186247.pdf?srsltid=AfmBOoqC7uAiZBA6RoouOt9ByvvPM5Sy5M-yFMTtI5dfTa2-e7MJFZq5). The project is an addon to the [FullPageOS](https://github.com/guysoft/FullPageOS) [mqttBH1750Client](https://github.com/olialb/mqttBH1750Client) but works also totally independent.

The configuration is done over an ini file. 

## Implementation notes

The project in implemented and tested with [Python 3.11](https://www.python.org/downloads/) and runs as systemd service for standard user *pi* for example in [FullPageOS](https://github.com/guysoft/FullPageOS).

The implementaion is using the folling python libraries, which need to be installed:
* [paho-mqtt](https://pypi.org/project/paho-mqtt/) to implement the mqtt client
* [i2c-tools](https://packages.debian.org/stable/source/i2c-tools) 
* [dev](https://packages.debian.org/de/sid/python3-dev) 
* [smbus](https://packages.debian.org/bullseye/python3-smbus) 


All this libraries are installed with the `setup.sh` shell script, which is part of this project. See next section [Installation](#installation)

All the other used python libraries are standard in latest Raspbery PI OS and should be available without installation.
 

## Installation 
**Precondition**: Linux (like [FullPageOS](https://github.com/guysoft/FullPageOS)) is installed on your Raspberry PI and up and running.
#### Step 1:
Login with ssh to your kioskdisplay with user *pi*
#### Step 2:
Clone this project with: 
```
git clone https://github.com/olialb/mqttBH1750Client
``` 
and go inside the project directory: 
```
cd mqttBH1750Client
```
#### Step 3:
Call setup: 
```
bash setup.sh
```
This installs the required python packages and configures a systemd service which is atomatically running the mqtt client after startup. The systemd service is started with the current user rights.

#### Step 4:
Configure the ini file for your personal needs: 
```
nano mqttBH1750Client.ini 
```
Details of the configuration you can find in next section: [Configuration](#configuration)


#### In case of problems:

If you have issues with your configuration and the service is not running as expected you can stop the service with:
```bash
sudo systemctl stop mqttBH1750Client
```
Adapt the ini file in section [[logging]](#section-logging) and enable *DEBUG* logging level. Than activate the virtual python environment and start the service by hand:
```bash
source venv/bin/activate
python mqtt_bh1750_client.py
```
Check the logging output. After everything is fixed, set the logging level back to *ERROR*, deactivate the virtual environment and start the systemd service again with:
```bash
deactivate
sudo systemctl start mqttBH1750Client
```

## Configuration
In the project directory you find the configuration *mqtt-display-client.ini*. Adapt this file with an editor like *nano*:
```bash
nano mqttBH1750Client.ini
```
The file has different sections. Most of the configuration you can keep untouched. The only thing which you need to adapt to your specific environment are:

* Address of your mqtt broker in section [[global]](#section-global)
* Username and password of your mqtt broker, if needed. In section [[global]](#section-global)
* ID of your display in section [[global]](#section-global)

This configuration you find in the first section of the ini file: [[global]](#section-global). 

#### Section **[global]**
This is the main configuration section. This is the only section where you need to adapt somthing to your environment. 
* *broker=* Set here your mqtt broker address. Apapt the ip address or use url like *myLocalMQTTBroker.local*
* *port=* You can keep the standard port 1883 if you do not have a special setup
* *username=* Set here your user name for the broker. Keep it empty if no username is configured
* *password=* Password of your mqtt broker
* *topicRoot=* configuration of the root path of the published topics
* *deviceName=* Unique name of this device
* *reconnectDelay*= Retry delay in seconds if connection is lost to broker
* *publishDelay*= Publish cycle in seconds for topics
* *fullPublishCycle*= Publish cycle even if topic content is not changed. Cycle is *fullPublishCycle* multiplied with *publishCycle* in seconds

#### Section **[logging]**
Configuration of the python logger which is used to log events

* *level*= configuration of the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
* *path=*" path to the log files
* *file=*" filename of the log files. If empty, logging in files is disabled

## Exposed MQTT topics and usage

The MQTT client is exposing the following topics:

### lux (numeric)
The current brightness of the display is exposed with the topic brightness `kiosk/01/DEVICE_NETWORK_NAME/lux`. 

