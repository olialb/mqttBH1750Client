#!/bin/bash
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
abort()
{
   echo "
###########################
Abort!!        
###########################
An error occured Exiting..." >&2
   exit 1
}
trap 'abort' 0
#exit on error
set -e

echo "#########################################"
echo "Create virtual environment"
echo "#########################################"
python3 -m venv venv
source venv/bin/activate

echo "###########################################################################"
echo "Install required libs for bh1750 light sensor"
echo "###########################################################################"
sudo apt-get update
sudo apt-get install -y python3-dev i2c-tools
pip install smbus

echo "#########################################"
echo "Install the required python packages..."
echo "#########################################"
echo ""
pip install paho-mqtt

echo "#########################################"
echo "Fill templates"
echo "#########################################"
echo ""
python fill_oh_things_template.py 
 
echo "################################################"
echo "Install systemd serice..."
echo "service name: mqttBH1750Client"
eval "echo \"user        : $USER\""
echo "################################################"
echo ""

eval "echo \"$(cat mqttBH1750Client.service.template)\"" >mqttBH1750Client.service
sudo mv mqttBH1750Client.service /lib/systemd/system/mqttBH1750Client.service
sudo chmod 644 /lib/systemd/system/mqttBH1750Client.service
sudo systemctl daemon-reload
sudo systemctl enable mqttBH1750Client

echo "################################################"
echo "Stop the service with:"
echo "sudo systemctl stop mqttBH1750Client"
echo ""
echo "Start the service with:"
echo "sudo systemctl start mqttBH1750Client"
echo "################################################"
trap - 0
