#!/usr/bin/env python3
"""
31sumai 予約枠監視スクリプト
パークコート麻布十番東京 の空き枠が出た際にSlack通知を送る
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from datetime import datetime

from playwright.async_api import async_playwright

TARGET_URL = "https://www.31sumai.com/attend/X2571/"
CHECK_INTERVAL = 60  # 秒

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


def send_slack_notification(slots: list[dict], is_first_check: bool = False):
    if not SLACK_WEBHOOK_URL:
        print("[WARNING] SLACK_WEBHOOK_URL が設定されていません")
        return

    lines = [
        "🎉 *パークコート麻布十番東京* 予約枠に空きが出ました！",
        f"🔗 <{TARGET_URL}|予約ページを開く>",
        "",
        "*空き枠一覧:*",
    ]
    for slot in slots:
        status_icon = "🟢" if slot["status"] == "○" else "🟡"
        lines.append(f"{status_icon} {slot['date']}　{slot['time']}　{slot['status']}")

    payload = {
        "text": "\n".join(lines),
        "unfurl_links": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=10)
    print(f"  → Slack通知を送信しました ({len(slots)}件)")


async def get_available_slots(page) -> list[dict]:
    """ページをスクレイピングして空き枠リストを返す"""
    await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

    # 時間選択ボタンの読み込みを待機
    try:
        await page.wait_for_selector(".time_choose", timeout=30000)
    except Exception:
        # time_choose が見つからない場合（予約受付期間外など）
        return []

    # 有効な（満席でない）時間スロットを取得
    slots = []
    buttons = await page.query_selector_all(".js-time_choose_bt")

    for btn in buttons:
        is_disabled = await btn.evaluate(
            "el => el.classList.contains('c-btn_disable')"
        )
        if is_disabled:
            continue

        date = await btn.get_attribute("data-date") or ""
        time_val = await btn.get_attribute("data-time") or ""
        text = (await btn.inner_text()).strip()

        # ステータス文字（○ △）を本文から抽出
        status = ""
        for char in ["○", "△"]:
            if char in text:
                status = char
                break

        slots.append({
            "date": date,
            "time": time_val,
            "text": text,
            "status": status,
            "key": f"{date}_{time_val}",
        })

    return slots


async def main():
    if not SLACK_WEBHOOK_URL:
        print("=" * 50)
        print("⚠️  SLACK_WEBHOOK_URL が設定されていません")
        print("   export SLACK_WEBHOOK_URL='https://hooks.slack.com/...'")
        print("   を実行してから再起動してください")
        print("=" * 50)
        return

    print("=" * 50)
    print("📡 予約枠監視を開始します")
    print(f"   対象: パークコート麻布十番東京")
    print(f"   URL: {TARGET_URL}")
    print(f"   間隔: {CHECK_INTERVAL}秒")
    print("=" * 50)

    notified_keys: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        while True:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                print(f"[{now}] チェック中...", end="", flush=True)
                slots = await get_available_slots(page)

                available = [s for s in slots if s["status"] in ("○", "△")]
                new_slots = [s for s in available if s["key"] not in notified_keys]

                if new_slots:
                    print(f" 新着 {len(new_slots)}件！")
                    send_slack_notification(new_slots)
                    for s in new_slots:
                        notified_keys.add(s["key"])
                elif available:
                    print(f" 空き {len(available)}件（通知済み）")
                else:
                    print(" 空きなし")

                # 通知済みキーを現在の空き枠に限定（埋まったものを除去）
                current_keys = {s["key"] for s in available}
                notified_keys &= current_keys

            except Exception as e:
                print(f" エラー: {e}")

            await asyncio.sleep(CHECK_INTERVAL)

        await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 監視を終了しました")
