#!/usr/bin/env python3
"""
GitHub Actions用 予約枠監視スクリプト
31すまいのAPIを直接叩いて空き枠を確認する（Playwright不要）
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime
from pathlib import Path

TARGET_URL = os.environ.get("TARGET_URL", "https://www.31sumai.com/attend/X2571/")
STATE_FILE = "state.json"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
CHECK_COUNT = 5
CHECK_INTERVAL = 60  # 秒


def bukken_cd(url: str) -> str:
    """URLから物件コードを抽出する（例: .../attend/X2571/ → X2571）"""
    return [p for p in url.rstrip("/").split("/") if p][-1]


def api_url(url: str) -> str:
    return f"https://www.31sumai.com/services/api/attend/wakulists.json?bukkenCd={bukken_cd(url)}"


def fetch_available_slots(target_url: str) -> list[dict]:
    req = urllib.request.Request(
        api_url(target_url),
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": target_url,
        },
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        data = json.loads(res.read())

    slots = []
    for item in data.get("data", []):
        # statusSokuji or statusKibou が 1 = 空き
        if item.get("statusSokuji") != 2:
            continue

        # recepDate はUNIXタイムスタンプ（ミリ秒）
        ts = item.get("recepDate", 0)
        date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else ""

        time_raw = str(item.get("recepFrameFrom", ""))
        time_str = f"{time_raw[:-2]}:{time_raw[-2:]}" if len(time_raw) >= 3 else time_raw

        key = f"{date_str}_{time_raw}"
        slots.append({
            "date": date_str,
            "time": time_str,
            "key": key,
            "event": item.get("recepNm", ""),
        })

    return slots


def load_state() -> set[str]:
    if Path(STATE_FILE).exists():
        data = json.loads(Path(STATE_FILE).read_text())
        return set(data.get("notified_keys", []))
    return set()


def save_state(notified_keys: set[str]):
    Path(STATE_FILE).write_text(
        json.dumps({"notified_keys": list(notified_keys)}, ensure_ascii=False)
    )


def send_slack_notification(slots: list[dict], target_url: str):
    if not SLACK_WEBHOOK_URL:
        print("  SLACK_WEBHOOK_URL が設定されていません")
        return

    lines = [
        f"🎉 *予約枠に空きが出ました！*",
        f"🔗 <{target_url}|予約ページを開く>",
        "",
        "*空き枠一覧:*",
    ]
    for slot in slots:
        lines.append(f"🟢 {slot['date']}　{slot['time']}　{slot['event']}")

    payload = {"text": "\n".join(lines), "unfurl_links": False}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=10)
    print(f"  → Slack通知を送信しました ({len(slots)}件)")


def main():
    print(f"監視開始: {TARGET_URL}")
    print(f"{CHECK_COUNT}回チェック（{CHECK_INTERVAL}秒おき）")

    notified_keys = load_state()

    for i in range(CHECK_COUNT):
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] チェック {i + 1}/{CHECK_COUNT}", end=" ", flush=True)

        try:
            slots = fetch_available_slots(TARGET_URL)
            new_slots = [s for s in slots if s["key"] not in notified_keys]

            if new_slots:
                print(f"→ 新着 {len(new_slots)}件！")
                send_slack_notification(new_slots, TARGET_URL)
                for s in new_slots:
                    notified_keys.add(s["key"])
            elif slots:
                print(f"→ 空き {len(slots)}件（通知済み）")
            else:
                print("→ 空きなし")

            current_keys = {s["key"] for s in slots}
            notified_keys &= current_keys
            save_state(notified_keys)

        except Exception as e:
            print(f"→ エラー: {e}")

        if i < CHECK_COUNT - 1:
            time.sleep(CHECK_INTERVAL)

    print("完了")


if __name__ == "__main__":
    main()
