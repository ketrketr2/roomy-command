#!/usr/bin/env python3
"""ROOMY COMMAND: Windsor.ai REST APIから日次データ一式を取得し pull/ に保存する。
GitHub Actions（毎朝JST）で実行される。仕様は tools/DAILY.md と完全一致（refresh.py が読む形式）。
必要環境変数: WINDSOR_API_KEY
使い方: python3 tools/fetch_windsor.py   （カレント=リポジトリ直下。pull/ を作成）
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

KEY = os.environ.get('WINDSOR_API_KEY')
if not KEY:
    sys.exit('WINDSOR_API_KEY 未設定')

ACC = '324699885'
BASE = 'https://connectors.windsor.ai/googleanalytics4'
TODAY = (date.fromisoformat(os.environ['FETCH_TODAY']) if os.environ.get('FETCH_TODAY')
         else datetime.now(ZoneInfo('Asia/Tokyo')).date())
YB = TODAY - timedelta(days=1)          # 前日（データ終端）
D90 = YB - timedelta(days=89)
D28 = YB - timedelta(days=27)
D3  = YB - timedelta(days=2)

def q(fields, dfrom, dto, flt=None, extra=None):
    p = {'api_key': KEY, 'select_accounts': ACC, '_renderer': 'json',
         'fields': ','.join(fields), 'date_from': str(dfrom), 'date_to': str(dto)}
    if flt is not None:
        p['filter'] = json.dumps(flt, ensure_ascii=False)
    if extra:
        p.update(extra)
    url = BASE + '?' + urllib.parse.urlencode(p)
    last = None
    for att in range(3):
        try:
            with urllib.request.urlopen(url, timeout=240) as r:
                data = json.loads(r.read().decode('utf-8'))
            rows = data.get('data', data if isinstance(data, list) else [])
            return rows
        except Exception as e:
            last = e
            time.sleep(8 * (att + 1))
    raise SystemExit(f'Windsor取得失敗: {fields} {dfrom}..{dto}: {last}')

def num(x):
    if x is None or x == '':
        return 0
    f = float(x)
    return int(f) if f.is_integer() else round(f, 4)

ROOMY = [['page_path', 'contains', '/roomy/']]
os.makedirs('pull', exist_ok=True)
def save(name, obj):
    json.dump(obj, open(f'pull/{name}', 'w', encoding='utf-8'), ensure_ascii=False)
    print('saved', name)

# ---- q1: 90日 日次配列 ----
rows = q(['date', 'sessions', 'totalusers', 'newusers', 'engaged_sessions'], D90, YB, ROOMY)
by = {r['date'][:10]: r for r in rows}
dates = [str(D90 + timedelta(days=i)) for i in range(90)]
assert dates[-1] == str(YB)
missing = [d for d in dates if d not in by]
if len(missing) > 2:
    sys.exit(f'q1: 欠損日が多すぎる {missing[:5]}...')
if str(YB) not in by:
    sys.exit('q1: 前日データ未反映（GA4集計遅延の可能性）— デプロイ中止')
save('q1_daily.json', {
    'dates': dates,
    'sess': [num(by.get(d, {}).get('sessions', 0)) for d in dates],
    'users': [num(by.get(d, {}).get('totalusers', 0)) for d in dates],
    'newu': [num(by.get(d, {}).get('newusers', 0)) for d in dates],
    'eng': [num(by.get(d, {}).get('engaged_sessions', 0)) for d in dates]})

# ---- q2: 直近3日 チャネル日次 ----
rows = q(['date', 'session_default_channel_group', 'sessions'], D3, YB, ROOMY)
o = {}
for r in rows:
    d = r['date'][:10]
    o.setdefault(d, {})
    ch = r['session_default_channel_group']
    o[d][ch] = o[d].get(ch, 0) + num(r['sessions'])
save('q2_chdaily3.json', o)

# ---- q3: 直近3日 CVイベント ----
EV7 = ['maker_estimate_complete', 'dealer_estimate_complete', 'dealer_search',
       'test_drive_normal_reserve_complete', 'test_drive_instant_reserve_complete',
       'purchase_consultation', 'tel']
F_ROOMYCAR = ['customevent_car_model', 'contains', 'ルーミー']
rows = q(['date', 'event_name', 'event_count'], D3, YB,
         [F_ROOMYCAR, 'and', ['event_name', 'in', json.dumps(EV7)]])
o = {}
for r in rows:
    d = r['date'][:10]
    o.setdefault(d, {})
    o[d][r['event_name']] = o[d].get(r['event_name'], 0) + num(r['event_count'])
save('q3_cv3.json', o)

# ---- q4: ページ上位15（90日） ----
rows = q(['page_path', 'sessions', 'totalusers', 'engaged_sessions'], D90, YB, ROOMY, {'_max_rows': '300'})
rows.sort(key=lambda r: -float(r['sessions'] or 0))
save('q4_pages.json', [[r['page_path'], num(r['sessions']), num(r['totalusers']), num(r['engaged_sessions'])] for r in rows[:15]])

# ---- q5: ランディング上位10（28日） ----
rows = q(['landing_page', 'sessions', 'engaged_sessions'], D28, YB, [['landing_page', 'contains', '/roomy']], {'_max_rows': '300'})
rows.sort(key=lambda r: -float(r['sessions'] or 0))
save('q5_landing.json', [[r['landing_page'], num(r['sessions']), num(r['engaged_sessions'])] for r in rows[:10]])

# ---- q6: エンゲージメント指標（28日・単一行） ----
rows = q(['engagement_rate', 'bounce_rate', 'average_session_duration', 'screen_page_views_per_session'], D28, YB, ROOMY)
r0 = rows[0] if rows else {}
save('q6_eng28.json', {'er': num(r0.get('engagement_rate')), 'br': num(r0.get('bounce_rate')),
                       'dur': num(r0.get('average_session_duration')), 'pvs': num(r0.get('screen_page_views_per_session'))})

# ---- q7: 年代×性別（90日） ----
rows = q(['age', 'gender', 'sessions'], D90, YB, ROOMY)
AGES = ['18-24', '25-34', '35-44', '45-54', '55-64', '65+']
o = {'m': {a: 0 for a in AGES}, 'f': {a: 0 for a in AGES}, 'unknown': 0}
for r in rows:
    g, a, s = r['gender'], r['age'], num(r['sessions'])
    if g == 'male' and a in AGES: o['m'][a] += s
    elif g == 'female' and a in AGES: o['f'][a] += s
    else: o['unknown'] += s
save('q7_ag.json', o)

# ---- q8: 地域上位15（90日） ----
rows = q(['region', 'sessions'], D90, YB, ROOMY, {'_max_rows': '200'})
rows = [r for r in rows if r['region'] and r['region'] != '(not set)']
rows.sort(key=lambda r: -float(r['sessions'] or 0))
save('q8_region.json', [[r['region'], num(r['sessions'])] for r in rows[:15]])

# ---- q9: 当月累計 ----
m1 = YB.replace(day=1)
rows = q(['sessions', 'totalusers'], m1, YB, ROOMY)
r0 = rows[0] if rows else {}
save('q9_month.json', {'sess': num(r0.get('sessions')), 'users': num(r0.get('totalusers'))})

# ---- q9b: 前月確定値（停止が月境界をまたいだときの monthly/R_LONG ヒール用） ----
pm_last = m1 - timedelta(days=1); pm_first = pm_last.replace(day=1)
rows = q(['sessions', 'totalusers'], pm_first, pm_last, ROOMY)
r0 = rows[0] if rows else {}
save('q9_prevmonth.json', {'ym': str(pm_first)[:7], 'sess': num(r0.get('sessions')), 'users': num(r0.get('totalusers'))})

# ---- q10: source/medium 上位20（28日） ----
rows = q(['source', 'medium', 'sessions', 'engaged_sessions'], D28, YB, ROOMY, {'_max_rows': '300'})
rows.sort(key=lambda r: -float(r['sessions'] or 0))
save('q10_sm.json', [[f"{r['source']} / {r['medium']}", num(r['sessions']), num(r['engaged_sessions'])] for r in rows[:20]])

# ---- q11: サイト全体（28日） ----
rows = q(['event_name', 'event_count'], D28, YB,
         [['event_name', 'in', json.dumps(['sign_up', 'estimate_simulation_complete'])]])
agg = {}
for r in rows:
    agg[r['event_name']] = agg.get(r['event_name'], 0) + num(r['event_count'])
save('q11_sitewide.json', {'signup28': agg.get('sign_up', 0), 'estAll28': agg.get('estimate_simulation_complete', 0)})

# ---- q12: 全車種CV（28日） ----
K12 = {'maker_estimate_complete': 'mkr', 'dealer_estimate_complete': 'dlr',
       'test_drive_normal_reserve_complete': 'tdn', 'test_drive_instant_reserve_complete': 'tdi'}
rows = q(['customevent_car_model', 'event_name', 'event_count'], D28, YB,
         [['event_name', 'in', json.dumps(list(K12))]], {'_max_rows': '3000'})
out = []
for r in rows:
    car = (r['customevent_car_model'] or '').lstrip(';')
    if not car:
        continue
    out.append([car, K12[r['event_name']], num(r['event_count'])])
save('q12_allcar.json', out)

# ---- q13: シエンタ／ライズ（90日集計） ----
for path, name in (('/sienta/', 'q13_sienta.json'), ('/raize/', 'q13_raize.json')):
    rows = q(['sessions', 'totalusers', 'newusers', 'engaged_sessions'], D90, YB, [['page_path', 'contains', path]])
    r0 = rows[0] if rows else {}
    save(name, [num(r0.get('sessions')), num(r0.get('totalusers')), num(r0.get('newusers')), num(r0.get('engaged_sessions'))])

# ---- q14: チャネル集計（90日） ----
rows = q(['session_default_channel_group', 'sessions', 'totalusers', 'newusers', 'engaged_sessions'], D90, YB, ROOMY)
save('q14_chagg.json', [[r['session_default_channel_group'], num(r['sessions']), num(r['totalusers']),
                         num(r['newusers']), num(r['engaged_sessions'])] for r in rows])

# ---- q15: チャネル×CV（90日 → 45日×2分割） ----
EV5 = [e for e in EV7 if e not in ('purchase_consultation', 'tel')]
F15 = [F_ROOMYCAR, 'and', ['event_name', 'in', json.dumps(EV5)]]
K15 = {'maker_estimate_complete': 'mkr', 'dealer_estimate_complete': 'dlr', 'dealer_search': 'ds',
       'test_drive_normal_reserve_complete': 'tdn', 'test_drive_instant_reserve_complete': 'tdi'}
mid = D90 + timedelta(days=44)
o = {}
for hk, (f, t) in (('h1', (D90, mid)), ('h2', (mid + timedelta(days=1), YB))):
    rows = q(['session_default_channel_group', 'event_name', 'event_count'], f, t, F15)
    o[hk] = [[r['session_default_channel_group'], K15[r['event_name']], num(r['event_count'])] for r in rows]
save('q15_chcv.json', o)

print(f'FETCH COMPLETE: 終端 {YB} / pull/ {len(os.listdir("pull"))} files')
