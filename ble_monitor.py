"""
Smart Scale BLE Monitor
MY_SCALE (KT630B) - リアルタイム重量データ受信
Service: FFB0, Notify: FFB2, Write: FFB1
"""

import asyncio
import signal
from bleak import BleakScanner, BleakClient

TARGET_NAME = "MY_SCALE"

# GATT UUIDs
SERVICE_UUID = "0000ffb0-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ffb2-0000-1000-8000-00805f9b34fb"  # Server Tx Data
WRITE_UUID = "0000ffb1-0000-1000-8000-00805f9b34fb"   # Server Rx Data

running = True


def notification_handler(sender, data: bytearray):
    """Notificationデータを受信してパース"""
    hex_str = data.hex()
    # バイト列をわかりやすく表示
    byte_list = " ".join(f"{b:02X}" for b in data)
    print(f"[{len(data):2d} bytes] {byte_list}")

    # 既知のChipsea/ICOMON系フォーマットを試行パース
    if len(data) >= 6:
        # パターン1: 符号付き16bit (big endian)
        val_16be = int.from_bytes(data[3:5], byteorder='big', signed=True)
        # パターン2: 符号付き16bit (little endian)
        val_16le = int.from_bytes(data[3:5], byteorder='little', signed=True)
        # パターン3: 24bit (big endian) - KT630LBで確認済み
        if len(data) >= 7:
            val_24be = int.from_bytes(data[4:7], byteorder='big', signed=False)
            val_24le = int.from_bytes(data[4:7], byteorder='little', signed=False)
            print(f"  -> 解析候補: 16BE={val_16be} 16LE={val_16le} "
                  f"24BE={val_24be} 24LE={val_24le}")
        else:
            print(f"  -> 解析候補: 16BE={val_16be} 16LE={val_16le}")


async def find_scale():
    """MY_SCALEを探す"""
    print("=== MY_SCALE を探しています... ===")
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
    for d, adv in devices.values():
        if TARGET_NAME in (d.name or ""):
            print(f">>> 発見: {d.name} ({d.address}) RSSI:{adv.rssi}")
            return d
    return None


async def monitor():
    """接続してNotificationを監視"""
    global running

    device = await find_scale()
    if not device:
        print("MY_SCALE が見つかりません。電源を確認してください。")
        return

    print(f"\n=== {device.name} に接続中... ===")

    async with BleakClient(device.address) as client:
        print(f"接続成功!")
        print(f"\n=== FFB2 Notification 監視開始 ===")
        print("スケールに物を乗せたり降ろしたりしてください。")
        print("Ctrl+C で終了\n")

        await client.start_notify(NOTIFY_UUID, notification_handler)

        # Ctrl+Cまで待機
        try:
            while running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

        await client.stop_notify(NOTIFY_UUID)
        print("\n=== 監視終了 ===")


def handle_sigint(sig, frame):
    global running
    running = False


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)
    asyncio.run(monitor())
