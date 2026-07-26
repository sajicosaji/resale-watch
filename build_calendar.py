import html
import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).date()

SOURCES = [
    ("history.json", "本体", "🎴", "#e63946"),
    ("history_conveni.json", "コンビニ", "🏪", "#f77f00"),
    ("history_aichi.json", "愛知", "🍡", "#1d7a4f"),
    ("history_fukuoka.json", "福岡", "🍜", "#1660a8"),
]

def load_items():
    items = []
    for filename, label, emoji, color in SOURCES:
        if not os.path.exists(filename):
            continue
        with open(filename, encoding="utf-8") as f:
            data = json.load(f)
        for it in data.get("items", []):
            rd = it.get("release_date")
            if not rd:
                continue
            try:
                d = datetime.strptime(rd, "%Y-%m-%d").date()
            except ValueError:
                continue
            url = it.get("url", "")
            items.append({
                "date": d,
                "topic": it.get("topic", ""),
                "price": it.get("price", ""),
                "url": url if url.startswith("http") else "",
                "source": label,
                "emoji": emoji,
                "color": color,
            })
    return items

def build_html(items):
    upcoming = sorted([i for i in items if i["date"] >= TODAY], key=lambda x: x["date"])
    past = sorted([i for i in items if i["date"] < TODAY], key=lambda x: x["date"], reverse=True)[:20]

    def render_group(group, empty_msg):
        if not group:
            return f'<p class="empty">{empty_msg}</p>'
        by_date = {}
        for it in group:
            by_date.setdefault(it["date"], []).append(it)
        out = []
        for d in sorted(by_date.keys()):
            days_away = (d - TODAY).days
            if days_away == 0:
                badge = '<span class="badge today">本日</span>'
            elif days_away == 1:
                badge = '<span class="badge tomorrow">明日</span>'
            elif days_away > 0:
                badge = f'<span class="badge">{days_away}日後</span>'
            else:
                badge = f'<span class="badge past">{-days_away}日前</span>'
            out.append(f'<div class="date-group"><h3>{d.strftime("%Y年%m月%d日")} ({["月","火","水","木","金","土","日"][d.weekday()]}) {badge}</h3>')
            for it in by_date[d]:
                price_html = f'<div class="price">{html.escape(it["price"])}</div>' if it["price"] else ""
                topic_esc = html.escape(it["topic"])
                if it["url"]:
                    topic_html = f'<a class="topic-link" href="{html.escape(it["url"])}" target="_blank" rel="noopener">{topic_esc} 🔗</a>'
                else:
                    topic_html = topic_esc
                out.append(f'''
                <div class="item" style="border-left-color:{it['color']}">
                    <div class="source">{it['emoji']} {it['source']}</div>
                    <div class="topic">{topic_html}</div>
                    {price_html}
                </div>''')
            out.append('</div>')
        return "\n".join(out)

    upcoming_html = render_group(upcoming, "今後の予定はまだありません")
    past_html = render_group(past, "")

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>転売ウォッチ カレンダー</title>
<style>
  body {{ font-family: "Yu Gothic UI", "Meiryo", sans-serif; background: #f5f1e8; color: #2b2b2b; margin: 0; padding: 24px; }}
  .wrap {{ max-width: 720px; margin: 0 auto; }}
  h1 {{ font-size: 28px; margin-bottom: 4px; }}
  .updated {{ color: #8a8171; font-size: 13px; margin-bottom: 24px; }}
  h2 {{ font-size: 20px; border-bottom: 3px solid #e63946; padding-bottom: 6px; margin-top: 32px; }}
  .date-group h3 {{ font-size: 16px; margin: 20px 0 8px; color: #444; }}
  .badge {{ display: inline-block; background: #e63946; color: #fff; font-size: 12px; padding: 2px 8px; border-radius: 10px; margin-left: 8px; }}
  .badge.today {{ background: #d90429; font-weight: bold; }}
  .badge.tomorrow {{ background: #f77f00; }}
  .badge.past {{ background: #999; }}
  .item {{ background: #fff; border-left: 5px solid #ccc; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .source {{ font-size: 12px; color: #666; font-weight: bold; }}
  .topic {{ font-size: 15px; margin-top: 2px; }}
  .topic-link {{ color: #1660a8; text-decoration: none; }}
  .topic-link:hover {{ text-decoration: underline; }}
  @media (prefers-color-scheme: dark) {{ .topic-link {{ color: #6fb3ff; }} }}
  .price {{ font-size: 13px; color: #1d7a4f; margin-top: 4px; font-weight: bold; }}
  .empty {{ color: #999; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #1a1a1a; color: #eee; }}
    .item {{ background: #2a2a2a; box-shadow: none; }}
    .source {{ color: #aaa; }}
    .date-group h3 {{ color: #ccc; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <h1>🎴 転売ウォッチ カレンダー</h1>
  <div class="updated">最終更新: {datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")}（毎日自動更新）</div>

  <h2>📅 今後の予定</h2>
  {upcoming_html}

  <h2>📜 直近の履歴</h2>
  {past_html}
</div>
</body>
</html>
"""

def main():
    items = load_items()
    html = build_html(items)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated docs/index.html with {len(items)} dated items.")

if __name__ == "__main__":
    main()
