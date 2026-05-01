"""
Smart Scale リアルタイム重量モニター
MY_SCALE (KT630B) - BLE Weight Monitor
"""

import asyncio
import signal
from bleak import BleakScanner, BleakClient

TARGET_NAME = "MY_SCALE"

# GATT UUIDs (Service FFB0)
NOTIFY_UUID = "0000ffb2-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000ffb1-0000-1000-8000-00805f9b34fb"

# Packet format:
# [0]  AC    Header
# [1]  40    Mode/Unit flags
# [2]  SS    Stable flag (00=measuring, 01=stable)
# [3]  00    Reserved
# [4-6]      Weight raw (24bit big endian)
# [7-17] 00  Reserved
# [18] A6    Footer
# [19] CC    Checksum

SCALE_FACTOR = 1000.0  # raw / 1000 = grams

running = True


def parse_weight_packet(data: bytearray):
    """パケットをパースして重量データを返す"""
    if len(data) != 20 or data[0] != 0xAC:
        return None

    stable = data[2] == 0x01
    raw_weight = int.from_bytes(data[4:7], byteorder='big', signed=False)
    weight_g = raw_weight / SCALE_FACTOR

    return {
        "weight_g": weight_g,
        "weight_raw": raw_weight,
        "stable": stable,
        "mode": data[1],
    }


def notification_handler(sender, data: bytearray):
    """Notificationハンドラー"""
    result = parse_weight_packet(data)
    if result is None:
        hex_str = " ".join(f"{b:02X}" for b in data)
        print(f"[Unknown] {hex_str}")
        return

    stable_mark = " *" if result["stable"] else "  "
    weight = result["weight_g"]

    # ターミナル上書き表示
    print(f"\r{stable_mark} {weight:8.1f} g  (raw: {result['weight_raw']:>8d})", end="", flush=True)

    if result["stable"] and weight > 0:
        print(f"\r * {weight:8.1f} g  (raw: {result['weight_raw']:>8d})  [STABLE]")


async def main():
    global running

    print("=== Smart Scale 重量モニター ===")
    print("MY_SCALE を探しています...")

    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
    device = None
    for d, adv in devices.values():
        if TARGET_NAME in (d.name or ""):
            print(f"発見: {d.name} ({d.address}) RSSI:{adv.rssi}")
            device = d
            break

    if not device:
        print("MY_SCALE が見つかりません。電源を確認してください。")
        return

    print(f"接続中...")

    async with BleakClient(device.address) as client:
        print("接続成功!")
        print("=" * 50)
        print("  スケールに物を乗せてください")
        print("  * = 安定  Ctrl+C で終了")
        print("=" * 50)

        await client.start_notify(NOTIFY_UUID, notification_handler)

        try:
            while running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

        await client.stop_notify(NOTIFY_UUID)
        print("\n\n=== 終了 ===")


def handle_sigint(sig, frame):
    global running
    running = False


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)
    asyncio.run(main())
