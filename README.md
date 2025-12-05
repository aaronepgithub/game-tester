# ANT+ Heart Rate Monitor to Bluetooth LE Bridge

This application connects to an ANT+ heart rate monitor using a USB stick and broadcasts the heart rate data via Bluetooth LE using the BLE Heart Rate Service.

## Prerequisites

- Python 3.7+
- ANT+ USB stick (e.g., Garmin ANTUSB-m or similar)
- Heart rate monitor with known ANT+ device ID

## Installation

1. Install the required dependencies:
```bash
pip install openant bleak
```

2. Make sure your ANT+ USB stick is plugged in and accessible by the system.

3. Determine your heart rate monitor's ANT+ device ID (you may need to use ANT+ scanning tools to find this).

## Usage

1. Edit the `hr_monitor_bridge.py` file and replace the `HRM_DEVICE_ID` variable with your actual heart rate monitor's ANT+ device ID.

2. Run the application:
```bash
python hr_monitor_bridge.py
```

3. The application will:
   - Connect to your ANT+ USB stick
   - Listen for heart rate data from your specific device ID
   - Broadcast the heart rate data via Bluetooth LE using the standard Heart Rate Service (UUID 0x180D)

4. Any Bluetooth LE client (like a smartphone app) can now connect to this device and receive heart rate measurements.

## Configuration

The application has the following configurable parameters:

- `HRM_DEVICE_ID`: The ANT+ device ID of your heart rate monitor (required)
- `ant_network_key`: The ANT+ network key (defaults to public network key)

## Troubleshooting

- **Permission errors**: On Linux, you may need to add your user to the `dialout` group to access the USB device:
  ```bash
  sudo usermod -a -G dialout $USER
  ```
  Then log out and back in.

- **No ANT+ device found**: Make sure your USB stick is properly connected and recognized by the system.

- **Bluetooth permissions**: On some systems, you may need special permissions to create BLE peripherals.

## How It Works

1. The application initializes an ANT+ node using the openant library
2. It opens a channel to listen specifically for your heart rate monitor's device ID
3. When heart rate data is received via ANT+, it stores the value
4. Simultaneously, it creates a BLE peripheral using the bleak library
5. The stored heart rate value is broadcasted via the standard BLE Heart Rate Measurement characteristic
6. Any BLE client can connect and receive real-time heart rate updates

## BLE Heart Rate Service Specification

The application implements the standard Bluetooth Heart Rate Service (0x180D) with the Heart Rate Measurement characteristic (0x2A37), following the Bluetooth SIG specifications. The data format includes flags indicating 8-bit heart rate values, followed by the actual heart rate in beats per minute.
