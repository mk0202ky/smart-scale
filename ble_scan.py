"""
Smart Scale BLE Scanner & GATT Explorer
デバイス名: MY_SCALE (D0:4D:00:6E:2B:C4)
Step 1: スキャン → 接続 → GATT Service/Characteristic一覧取得
"""

import asyncio
from bleak import BleakScanner, BleakClient

TARGET_NAME = "MY_SCALE"
TARGET_ADDRESS = "D0:4D:00:6E:2B:C4"


async def scan():
    """BLEデバイスをスキャンしてMY_SCALEを探す"""
    print("=== BLE スキャン開始 (10秒) ===")
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)

    target = None
    for d, adv in devices.values():
        name = d.name or "Unknown"
        rssi = adv.rssi if adv else 0
        print(f"  {d.address}  RSSI:{rssi:4d}  {name}")
        if TARGET_NAME in (d.name or "") or d.address.upper() == TARGET_ADDRESS.upper():
            target = d

    if target:
        print(f"\n>>> ターゲット発見: {target.name} ({target.address})")
    else:
        print(f"\n>>> {TARGET_NAME} が見つかりませんでした。スケールの電源を確認してください。")

    return target


async def explore_gatt(device):
    """接続してGATT Service/Characteristicを一覧表示"""
    print(f"\n=== {device.name} に接続中... ===")

    async with BleakClient(device.address) as client:
        print(f"接続成功! MTU: {client.mtu_size}")

        print("\n=== GATT Services & Characteristics ===")
        for service in client.services:
            print(f"\n[Service] {service.uuid}")
            print(f"  Description: {service.description}")

            for char in service.characteristics:
                props = ", ".join(char.properties)
                print(f"  [Char] {char.uuid}")
                print(f"    Properties: {props}")
                print(f"    Handle: {char.handle}")

                # Readableならデータを読む
                if "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char.uuid)
                        print(f"    Value: {value.hex()} ({value})")
                    except Exception as e:
                        print(f"    Read error: {e}")

                # Descriptorも表示
                for desc in char.descriptors:
                    try:
                        value = await client.read_gatt_descriptor(desc.handle)
                        print(f"    [Desc] {desc.uuid}: {value.hex()}")
                    except Exception:
                        print(f"    [Desc] {desc.uuid}: (read failed)")


async def main():
    device = await scan()
    if device:
        await explore_gatt(device)


if __name__ == "__main__":
    asyncio.run(main())
