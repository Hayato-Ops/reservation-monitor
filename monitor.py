#!/usr/bin/env python3
"""
31すまい 予約枠監視スクリプト（ローカル実行用）
APIを直接叩いて空き枠を確認する（Playwright不要）
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime

TARGET_URL = os.environ.get("TARGET_URL", "https://www.31sumai.com/attend/X2571/")
CHECK_INTERVAL = 60  # 秒
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


def bukken_cd(url: str) -> str:
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
        if item.get("statusSokuji") != 2:
            continue

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


def send_slack_notification(slots: list[dict], target_url: str):
    if not SLACK_WEBHOOK_URL:
        print("[WARNING] SLACK_WEBHOOK_URL が設定されていません")
        return

    lines = [
        "🎉 *予約枠に空きが出ました！*",
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
    print("=" * 50)
    print("📡 予約枠監視を開始します")
    print(f"   URL: {TARGET_URL}")
    print(f"   間隔: {CHECK_INTERVAL}秒")
    print("=" * 50)

    if not SLACK_WEBHOOK_URL:
        print("⚠️  SLACK_WEBHOOK_URL が設定されていません")
        return

    notified_keys: set[str] = set()

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] チェック中...", end=" ", flush=True)

        try:
            slots = fetch_available_slots(TARGET_URL)
            new_slots = [s for s in slots if s["key"] not in notified_keys]

            if new_slots:
                print(f"新着 {len(new_slots)}件！")
                send_slack_notification(new_slots, TARGET_URL)
                for s in new_slots:
                    notified_keys.add(s["key"])
            elif slots:
                print(f"空き {len(slots)}件（通知済み）")
            else:
                print("空きなし")

            current_keys = {s["key"] for s in slots}
            notified_keys &= current_keys

        except Exception as e:
            print(f"エラー: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 監視を終了しました")
