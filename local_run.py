"""PCの定時実行で、転売ウォッチとコンビニ配信の下書きを作って push する係。

調査はこのPCのログインで Claude Code が行う。Claude Code にコマンド実行は持たせず、
読み書きはリポジトリの中だけ（local_settings.json）。git はこのプログラムが行う。
Discord への送信は push を受けて deliver.yml が行う。失敗したらクラウドの予備が動く。
"""
import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
LOGS = ROOT.parent / 'logs'
JST = dt.timezone(dt.timedelta(hours=9))
CLAUDE = shutil.which('claude') or str(pathlib.Path.home() / '.local' / 'bin' / 'claude.exe')
NOWIN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
TOOLS = 'ToolSearch,WebSearch,WebFetch,Read,Glob,Grep,Write,Edit'

KINDS = {
    'resale': {
        'prompt': 'prompt.md', 'history': 'history.json', 'turns': 50,
        'checks': '''1. history.json の release_date が今後14日以内の項目の続報と相場
2. ポケカの抽選・再販（店舗の抽選を含む）
3. ワンピカードの抽選・再販
4. `https://gashapon.jp/schedule/` を WebFetch で読む
5. 一番くじの発売予定（厳選トリガー）
6. ボンボンドロップシール
7. 映画館限定ポップコーンケース・ノベルティ
8. ポイ活・黒字案件（F）
9. price 付きの過去の項目3〜4件の相場警戒・上昇検知''',
    },
    'conveni': {
        'prompt': 'conveni_prompt.md', 'history': 'history_conveni.json', 'turns': 50,
        'checks': '''1. history_conveni.json の release_date が今後14日以内の項目の続報と相場
2. conveni_prompt.md の調査範囲の各節を、節ごとに最低1回検索する
3. 一番くじの発売予定（厳選トリガーとアフターフォローを含む）
4. ローソン、セブンイレブン、ファミリーマートの限定品と引き換えキャンペーン''',
    },
}

PROMPT = '''今は日本時間 {now} です。無人実行です。質問せず最後までやり切ってください。

リポジトリ直下の `{prompt}` を読み、その手順どおりに調査・選別し、`{history}` を更新する。

## 調査の下限（省略しない）
「新情報なし」で早く終えない。検索は `{prompt}` の上限（15回程度）まで使い、次の全部を確かめる。
{checks}

検索結果の要約だけで判断せず、有望なページは WebFetch で中身を読む。`{history}` の最新の date が3日以上前なら、その間に始まった発売・受付も対象にする。

## 置き換える点
- Bash は使えない。日付は上に書いたものを使う。
- 「Discordへの投稿方法」の curl は使わない。投稿する本文は1通ごとに `outbox/{kind}/001.json`、`002.json` と番号順に `{{"content": "本文"}}` の形で Write する。1通2000文字まで。本文内の改行はJSONの \\n にする。
- 投稿するものが無い日は、本文のファイルを作らない。
- git は使わない。push と送信はこのあとプログラムが行う。

## 報告
通数、各通の先頭1行、検索した回数を報告して終了する。0通の時は、上の項目それぞれの結果を1行ずつ書く。
'''

FIX = '''`outbox/{kind}/` のJSONファイルか `{history}` が、JSONとして壊れています。

{error}

中身の意味は変えず、正しいJSONに直してください。本文内の改行は \\n、ダブルクォートは \\" にします。ほかのファイルはさわらないでください。
'''


def now():
    return dt.datetime.now(JST)


def log(msg):
    line = f"{now().strftime('%m/%d %H:%M:%S')} {msg}"
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / f"{now().strftime('%Y%m%d')}.log", 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    if sys.stdout:
        print(line, flush=True)


def git(*args, check=True):
    r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=NOWIN)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def sync():
    git('fetch', '-q', 'origin', 'main')
    git('checkout', '-q', '-f', 'main')
    git('reset', '-q', '--hard', 'origin/main')
    git('clean', '-qfdx')


def done_today(kind):
    path = ROOT / 'last_run.json'
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    return str(data.get(kind, '')).startswith(now().strftime('%Y-%m-%d'))


