import asyncio
import argparse
import logging
import struct
import curses
import signal
import sys

import h5py

from bleak import BleakClient, BleakScanner
from datetime import datetime
from tabulate import tabulate

import constants

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

def save_to_hdf5(filename, data):
    if filename is None:
        filename = datetime.now().strftime("output_%Y_%m_%d__%H_%M_%S.h5")
    with h5py.File(filename, "w") as file:
        data_group = file.create_group("data")
        for key, val in data.items():
            data_group.create_dataset(f"{key}", data=val)

async def read_temperature_and_humidity(client):
    res: bytearray = await client.read_gatt_char(constants.GET_TEMP_AND_HUMIDITY_ATTRIBUTE_UUID)
    temp, hum, vol = struct.unpack_from('<hBh', res)
    return temp / 100, hum, vol / 1000

async def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--name",
        help="the name of the bluetooth device to connect to",
        required=False
    )
    parser.add_argument(
        "--address",
        help="the address of the bluetooth device to connect to",
        required=False
    )

    parser.add_argument(
        "-t",
        "--time-sleep",
        help="Sleep time between requests",
        type=float,
        default=constants.TIME_SLEEP,
    )

    parser.add_argument(
        "--macos-use-bdaddr",
        action="store_true",
        help="when true use Bluetooth address instead of UUID on macOS",
    )

    parser.add_argument("-o", "--output", type=str, help="Output HDF5 file", required=False)

    args = parser.parse_args()

    logger.info("Scanning device")

    device = None

    if args.address:
        device = await BleakScanner.find_device_by_address(
            args.address, cb=dict(use_bdaddr=args.macos_use_bdaddr)
        )

    elif args.name:
        device = await BleakScanner.find_device_by_name(
            args.name, cb=dict(use_bdaddr=args.macos_use_bdaddr)
        )

    else:
        device = await BleakScanner.find_device_by_address(
            constants.DEVICE_ADDRESS, cb=dict(use_bdaddr=args.macos_use_bdaddr)
        )

    if device is None:
        logger.error("Could not find device")
        return

    async with BleakClient(device) as client:
        logger.info("Connected")

        data = {
            "temperature": [],
            "humidity": [],
            "datetime": [],
        }

        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        stdscr.nodelay(True)

        def cleanup(signal, frame):
            curses.nocbreak()
            stdscr.keypad(False)
            curses.echo()
            curses.endwin()
            save_to_hdf5(filename=args.output, data=data)
            sys.exit(0)

        signal.signal(signal.SIGINT, cleanup)

        try:
            while True:
                temp, hum, volt = await read_temperature_and_humidity(client)
                date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                data["temperature"].append(temp)
                data["humidity"].append(hum)
                data["datetime"].append(date_time)

                stdscr.clear()
                table_data = [["Date time", "Temperature, °C", "Humidity, %", "Voltage, V"]]
                table_data.append([date_time, temp, hum, volt])

                table_str = tabulate(table_data, headers="firstrow", tablefmt="grid")
                stdscr.addstr(0, 0, table_str)
                stdscr.refresh()

                await asyncio.sleep(args.time_sleep)
        except Exception as e:
            logger.error(f"{e}")
        finally:
            cleanup(None, None)

asyncio.run(main())
