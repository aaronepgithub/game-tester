#!/usr/bin/env python3
"""
ANT+ Heart Rate Monitor to Bluetooth LE Bridge

This application connects to an ANT+ heart rate monitor using a USB stick
and broadcasts the heart rate data via Bluetooth LE using the BLE Heart Rate Service.
"""

import asyncio
import logging
import struct
import time
from typing import Optional

from openant import easy
from openant.easy.node import Node
from openant.easy.channel import Channel
from openant.base.message import Message
from openant.easy.filter import wait_for_event
from bless import BlessServer, BlessGATTService, BlessGATTCharacteristic
from bless.backends.server import GATTAttributePermissions
from bless.backends.server import GATTCharacteristicProperties
import uuid


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HeartRateMonitorBridge:
    def __init__(self, ant_device_id: int, ant_network_key: bytes = b'\xB9\xA5\x21\xFB\xBD\x72\xC3\x45'):
        """
        Initialize the bridge with the ANT+ device ID of the heart rate monitor.
        
        Args:
            ant_device_id: The ANT+ device ID of your heart rate monitor
            ant_network_key: The ANT+ network key (default is for ANT+ public network)
        """
        self.ant_device_id = 22184
        self.ant_network_key = ant_network_key
        self.ant_node = None
        self.ant_driver = None
        self.bluetooth_server = None
        self.current_heart_rate = 0
        self.last_heart_rate_time = 0
        
        # Bluetooth LE Heart Rate Service and Characteristic UUIDs
        self.HEART_RATE_SERVICE_UUID = "0000180D-0000-1000-8000-00805F9B34FB"
        self.HEART_RATE_MEASUREMENT_CHAR_UUID = "00002A37-0000-1000-8000-00805F9B34FB"
        
    def setup_ant_node(self):
        """Setup the ANT+ node to connect to the heart rate monitor."""
        # Create ANT+ node
        self.ant_node = easy.Node()
        
        # Request basic information about the USB stick
        capabilities = self.ant_node.request_message(Message.ID.RESPONSE_CAPABILITIES)
        max_channels, max_networks, _ = capabilities[1:4]
        logger.info(f"USB Stick capabilities: {max_channels} channels, {max_networks} networks")
        
        # Setup HRM sensor (channel 0)
        self.hrm_channel = self.ant_node.new_channel(easy.CHANNEL_TYPE_SLAVE_RX_ONLY, 0)
        self.hrm_channel.on_broadcast_data = self.on_ant_broadcast
        self.hrm_channel.on_burst_data = self.on_ant_broadcast
        
        # Set network key for the channel
        self.hrm_channel.set_network_key(0, self.ant_network_key)
        
        # Configure channel for HRM (device type 120, transmission type 0)
        DEVICE_TYPE = 120  # Heart Rate Monitor device type
        TRANSMISSION_TYPE = 0
        self.hrm_channel.set_id(self.ant_device_id, DEVICE_TYPE, TRANSMISSION_TYPE)
        
        # Open channel
        self.hrm_channel.open()
        
        logger.info(f"Listening for ANT+ HRM with device ID: {self.ant_device_id}")
    
    def on_ant_broadcast(self, data):
        """Callback for when ANT+ data is received."""
        if len(data) >= 5:
            # Parse ANT+ HRM data
            # Byte 0: Heart beat count (cumulative)
            # Byte 1: Computed heart rate
            heart_rate = data[1]
            
            if heart_rate != 0:  # Only update if valid heart rate
                self.current_heart_rate = heart_rate
                self.last_heart_rate_time = time.time()
                logger.info(f"Heart rate received: {heart_rate} BPM")
    
    async def start_bluetooth_server(self):
        """Start the Bluetooth LE server to broadcast heart rate data."""
        # Create a new Bless server
        server = BlessServer(name="HRM-Bridge")
        
        # Define UUIDs for Heart Rate Service and Characteristic
        heart_rate_service_uuid = "0000180D-0000-1000-8000-00805F9B34FB"  # Heart Rate Service
        heart_rate_measurement_uuid = "00002A37-0000-1000-8000-00805F9B34FB"  # Heart Rate Measurement
        
        # Create the heart rate service
        heart_rate_service = BlessGATTService(heart_rate_service_uuid)
        
        # Create the heart rate measurement characteristic
        heart_rate_char = BlessGATTCharacteristic(
            uuid=heart_rate_measurement_uuid,
            properties=GATTCharacteristicProperties.notify,
            permissions=GATTAttributePermissions.readable
        )
        
        # Add the characteristic to the service
        heart_rate_service.add_characteristic(heart_rate_char)
        
        # Add the service to the server
        server.add_service(heart_rate_service)
        
        # Subscribe to notifications (though we'll push data from our side)
        def on_update_requested(characteristic: BlessGATTCharacteristic, value: bytearray):
            logger.debug(f"Update requested for characteristic {characteristic}")
        
        server.subscribe(heart_rate_measurement_uuid, on_update_requested)
        
        # Start the server
        await server.start()
        logger.info("Bluetooth LE peripheral started and advertising as Heart Rate Monitor")
        
        # Store the server and characteristic for later use
        self.bluetooth_server = server
        self.heart_rate_characteristic = heart_rate_char
        
        # Main loop to broadcast heart rate data
        await self.broadcast_loop(server, heart_rate_char)
    
    async def broadcast_loop(self, server, heart_rate_char):
        """Main loop to broadcast heart rate data via Bluetooth LE."""
        while True:
            if self.current_heart_rate > 0:
                # Create heart rate measurement data following Bluetooth SIG specification
                # Format: Flags (1 byte) + Heart Rate (1-2 bytes)
                # Flags: bit 0 = 0 (Heart Rate Value Format is UINT8)
                # Other bits = 0 (no extra fields)
                flags = 0x00  # 8-bit heart rate value
                
                # Pack the heart rate data
                # Format: [flags, heart_rate_value]
                hr_data = struct.pack('<BB', flags, self.current_heart_rate)
                
                try:
                    # Update the characteristic value using Bless API
                    await server.update_value(heart_rate_char.uuid, hr_data)
                    logger.debug(f"Updated heart rate characteristic: {self.current_heart_rate} BPM")
                except Exception as e:
                    logger.error(f"Error updating heart rate characteristic: {e}")
            
            # Wait for 1 second before sending next update
            await asyncio.sleep(1)
    
    async def run(self):
        """Run the bridge application."""
        try:
            # Setup ANT+ connection
            self.setup_ant_node()
            
            # Start Bluetooth LE server
            await self.start_bluetooth_server()
            
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error in bridge application: {e}")
        finally:
            # Cleanup
            if self.ant_node:
                self.ant_node.stop()


async def main():
    """Main entry point."""
    # Replace with your actual ANT+ heart rate monitor device ID
    # You can find this using ANT+ monitoring tools or by scanning
    HRM_DEVICE_ID = 12345  # Change this to your actual device ID
    
    bridge = HeartRateMonitorBridge(ant_device_id=HRM_DEVICE_ID)
    await bridge.run()


if __name__ == "__main__":
    asyncio.run(main())
