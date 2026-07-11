# 転売ウォッチ（resale-watch）

ポケモン関連商品とワンピースカードゲームの発売・予約・抽選・高騰情報を、毎日 朝8時・夜8時（日本時間）に自動調査してDiscordに配信するリポジトリ。

## 仕組み
- GitHub Actions が cron（UTC 23:00 / 11:00）で起動
- Claude Code CLI が `prompt.md` の指示に従ってWeb検索・要約
- 結果を Discord Webhook（Secretsの `DISCORD_WEBHOOK`）に投稿

## 必要なSecrets
- `CLAUDE_CODE_OAUTH_TOKEN` — `claude setup-token` で発行
- `DISCORD_WEBHOOK` — DiscordチャンネルのWebhook URL

## 手動実行
Actions タブ → resale-watch → Run workflow
