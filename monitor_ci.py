#!/usr/bin/env python3
"""
GitHub Actions用 予約枠監視スクリプト
6時間ループして空き枠があるたびにSlack通知する
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime

TARGET_URL = os.environ.get("TARGET_URL") or "https://www.31sumai.com/attend/X2571/"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
CHECK_COUNT = 360   # 6時間（1分おき）
CHECK_INTERVAL = 60


def bukken_cd(url: str) -> str:
    return [p for p in url.rstrip("/").split("/") if p][-1]


def fetch_available_slots(target_url: str) -> list[dict]:
    req = urllib.request.Request(
        f"https://www.31sumai.com/services/api/attend/wakulists.json?bukkenCd={bukken_cd(target_url)}",
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
        date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
        time_raw = str(item.get("recepFrameFrom", ""))
        time_str = time_raw[:-2] + ":" + time_raw[-2:] if len(time_raw) >= 3 else time_raw
        slots.append({
            "date": date_str,
            "time": time_str,
            "event": item.get("recepNm", ""),
        })
    return slots


def send_slack_notification(slots: list[dict], target_url: str):
    if not SLACK_WEBHOOK_URL:
        print("  SLACK_WEBHOOK_URL が設定されていません")
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
    print(f"監視開始: {TARGET_URL}")
    print(f"{CHECK_COUNT}回チェック（{CHECK_INTERVAL}秒おき）")

    for i in range(CHECK_COUNT):
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] チェック {i + 1}/{CHECK_COUNT}", end=" ", flush=True)

        try:
            slots = fetch_available_slots(TARGET_URL)
            if slots:
                print(f"→ 空き {len(slots)}件！")
                send_slack_notification(slots, TARGET_URL)
            else:
                print("→ 空きなし")
        except Exception as e:
            print(f"→ エラー: {e}")

        if i < CHECK_COUNT - 1:
            time.sleep(CHECK_INTERVAL)

    print("完了")


if __name__ == "__main__":
    main()
