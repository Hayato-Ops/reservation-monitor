#!/usr/bin/env python3
"""
GitHub Actions用 予約枠監視スクリプト
ブラウザを起動したまま5回チェック（1分おき）して終了する
状態はstate.jsonに保存し、GitHub Actionsのキャッシュで引き継ぐ
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

TARGET_URL = "https://www.31sumai.com/attend/X2571/"
STATE_FILE = "state.json"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
CHECK_COUNT = 5    # 1ジョブあたりのチェック回数
CHECK_INTERVAL = 60  # チェック間隔（秒）


def load_state() -> set[str]:
    if Path(STATE_FILE).exists():
        data = json.loads(Path(STATE_FILE).read_text())
        return set(data.get("notified_keys", []))
    return set()


def save_state(notified_keys: set[str]):
    Path(STATE_FILE).write_text(
        json.dumps({"notified_keys": list(notified_keys)}, ensure_ascii=False)
    )


def send_slack_notification(slots: list[dict]):
    if not SLACK_WEBHOOK_URL:
        print("  SLACK_WEBHOOK_URL が設定されていません")
        return

    lines = [
        "🎉 *パークコート麻布十番東京* 予約枠に空きが出ました！",
        f"🔗 <{TARGET_URL}|予約ページを開く>",
        "",
        "*空き枠一覧:*",
    ]
    for slot in slots:
        icon = "🟢" if slot["status"] == "○" else "🟡"
        lines.append(f"{icon} {slot['date']}　{slot['time']}　{slot['status']}")

    payload = {"text": "\n".join(lines), "unfurl_links": False}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=10)
    print(f"  → Slack通知を送信しました ({len(slots)}件)")


async def scrape_slots(page) -> list[dict]:
    await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

    try:
        await page.wait_for_selector(".time_choose", timeout=30000)
    except Exception:
        print("  時間スロットが見つかりません（受付期間外の可能性）")
        return []

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
        status = "○" if "○" in text else "△" if "△" in text else ""

        slots.append({
            "date": date,
            "time": time_val,
            "text": text,
            "status": status,
            "key": f"{date}_{time_val}",
        })

    return slots


async def main():
    print(f"監視開始: {TARGET_URL}")
    print(f"{CHECK_COUNT}回チェック（{CHECK_INTERVAL}秒おき）")

    notified_keys = load_state()

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

        for i in range(CHECK_COUNT):
            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] チェック {i + 1}/{CHECK_COUNT}", end=" ", flush=True)

            try:
                slots = await scrape_slots(page)
                available = [s for s in slots if s["status"] in ("○", "△")]
                new_slots = [s for s in available if s["key"] not in notified_keys]

                if new_slots:
                    print(f"→ 新着 {len(new_slots)}件！")
                    send_slack_notification(new_slots)
                    for s in new_slots:
                        notified_keys.add(s["key"])
                elif available:
                    print(f"→ 空き {len(available)}件（通知済み）")
                else:
                    print("→ 空きなし")

                # 埋まった枠を通知済みリストから除去
                current_keys = {s["key"] for s in available}
                notified_keys &= current_keys
                save_state(notified_keys)

            except Exception as e:
                print(f"→ エラー: {e}")

            if i < CHECK_COUNT - 1:
                await asyncio.sleep(CHECK_INTERVAL)

        await browser.close()

    print("完了")


if __name__ == "__main__":
    asyncio.run(main())
