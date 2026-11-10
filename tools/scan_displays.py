"""List named CoolLED advertisements as JSON; does not connect or write."""
import asyncio
import json
import sys

from bleak import BleakScanner


async def scan():
    found = await BleakScanner.discover(timeout=15, return_adv=True)
    devices = []
    for device, advertisement in found.values():
        name = advertisement.local_name or device.name or ''
        if name.lower().startswith(('coolledx', 'coolledm')):
            devices.append({'name': name, 'address': device.address})
    return sorted(devices, key=lambda item: (item['name'].lower(), item['address']))


if __name__ == '__main__':
    try:
        print(json.dumps(asyncio.run(scan())))
    except Exception as exc:
        print(f'Bluetooth scan failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