def ask_claude(prompt, turns, name):
    cmd = [CLAUDE, '-p', '--model', 'claude-sonnet-5-5', '--output-format', 'json', '--max-turns', str(turns),
           '--settings', str(ROOT / 'local_settings.json'), '--setting-sources', 'project', '--strict-mcp-config',
           '--permission-mode', 'dontAsk', '--tools', TOOLS, '--no-session-persistence']
    p = subprocess.run(cmd, input=prompt.encode('utf-8'), capture_output=True, cwd=ROOT, timeout=45 * 60, creationflags=NOWIN)
    out = p.stdout.decode('utf-8', 'replace')
    (LOGS / f"{now().strftime('%Y%m%d-%H%M')}_{name}.json").write_text(out + '\n--- stderr ---\n' + p.stderr.decode('utf-8', 'replace'), encoding='utf-8')
    try:
        j = json.loads(out)
    except ValueError as e:
        raise RuntimeError(f'Claude Code の応答が読めません rc={p.returncode}: {out[:200]}') from e
    log(f"{name}: {j.get('subtype')} {round((j.get('duration_ms') or 0) / 60000, 1)}分 {j.get('num_turns')}手 denied={len(j.get('permission_denials') or [])}")
    if p.returncode or j.get('is_error') or j.get('subtype') != 'success':
        raise RuntimeError(f"Claude Code が完了しませんでした: {j.get('subtype')} {str(j.get('result'))[:200]}")
    return j


def problems(kind, history):
    errs = []
    for f in sorted((ROOT / 'outbox' / kind).glob('*.json')) if (ROOT / 'outbox' / kind).exists() else []:
        try:
            content = json.loads(f.read_text(encoding='utf-8')).get('content')
            if not isinstance(content, str) or not content.strip():
                errs.append(f'{f.name}: content がありません')
        except ValueError as e:
            errs.append(f'{f.name}: {e}')
    try:
        json.loads((ROOT / history).read_text(encoding='utf-8'))
    except ValueError as e:
        errs.append(f'{history}: {e}')
    return errs


def run_kind(kind):
    cfg = KINDS[kind]
    sync()
    if done_today(kind):
        log(f'{kind}: 本日は配信済み')
        return
    ask_claude(PROMPT.format(now=now().strftime('%Y-%m-%d %H:%M'), prompt=cfg['prompt'], history=cfg['history'], checks=cfg['checks'], kind=kind), cfg['turns'], kind)
    errs = problems(kind, cfg['history'])
    if errs:
        log(f'{kind}: JSONを直させます {errs[:3]}')
        ask_claude(FIX.format(kind=kind, history=cfg['history'], error='\n'.join(errs)), 8, f'{kind}_fix')
        errs = problems(kind, cfg['history'])
        if errs:
            raise RuntimeError(f'JSONが直りません: {errs[:3]}')
    box = ROOT / 'outbox' / kind
    box.mkdir(parents=True, exist_ok=True)
    posted = len(list(box.glob('[0-9]*.json')))
    (box / 'done.json').write_text(json.dumps({'kind': kind, 'posted': posted, 'via': 'pc'}) + '\n', encoding='utf-8')
    extra = sorted(x for x in git('status', '--porcelain').splitlines() if 'outbox/' not in x and cfg['history'] not in x)
    if extra:
        log(f'{kind}: 想定外の変更は入れません {extra[:5]}')
    branch = f"claude/{kind}-{now().strftime('%Y%m%d-%H%M')}"
    git('checkout', '-q', '-b', branch)
    git('add', f'outbox/{kind}', cfg['history'])
    git('-c', 'user.name=resale-watch-bot', '-c', 'user.email=actions@users.noreply.github.com', 'commit', '-q', '-m', f'{kind} の下書き（{posted}通）')
    git('push', '-q', '-u', 'origin', branch)
    log(f'{kind}: {posted}通を push しました {branch}')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    log(f'開始 pid={os.getpid()}')
    failed = 0
    for kind in (sys.argv[1:] or KINDS):
        try:
            run_kind(kind)
        except Exception as e:  # noqa: BLE001  片方が失敗してももう片方は進める
            failed += 1
            log(f'{kind}: 失敗 {e}')
    try:
        sync()
    except Exception as e:  # noqa: BLE001
        log(f'戻せませんでした {e}')
    log(f'終了 失敗={failed}')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
