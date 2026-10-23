#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""復号済みボード（平文HTML）と画面テキストから、データマン用の資料一式を作る。
使い方: build_digest.py <plain_dir> <text_dir> <out_dir>
出力: <out_dir>/<board>/README.md, 画面本文.md, data_*.json（＋ROOMY AIOは設問一覧）、<out_dir>/_boards.md
"""
import csv, glob, io, json, os, re, sys
from datetime import datetime, timezone, timedelta

PLAIN, TEXT, OUT = sys.argv[1:4]
JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)

BOARDS = {
    "roomy_aio": dict(name="ROOMY AIO（ルーミー AIO観測ダッシュボード）", url="https://ketrketr2.github.io/roomy-aio/",
                      repo="ketrketr2/ketrketr2.github.io（roomy-aio/）", update="自動更新なし（2026-10-03時点のスナップショット）",
                      what="ルーミーを想定した生活起点の問いに対する4つのAI面（Google AI Overviews／AI Mode／ChatGPT／Gemini）の実回答で、推奨（5位以内）・言及・引用・誤情報を測った分析ダッシュボード。競合・拡張分析・GA4/口コミとの突き合わせ・施策プランまで43画面。率には95%信頼区間。"),
    "roomy_command": dict(name="ROOMY COMMAND（ルーミー車種マーケ統合ボード）", url="https://ketrketr2.github.io/roomy-command/",
                          repo="ketrketr2/roomy-command", update="毎朝自動更新（06:53 JST・GA4実測を前日まで）",
                          what="ルーミー1車種を丸ごと統合した車種マーケボード。GA4実測×AI言及×市場（自販連）×SNS×ペルソナ×Google検索トレンドを15画面でクロス分析。"),
    "car_signal": dict(name="CAR×AI SIGNAL ROOM（車種別AI分析・司令室）", url="https://ketrketr2.github.io/toyota-car-board/signal.html",
                       repo="ketrketr2/toyota-car-board（docs/signal.html）", update="毎朝自動更新（07:35 JST）。AI指標は car-round（車種クエリの計測回）の値",
                       what="重点8車種×車種クエリ×4AI面の実測を司令室UIに集約。GEO総合スコア、車型別SoV・第一想起、ファネル（露出機会→言及→第一想起→流入）、30車種の言及トレンド、クエリ単位の4面回答・引用、公式引用のトヨタvs競合。"),
    "car_deepdive": dict(name="車種別AI分析（CAR × AI DEEP DIVE）", url="https://ketrketr2.github.io/toyota-car-board/",
                         repo="ketrketr2/toyota-car-board（docs/index.html）", update="毎朝自動更新（07:35 JST）。AI指標は car-round の値",
                         what="重点8車種（ルーミー／シエンタ／アルファード／ヴォクシー／ノア／アクア／ライズ／ランドクルーザー250）が、生活者がAIに投げる質問の中でどれだけ候補に挙がり、第一想起を取れているかを車種ごとに深掘りするボード。"),
    "ucar_signal": dict(name="U-CAR SIGNAL（トヨタ中古車 AI可視化ボード）", url="https://ketrketr2.github.io/toyota-ucar-board/",
                        repo="ketrketr2/toyota-ucar-board", update="手動更新（日次トレンドは形状モデル＋実測で水準補正。画面にバッジ表示）",
                        what="トヨタの中古車プラットフォーム（認定中古車・GAZOO・販売店U-Car）がAIに「買う場所」として挙がるかを測るボード。弾探し×全体のファネルKPI、AICAS段階評価、クエリと4面回答、専業店との争い、広告・GEO施策ROI。"),
    "ga4_command": dict(name="TOYOTA GA4 COMMAND（toyota.jp デジタル計測ボード）", url="https://ketrketr2.github.io/toyota-ga-board/",
                        repo="ketrketr2/toyota-ga-board", update="毎朝自動更新（GA4実測）",
                        what="toyota.jp全体のGA4実測を12セクターで俯瞰。サイト全体の流入・回遊・CV、JP活用実績（T-Connect等の導線効果測定）、車種横断ランキング。"),
}
IMG_HINT = re.compile(r'data:image|\.(jpg|jpeg|png|webp)"|base64,')


def md_esc(s):
    return str(s).replace('|', '｜').replace('\n', ' ')


def chart_tables(charts):
    out = []
    for ch in charts:
        title = ch.get('title') or ''
        if ch.get('lib') == 'chartjs':
            labels = ch.get('labels') or []
            ds = ch.get('datasets') or []
            if not ds:
                continue
            out.append(f"\n［図のデータ：{md_esc(title)}（{ch.get('type','')}）］")
            if labels and all(len(d.get('data') or []) == len(labels) for d in ds):
                out.append('| 項目 | ' + ' | '.join(md_esc(d.get('label') or f'系列{i+1}') for i, d in enumerate(ds)) + ' |')
                out.append('|---|' + '---:|' * len(ds))
                for i, lb in enumerate(labels[:200]):
                    out.append(f"| {md_esc(lb)} | " + ' | '.join(fmtv(d['data'][i]) for d in ds) + ' |')
                if len(labels) > 200:
                    out.append(f"（以下 {len(labels)-200} 行省略）")
            else:
                for d in ds:
                    out.append(f"- {md_esc(d.get('label') or '系列')}: " + ', '.join(fmtv(v) for v in (d.get('data') or [])[:200]))
                if labels:
                    out.append('- 項目: ' + ', '.join(md_esc(x) for x in labels[:200]))
        elif ch.get('lib') == 'echarts':
            series = ch.get('series') or []
            if not series:
                continue
            out.append(f"\n［図のデータ：{md_esc(title)}］")
            axis = ch.get('xAxis') or ch.get('yAxis')
            for sr in series:
                data = sr.get('data') or []
                if axis and len(axis) == len(data) and not any(isinstance(v, list) for v in data):
                    out.append(f"- {md_esc(sr.get('name') or sr.get('type'))}: " + ', '.join(f"{md_esc(a)}={fmtv(v)}" for a, v in list(zip(axis, data))[:200]))
                else:
                    out.append(f"- {md_esc(sr.get('name') or sr.get('type'))}: " + ', '.join(fmtv(v) for v in data[:200]))
    return '\n'.join(out)


def fmtv(v):
    if isinstance(v, float):
        return f"{v:.4g}" if abs(v) < 1e6 else f"{v:,.0f}"
    if isinstance(v, list):
        return '[' + ', '.join(fmtv(x) for x in v) + ']'
    return md_esc(v)


def clean_text(t):
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = '\n'.join(ln.rstrip() for ln in t.split('\n'))
    return t.strip()


def extract_data(html):
    """大きな JSON リテラル（画像辞書は除く）を {名前: オブジェクト} で返す。"""
    found = {}
    dec = json.JSONDecoder()
    for m in re.finditer(r'(?:window\.|const\s+|let\s+|var\s+)([A-Za-z_$][\w$]*)\s*=\s*(?=[\{\[])', html):
        st = m.end()
        try:
            o, end = dec.raw_decode(html, st)
        except Exception:
            continue
        if end - st < 3000:
            continue
        frag = html[st:min(end, st + 400000)]
        if len(IMG_HINT.findall(frag)) > 20:
            continue
        found[m.group(1)] = o
    for m in re.finditer(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S):
        try:
            o = json.loads(m.group(1))
            found.setdefault('embedded_json', o)
        except Exception:
            pass
    return found


def build_board(key):
    meta = BOARDS[key]
    tdir = os.path.join(TEXT, key)
    odir = os.path.join(OUT, key)
    os.makedirs(odir, exist_ok=True)
    screens = json.load(open(os.path.join(tdir, '_screens.json'), encoding='utf-8'))
    files = sorted(f for f in os.listdir(tdir) if f.endswith('.txt') and not f.startswith('_'))
    if key == 'roomy_aio':
        order = {s['id']: i for i, s in enumerate(screens)}
        files.sort(key=lambda f: order.get(f[:-4].split('_', 1)[1], 999))
    body = [f"# {meta['name']} — 全画面の本文", "",
            f"- 取り込み: {NOW:%Y-%m-%d %H:%M} JST（ボードを復号して全画面を描画し、表示された文字と図の数値をそのまま書き出したもの）",
            f"- 画面の数: {len(files)}", ""]
    index = []
    for f in files:
        txt = clean_text(open(os.path.join(tdir, f), encoding='utf-8').read())
        stem = f[:-4]
        head = txt.split('\n', 1)[0].lstrip('# ').strip() if txt.startswith('#') else stem
        if key == 'roomy_aio':
            code, sid = stem.split('_', 1)
            s = next((x for x in screens if x['id'] == sid), None)
            head = f"{s['code']} {s['title']}（{s['sub']}）" if s else stem
            txt_body = txt
        else:
            txt_body = txt.split('\n', 1)[1] if txt.startswith('#') else txt
        index.append(head)
        body += [f"## {head}", "", txt_body.strip(), ""]
        cj = os.path.join(tdir, stem + '.charts.json')
        if os.path.exists(cj):
            tb = chart_tables(json.load(open(cj, encoding='utf-8')))
            if tb.strip():
                body += [tb, ""]
    open(os.path.join(odir, '画面本文.md'), 'w', encoding='utf-8').write('\n'.join(body) + '\n')
    html = open(os.path.join(PLAIN, key + '.html'), encoding='utf-8').read()
    data = extract_data(html)
    dfiles = []
    for name, o in data.items():
        if re.search(r'IMG', name, re.I):
            continue
        fn = f"data_{name.strip('_') or 'main'}.json"
        json.dump(o, open(os.path.join(odir, fn), 'w', encoding='utf-8'), ensure_ascii=False)
        dfiles.append((fn, os.path.getsize(os.path.join(odir, fn))))
    return meta, index, dfiles


def roomy_questions():
    D = json.load(open(os.path.join(OUT, 'roomy_aio', 'data_D.json'), encoding='utf-8'))
    M = D['meta']
    names = M['names']
    vp = {p['pid']: p for p in D['v2']['vector']['points']}
    orbit = D['orig']['orbit']
    dem = {p['pid']: p for p in D['orig']['demand']['points']}
    surf = M['surf']
    rows = []
    for i, (pid, p) in enumerate(vp.items()):
        o = orbit[i] if i < len(orbit) and orbit[i]['q'] == p['q'] else next((x for x in orbit if x['q'] == p['q']), {})
        d = dem.get(pid, {})
        grp = 'ルーミー想定・車名なし' if p['own'] and not p['named'] else ('ルーミー想定・指名' if p['own'] else 'その他（コンパクト全般）')
        rk = o.get('rk') or [None] * 4
        tops = o.get('top') or [None] * 4
        rows.append({
            'pid': pid, '区分': grp, '問い': p['q'], '動機': p.get('drv', ''),
            '想定車種': '・'.join(names.get(a, a) for a in (o.get('af') or [])),
            **{f'ルーミー順位_{M["surf_short"][s]}': ('回答なし' if (rk[j] is not None and rk[j] < 0) else (rk[j] if rk[j] else '不在')) for j, s in enumerate(surf)},
            **{f'1位_{M["surf_short"][s]}': names.get(tops[j], tops[j] or '—') if tops[j] else '—' for j, s in enumerate(surf)},
            '検索キーワード': d.get('kw', ''), '月間検索数': (int(d['v']) if isinstance(d.get('v'), (int, float)) else ''),
        })
    order = {'ルーミー想定・車名なし': 0, 'ルーミー想定・指名': 1, 'その他（コンパクト全般）': 2}
    rows.sort(key=lambda r: (order[r['区分']], r['pid']))
    odir = os.path.join(OUT, 'roomy_aio')
    with open(os.path.join(odir, '設問一覧.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    L = ["# ROOMY AIO 設問一覧（計測に使った問い）", "",
         f"- 計測: {M['daily_from']}〜{M['daily_to']} の日次計測と car-round {M['car_round']}。ダッシュボード作成 {M['built']}",
         f"- 問いの数: コンパクト {M['n_compact_prompts']}問 × 4エンジン = {M['n_compact_cells']}回答。うちルーミー想定 {M['roomy_prompts']}問（車名なし {M['roomy_unnamed']}問・ルーミー指名 {M['roomy_named']}問）",
         "- 「ルーミー想定の45問×4エンジン=180回答」がダッシュボードの主指標（推奨5位以内入り率など）の分母",
         "- 順位は回答の中でルーミーが挙がった順番（1=最初）。「不在」は名前が出なかった回答。「回答なし」はそのエンジンが回答を出さなかった（AI Overviews が表示されない等）ため率の分母から除いたもの",
         "- 列の AIO=Google AI Overviews、AI Mode=Google AI Mode", ""]
    for g in ['ルーミー想定・車名なし', 'ルーミー想定・指名', 'その他（コンパクト全般）']:
        rs = [r for r in rows if r['区分'] == g]
        L += [f"## {g}（{len(rs)}問）", "", "| pid | 問い | 想定車種 | ルーミー順位 AIO／AI Mode／ChatGPT／Gemini | 1位の車 AIO／AI Mode／ChatGPT／Gemini | 検索キーワード（月間） |", "|---|---|---|---|---|---|"]
        for r in rs:
            rk = '／'.join(str(r[f'ルーミー順位_{x}']) for x in ['AIO', 'AI Mode', 'ChatGPT', 'Gemini'])
            tp = '／'.join(str(r[f'1位_{x}']) for x in ['AIO', 'AI Mode', 'ChatGPT', 'Gemini'])
            kw = f"{r['検索キーワード']}（{r['月間検索数']}）" if r['検索キーワード'] else ''
            L.append(f"| {r['pid']} | {md_esc(r['問い'])} | {md_esc(r['想定車種'])} | {rk} | {md_esc(tp)} | {md_esc(kw)} |")
        L.append("")
    tq = D['live'].get('trk_q') or {}
    if tq:
        L += ["## 日次の定点観測（A10）で毎日投げている問い", ""] + [f"- {k}: {v}" for k, v in tq.items()] + [""]
    open(os.path.join(odir, '設問一覧.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    return len(rows)


def car_round_note(key):
    """車種ボードは AI指標がどの計測回の値かを明記する（古い回のまま気づかない事故の防止）。"""
    try:
        d = json.load(open(os.path.join(OUT, key, 'data_DATA.json'), encoding='utf-8'))
    except Exception:
        return ''
    asof = d.get('asof') or {}
    cr = asof.get('car_round') or d.get('built')
    cells = (d.get('kpi') or {}).get('cells')
    if cells is None and isinstance(d.get('cars'), dict):
        cells = sum((c or {}).get('target_cells') or 0 for c in d['cars'].values())
    note = f"AI指標の計測回: {cr}" if cr else ''
    if cells == 0:
        note += '（注意: 車種クエリのセルが0。AI指標は「未計測」表示）'
    return note


def main():
    os.makedirs(OUT, exist_ok=True)
    reg = []
    manifest = {"built_at": NOW.isoformat(timespec='seconds'), "boards": []}
    for key in BOARDS:
        if not os.path.exists(os.path.join(TEXT, key, '_screens.json')) or not os.path.exists(os.path.join(PLAIN, key + '.html')):
            print('skip', key)
            manifest["boards"].append({"name": key, "ok": False, "screens": 0, "note": "復号または描画に失敗（前回の資料を使う）"})
            continue
        meta, index, dfiles = build_board(key)
        note = car_round_note(key) if key in ('car_signal', 'car_deepdive') else ''
        manifest["boards"].append({"name": key, "ok": len(index) > 0, "screens": len(index), "note": note})
        extra = []
        if key == 'roomy_aio':
            n = roomy_questions()
            extra.append(f"- `設問一覧.md` / `設問一覧.csv` … 計測に使った問い {n}問の全文と、問いごとのルーミー順位・各エンジンの1位の車・検索需要")
        readme = [f"# {meta['name']}", "",
                  f"- URL: {meta['url']}（ID/PW付き。中身は暗号化されている）",
                  f"- 置き場所: {meta['repo']}",
                  f"- 更新: {meta['update']}" + (f"／{note}" if note else ''),
                  f"- 取り込み日時: {NOW:%Y-%m-%d %H:%M} JST", "",
                  "## 何のボードか", "", meta['what'], "",
                  "## このフォルダの中身", "",
                  "- `画面本文.md` … 全画面を描画して、表示されている文字・表・図の数値（図の元データ）を画面ごとに書き出したもの。画面の数値はここが正",
                  *extra,
                  *[f"- `{fn}` … ボードに埋め込まれている元データ（{sz/1024:,.0f}KB）。画面に無い切り口の集計はこれから計算する" for fn, sz in dfiles], "",
                  "## 画面の一覧", ""] + [f"{i+1}. {h}" for i, h in enumerate(index)] + ["",
                  "## 答えるときの約束", "",
                  "- 数値は `画面本文.md` の表記どおりに引用し、画面名（例: A2 推奨（5位以内）入り数／率）を添える",
                  "- 画面に無い集計は data_*.json から計算してよい。その場合は「ボードの元データから集計」と明記する",
                  "- 「含まれていない」「見られない」と答える前に、`画面本文.md` と data_*.json を必ず検索する",
                  "- 社外向けの文面ではデータ取得元のサービス名を出さない"]
        open(os.path.join(OUT, key, 'README.md'), 'w', encoding='utf-8').write('\n'.join(readme) + '\n')
        reg.append((key, meta, len(index)))
        print('built', key, len(index), [f for f, _ in dfiles])
    L = ["# ボード台帳（データマンが読めるボードの一覧）", "",
         f"最終更新: {NOW:%Y-%m-%d %H:%M} JST", "",
         "ボードの質問を受けたら、まずここで該当ボードを特定し、`boards/<フォルダ>/README.md` → `画面本文.md` の順に読む。",
         "ここに無いボード・URLを聞かれたら「台帳に無い」と答え、URLと名前をけんけんさんにDMで知らせる（黙って推測しない）。", "",
         "| ボード | フォルダ | URL | 更新 | 画面数 |", "|---|---|---|---|---:|"]
    for key, meta, n in reg:
        L.append(f"| {meta['name']} | boards/{key}/ | {meta['url']} | {meta['update']} | {n} |")
    L += ["| AI VISIBILITY BOARD（GEO） | （toyota-geo-board の data/ をそのまま読む） | https://ketrketr2.github.io/toyota-geo-board/ | 毎朝自動更新 | — |", "",
          "## 呼び方の対応", "",
          "- 「ルーミーAIO」「ROOMY AIO」「TQPのルーミーダッシュボード」→ roomy_aio",
          "- 「ルーミーダッシュボード」「ROOMY COMMAND」→ roomy_command（どちらか曖昧なら両方を見て、どちらの話か確認する）",
          "- 「CAR×AI SIGNAL」「SIGNAL ROOM」「車種別AI分析」→ car_signal / car_deepdive",
          "- 「U-CAR SIGNAL」「中古車ボード」→ ucar_signal",
          "- 「GA4 COMMAND」「GAボード」→ ga4_command（GA4の任意の切り口は data/ga4/データマン回答ガイド.md の臨時クエリで取る）"]
    open(os.path.join(OUT, '_boards.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    json.dump(manifest, open(os.path.join(OUT, '_manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
