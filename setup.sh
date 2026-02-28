#!/bin/bash
set -e

echo "======================================"
echo "  予約枠監視システム セットアップ"
echo "======================================"

# Python確認
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 が見つかりません。Homebrewでインストールしてください:"
    echo "   brew install python"
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# pip でインストール
echo ""
echo "📦 依存パッケージをインストール中..."
pip3 install playwright

echo ""
echo "🎭 Playwright ブラウザをインストール中..."
python3 -m playwright install chromium

echo ""
echo "======================================"
echo "  Slack Webhook URL の設定"
echo "======================================"
echo ""
echo "Slack の Incoming Webhook URL を入力してください。"
echo "取得方法: https://api.slack.com/messaging/webhooks"
echo ""
read -rp "Webhook URL: " webhook_url

if [[ -z "$webhook_url" ]]; then
    echo "⚠️  スキップしました。後から以下で設定できます:"
    echo "   export SLACK_WEBHOOK_URL='https://hooks.slack.com/...'"
else
    # .envファイルに保存
    echo "SLACK_WEBHOOK_URL=$webhook_url" > "$(dirname "$0")/.env"
    echo "✅ .env ファイルに保存しました"
fi

echo ""
echo "======================================"
echo "  セットアップ完了！"
echo "======================================"
echo ""
echo "起動方法:"
echo "   cd $(dirname "$0")"
echo "   ./run.sh"
echo ""
