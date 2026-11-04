"""配信の下書き(outbox)を Discord へ送る。クラウドのルーティンから Discord へは直接送れないので、ここが受け持つ。

  deliver.py send            outbox/<種類>/NNN.json を番号順に送る
  deliver.py mark 種類...     last_run.json に実行時刻を書く
  deliver.py check           止まっている種類があれば Discord で知らせる
"""
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

LIMIT = 2000
HOOKS = {'resale': 'DISCORD_WEBHOOK', 'conveni': 'DISCORD_WEBHOOK_CONVENI'}
NAMES = {'resale': '転売ウォッチ', 'conveni': 'コンビニ配信'}
OUTBOX = pathlib.Path('outbox')
LAST_RUN = pathlib.Path('last_run.json')
JST = dt.timezone(dt.timedelta(hours=9))
UA = 'DiscordBot (https://github.com/sajicosaji/resale-watch, 1.0)'


def split(text):
    """2000文字に収まるよう、行の切れ目で分ける。"""
    parts, cur = [], ''
    for line in text.split('\n'):
        while len(line) > LIMIT:
            if cur:
                parts.append(cur)
                cur = ''
            parts.append(line[:LIMIT])
            line = line[LIMIT:]
        if len(cur) + len(line) + 1 > LIMIT:
            parts.append(cur)
            cur = line
        else:
            cur = f'{cur}\n{line}' if cur else line
    if cur.strip():
        parts.append(cur)
    return parts


def post(url, text):
    body = json.dumps({'content': text, 'allowed_mentions': {'parse': []}}).encode('utf-8')
    sep = '&' if '?' in url else '?'
    for attempt in range(5):
        req = urllib.request.Request(f'{url}{sep}wait=true', data=body, headers={'Content-Type': 'application/json', 'User-Agent': UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return res.status
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = float(json.loads(e.read().decode('utf-8') or '{}').get('retry_after', 2))
            elif e.code >= 500:
                wait = 2 * (attempt + 1)
            else:
                raise RuntimeError(f'Discordが断りました: {e.code}') from e
            time.sleep(min(wait, 30))
        except urllib.error.URLError:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError('Discordへ送れませんでした')


def load_outbox():
    """先に全部読んで確かめる。壊れていたら1通も送らない。"""
    plan = {}
    for d in sorted(p for p in OUTBOX.iterdir() if p.is_dir()):
        if d.name not in HOOKS and d.name != 'test':
            raise RuntimeError(f'知らない種類です: {d.name}')
        texts = []
        for f in sorted(d.glob('[0-9]*.json')):
            content = json.loads(f.read_text(encoding='utf-8'))['content']
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError(f'本文がありません: {f}')
            texts += split(content)
        if not (d / 'done.json').exists():
            raise RuntimeError(f'done.json がありません: {d}')
        plan[d.name] = texts
    if not plan:
        raise RuntimeError('outbox が空です')
    return plan


def via_cloud(kind):
    return json.loads((OUTBOX / kind / 'done.json').read_text(encoding='utf-8')).get('via') == 'cloud'


def send():
    plan = load_outbox()
    for kind, texts in plan.items():
        if texts and kind not in HOOKS:
            raise RuntimeError(f'{kind} には送り先がありません')
        for i, text in enumerate(texts):
            status = post(os.environ[HOOKS[kind]], text)
            print(f'{kind} {i + 1}/{len(texts)} {len(text)}文字 応答{status}')
            time.sleep(1)
        print(f'{kind}: {len(texts)}通')
        if kind in HOOKS and via_cloud(kind):
            post(os.environ[HOOKS[kind]], f'ℹ️ {NAMES[kind]}: PCが動いていなかったので、クラウドの予備で配信しました。開けないサイトがあるため、調査は浅めです。')
    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a', encoding='utf-8') as f:
            f.write(f"kinds={' '.join(plan)}\n")


def mark(kinds):
    data = json.loads(LAST_RUN.read_text(encoding='utf-8')) if LAST_RUN.exists() else {}
    now = dt.datetime.now(JST).isoformat(timespec='seconds')
    for k in kinds:
        data[k] = now
    LAST_RUN.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def check():
    hours = float(os.environ.get('MAX_HOURS') or 30)
    data = json.loads(LAST_RUN.read_text(encoding='utf-8')) if LAST_RUN.exists() else {}
    now = dt.datetime.now(JST)
    stale = 0
    for kind, env in HOOKS.items():
        at = data.get(kind)
        age = (now - dt.datetime.fromisoformat(at)).total_seconds() / 3600 if at else None
        print(f'{kind}: 最後の実行 {at} 経過 {age}')
        if age is None or age >= hours:
            stale += 1
            label = '（試験）' if hours != 30 else ''
            post(os.environ[env], f"⚠️{label} {NAMES[kind]}が{hours:.0f}時間以上動いていません。最後の実行: {at or '記録なし'}")
    print(f'止まっている種類: {stale}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'send':
        send()
    elif cmd == 'mark':
        mark(sys.argv[2:])
    elif cmd == 'check':
        check()
    else:
        sys.exit(__doc__)
