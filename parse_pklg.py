"""
PacketLogger .pklg ファイルから ATT Write を抽出する解析ツール
目的: Nutridays が FFB1 に書き込むコマンドペイロード (tare/unit切替) を特定する
"""

import struct
import sys
from pathlib import Path

# .pklg packet types (Apple PacketLogger format)
PKT_HCI_CMD = 0x00
PKT_HCI_EVT = 0x01
PKT_ACL_SENT = 0x02      # host -> controller (iPhoneアプリからの送信)
PKT_ACL_RECV = 0x03      # controller -> host (スケールからの受信)

# L2CAP CID
CID_ATT = 0x0004

# ATT opcodes
ATT_WRITE_REQ = 0x12
ATT_WRITE_CMD = 0x52
ATT_HANDLE_VALUE_NTF = 0x1B
ATT_READ_BY_TYPE_RSP = 0x09  # GATT discovery response (handle→UUID マッピングに利用)


def parse_pklg(path: Path):
    """ .pklg を読み、エントリ毎に (timestamp, type, payload) をyield
    フォーマット (LE): 4B length + 4B sec + 4B usec + 1B type + payload
    length は (sec+usec+type+payload) のバイト数 = 9 + len(payload)
    """
    data = path.read_bytes()
    offset = 0
    while offset < len(data):
        if offset + 13 > len(data):
            break
        length = struct.unpack("<I", data[offset:offset+4])[0]
        sec = struct.unpack("<I", data[offset+4:offset+8])[0]
        usec = struct.unpack("<I", data[offset+8:offset+12])[0]
        pkt_type = data[offset+12]
        payload_len = length - 9
        if payload_len < 0 or offset + 4 + length > len(data):
            break
        payload = data[offset+13:offset+13+payload_len]
        offset += 4 + length
        yield (sec + usec / 1e6, pkt_type, payload)


def parse_acl(payload: bytes):
    """ ACL packet → (conn_handle, l2cap_cid, l2cap_payload) """
    if len(payload) < 4:
        return None
    # 2B handle/flags + 2B length
    h = struct.unpack("<H", payload[0:2])[0]
    conn_handle = h & 0x0FFF
    acl_len = struct.unpack("<H", payload[2:4])[0]
    acl_data = payload[4:4+acl_len]
    if len(acl_data) < 4:
        return None
    # L2CAP: 2B length + 2B CID
    l2_len = struct.unpack("<H", acl_data[0:2])[0]
    cid = struct.unpack("<H", acl_data[2:4])[0]
    l2_payload = acl_data[4:4+l2_len]
    return (conn_handle, cid, l2_payload)


def hex_str(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def analyze(path: Path):
    print(f"=== {path.name} ===\n")

    handle_to_value_handles = {}  # 後で UUID マッピングに使うため保持
    writes = []   # (ts, direction, conn_handle, opcode_name, att_handle, value)
    notifies = []

    first_ts = None
    for ts, ptype, payload in parse_pklg(path):
        if first_ts is None and ptype in (PKT_ACL_SENT, PKT_ACL_RECV):
            first_ts = ts

        if ptype not in (PKT_ACL_SENT, PKT_ACL_RECV):
            continue
        acl = parse_acl(payload)
        if acl is None:
            continue
        conn_handle, cid, l2 = acl
        if cid != CID_ATT or len(l2) < 1:
            continue

        opcode = l2[0]
        rel_ts = ts - first_ts if first_ts else 0

        if opcode in (ATT_WRITE_REQ, ATT_WRITE_CMD) and ptype == PKT_ACL_SENT:
            if len(l2) < 3:
                continue
            att_handle = struct.unpack("<H", l2[1:3])[0]
            value = l2[3:]
            opname = "WriteReq" if opcode == ATT_WRITE_REQ else "WriteCmd"
            writes.append((rel_ts, conn_handle, opname, att_handle, value))

        elif opcode == ATT_HANDLE_VALUE_NTF and ptype == PKT_ACL_RECV:
            if len(l2) < 3:
                continue
            att_handle = struct.unpack("<H", l2[1:3])[0]
            value = l2[3:]
            notifies.append((rel_ts, conn_handle, att_handle, value))

    # === Writes (host -> scale) ===
    print(f"--- ATT Writes (iPhone -> Scale): {len(writes)} 件 ---")
    print(f"{'time':>8s}  {'conn':>4s}  {'op':>9s}  {'handle':>6s}  value")
    for ts, ch, op, h, v in writes:
        print(f"{ts:8.3f}  {ch:4d}  {op:>9s}  0x{h:04X}  {hex_str(v)}")

    # === Notifications (scale -> host) のうちユニークな種類だけサマリ ===
    print(f"\n--- ATT Notifications (Scale -> iPhone): {len(notifies)} 件 ---")
    by_handle = {}
    for ts, ch, h, v in notifies:
        by_handle.setdefault(h, []).append((ts, v))
    for h, items in sorted(by_handle.items()):
        print(f"  handle 0x{h:04X}: {len(items)} 件  (例: {hex_str(items[0][1])})")

    # === 候補: 同じペイロードが複数回現れたWriteは「ボタン押下」確度が高い ===
    print(f"\n--- 重複出現 Write ペイロード (コマンド候補) ---")
    seen = {}
    for ts, ch, op, h, v in writes:
        key = (h, bytes(v))
        seen.setdefault(key, []).append(ts)
    for (h, v), tss in seen.items():
        if len(tss) >= 1:
            tss_str = ", ".join(f"{t:.2f}s" for t in tss)
            print(f"  handle 0x{h:04X} value [{hex_str(v)}]  x{len(tss)}  @ {tss_str}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # デフォルトでカレントディレクトリの .pklg を探す
        candidates = list(Path(".").glob("*.pklg"))
        if not candidates:
            print("Usage: python3 parse_pklg.py <capture.pklg>")
            sys.exit(1)
        path = candidates[0]
        print(f"(指定なしのため {path} を解析)")
    else:
        path = Path(sys.argv[1])

    if not path.exists():
        print(f"ファイルが見つかりません: {path}")
        sys.exit(1)

    analyze(path)
