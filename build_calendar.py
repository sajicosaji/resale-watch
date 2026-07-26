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

def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

def load_items():
    items = []
    undated = []
    for filename, label, emoji, color in SOURCES:
        if not os.path.exists(filename):
            continue
        with open(filename, encoding="utf-8") as f:
            data = json.load(f)
        for it in data.get("items", []):
            deadline = parse_date(it.get("deadline"))
            if deadline and deadline < TODAY:
                # 締切を過ぎたものはもう行動できないので表示しない
                continue
            release_date = parse_date(it.get("release_date"))
            # 締切があればそちらを基準にカレンダーへ配置する（発売日より締切のほうが行動の期限として重要）
            d = deadline or release_date
            if not d:
                # release_date も deadline も無いエントリはカレンダーに一切出せない。
                # 黙って捨てると「配信したのにカレンダーに出ない」事故に気付けないので警告する。
                # 古いエントリは日付が無くて当然なので、直近7日以内に配信したものだけを対象にする
                posted = parse_date(it.get("date"))
                if posted and (TODAY - posted).days <= 7:
                    undated.append((filename, it.get("topic", "")))
                continue
            url = it.get("url", "")
            links = [
                {"label": l.get("label", ""), "url": l.get("url", ""), "app": l.get("app", "")}
                for l in it.get("links", [])
                if l.get("url", "").startswith("http") and l.get("label")
            ]
            items.append({
                "date": d,
                "deadline": deadline,
                # 締切日に配置した項目でも、発売日が別にあるなら本文に併記する（発売日が埋もれないように）
                "release_date": release_date if deadline and release_date and release_date != deadline else None,
                "topic": it.get("topic", ""),
                "price": it.get("price", ""),
                "url": url if url.startswith("http") else "",
                "links": links,
                "source": label,
                "emoji": emoji,
                "color": color,
            })
    return items, undated

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
                links_html = ""
                if it["links"]:
                    # 複数チャネルをまとめた項目は、それぞれ個別にクリックできる番号付きリンクにする
                    topic_html = topic_esc
                    chips = " ".join(
                        f'<a class="link-chip" href="{html.escape(l["url"])}" target="_blank" rel="noopener">'
                        f'<span class="link-chip-num">{i}</span>'
                        + (f'📱{html.escape(l["label"])}（{html.escape(l["app"])}が必要）' if l["app"] else html.escape(l["label"]))
                        + '</a>'
                        for i, l in enumerate(it["links"], start=1)
                    )
                    links_html = f'<div class="links">応募先: {chips}</div>'
                elif it["url"]:
                    topic_html = f'<a class="topic-link" href="{html.escape(it["url"])}" target="_blank" rel="noopener">{topic_esc} 🔗</a>'
                else:
                    topic_html = topic_esc
                deadline_html = ""
                if it["deadline"]:
                    dl = it["deadline"]
                    dl_days = (dl - TODAY).days
                    if dl_days == 0:
                        dl_label = "本日締切"
                    elif dl_days == 1:
                        dl_label = "明日締切"
                    else:
                        dl_label = f"あと{dl_days}日で締切"
                    deadline_html = f'<div class="deadline">⏰<span class="deadline-date">{dl.strftime("%m/%d")}</span><span class="deadline-label">{dl_label}</span></div>'
                release_html = ""
                if it["release_date"]:
                    release_html = f'<div class="release">🗓 発売日: {it["release_date"].strftime("%m/%d")}</div>'
                out.append(f'''
                <div class="item" style="border-left-color:{it['color']}">
                    <div class="source">{it['emoji']} {it['source']}</div>
                    <div class="topic">{topic_html}</div>
                    {links_html}
                    {deadline_html}
                    {release_html}
                    {price_html}
                </div>''')
            out.append('</div>')
        return "\n".join(out)

    upcoming_html = render_group(upcoming, "今後の予定はまだありません")
    past_html = render_group(past, "まだ履歴がありません")

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
  .links {{ font-size: 13px; margin-top: 6px; color: #666; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }}
  .link-chip {{ display: inline-flex; align-items: center; gap: 4px; color: #1660a8; text-decoration: none; background: #eef4fb; border-radius: 12px; padding: 2px 10px 2px 6px; }}
  .link-chip:hover {{ text-decoration: underline; }}
  .link-chip-num {{ display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; border-radius: 50%; background: #1660a8; color: #fff; font-size: 10px; font-weight: bold; }}
  @media (prefers-color-scheme: dark) {{ .links {{ color: #aaa; }} .link-chip {{ color: #6fb3ff; background: #1c2733; }} .link-chip-num {{ background: #6fb3ff; color: #1a1a1a; }} }}
  .price {{ font-size: 13px; color: #1d7a4f; margin-top: 4px; font-weight: bold; }}
  .deadline {{ display: flex; align-items: baseline; gap: 6px; font-size: 13px; color: #b3261e; margin-top: 4px; font-weight: bold; }}
  .deadline-date {{ font-variant-numeric: tabular-nums; font-family: "Consolas", "Yu Gothic UI", monospace; min-width: 42px; display: inline-block; }}
  .deadline-label {{ font-weight: normal; color: #8a4a45; }}
  @media (prefers-color-scheme: dark) {{ .deadline {{ color: #ff8a80; }} .deadline-label {{ color: #d9a29d; }} }}
  .release {{ font-size: 13px; color: #666; margin-top: 4px; }}
  @media (prefers-color-scheme: dark) {{ .release {{ color: #aaa; }} }}
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
    items, undated = load_items()
    # 変数名に html を使うと import した html モジュールを隠してしまうので page にする
    page = build_html(items)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Generated docs/index.html with {len(items)} dated items.")
    if undated:
        print(f"WARNING: 直近7日の配信のうち {len(undated)} 件が release_date / deadline を持たないため"
              f"カレンダーに表示されません（相場警戒アラート等、日付を持たないのが正常な項目も含みます）:")
        for filename, topic in undated[:10]:
            print(f"  - {filename}: {topic[:60]}")
        if len(undated) > 10:
            print(f"  ... 他 {len(undated) - 10} 件")

if __name__ == "__main__":
    main()
