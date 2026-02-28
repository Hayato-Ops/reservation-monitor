#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"

# .env から環境変数を読み込む
if [[ -f "$DIR/.env" ]]; then
    export $(grep -v '^#' "$DIR/.env" | xargs)
fi

if [[ -z "$SLACK_WEBHOOK_URL" ]]; then
    echo "❌ SLACK_WEBHOOK_URL が設定されていません"
    echo "   ./setup.sh を実行するか、以下を設定してください:"
    echo "   export SLACK_WEBHOOK_URL='https://hooks.slack.com/...'"
    exit 1
fi

python3 "$DIR/monitor.py"
