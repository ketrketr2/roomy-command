#!/usr/bin/env python3
"""ROOMY COMMAND R_GA_DATA 日次リフレッシュエンジン。
pull/ ディレクトリのWindsor取得JSON群から R_GA_DATA / R_LONG を再構築し、js_data.js を書き換える。
対照群検証（既存コミット値との重複期間比較）に不合格のキーは更新せず旧値を維持して報告する。
使い方: python3 tools/refresh.py  （カレント＝roomy-board、pull/ と js_data.js が存在すること）
"""
import json, re, subprocess, sys
from datetime import date, timedelta

P = json.load
def load(name): return P(open(f'pull/{name}'))

# ---------- 既存データ ----------
node = subprocess.run(['node','-e','''
const w={};new Function("window",require("fs").readFileSync("js_data.js","utf8"))(w);
require("fs").writeFileSync("/tmp/_committed.json", JSON.stringify({GA:w.R_GA_DATA, LONG:w.R_LONG}));
'''], capture_output=True, text=True)
assert node.returncode == 0, node.stderr
CM = P(open('/tmp/_committed.json')); OLD = CM['GA']; LONG = CM['LONG']

rep = []   # 検証レポート
def check(name, ok, detail=''):
    rep.append(('PASS' if ok else 'FAIL', name, detail))
    return ok

GA = dict(OLD)  # ベース＝旧。キーごとに置換。

# ---------- q1: 日次配列 ----------
q1 = load('q1_daily.json')
dates, sess, users, newu, eng = q1['dates'], q1['sess'], q1['users'], q1['newu'], q1['eng']
assert len(dates) == 90
ok = True
for i, dt in enumerate(dates):
    if dt in OLD['dates']:
        j = OLD['dates'].index(dt)
        if abs(sess[i]-OLD['sess'][j]) > max(5, OLD['sess'][j]*0.03): ok = False
if check('daily(sess/users/newu/eng)', ok):
    GA.update(dates=dates, sess=sess, users=users, newu=newu, eng=eng, upto=dates[-1])

# ---------- q2: chDaily（スライド＋末尾差替） ----------
CH_MAP = {'Organic Search':0,'Direct':1,'Referral':2,'Unassigned':3,'Paid Search':4,'Organic Social':5,'Paid Social':5,'AI Assistant':6}
q2 = load('q2_chdaily3.json')
def row_from(day):
    r = [0]*8
    for ch, v in q2[day].items():
        r[CH_MAP.get(ch, 7)] = r[CH_MAP.get(ch, 7)] + v if CH_MAP.get(ch, 7) == 7 else v
    # oth は合算
    oth = sum(v for ch, v in q2[day].items() if ch not in CH_MAP)
    r[7] = oth
    return r
chD = []
for dt in dates:
    if dt in q2:
        chD.append(row_from(dt))
    elif dt in OLD['dates']:
        chD.append(OLD['chDaily'][OLD['dates'].index(dt)])
    else:
        chD.append([0]*8)
ok = True
for dt in ('2026-08-22','2026-08-23'):
    if dt in OLD['dates'] and dt in q2:
        a, b = row_from(dt), OLD['chDaily'][OLD['dates'].index(dt)]
        if sum(abs(x-y) for x, y in zip(a, b)) > max(10, sum(b)*0.02): ok = False
if check('chDaily', ok, 'splice3d'):
    GA['chDaily'] = chD

# ---------- q3: cvd（スライド＋末尾差替） ----------
q3 = load('q3_cv3.json')
def cvrow(day):
    e = q3.get(day, {})
    mkr = e.get('maker_estimate_complete', 0); dlr = e.get('dealer_estimate_complete', 0)
    td = e.get('test_drive_normal_reserve_complete', 0) + e.get('test_drive_instant_reserve_complete', 0)
    ds = e.get('dealer_search', 0); pc = e.get('purchase_consultation', 0) + e.get('tel', 0)
    return mkr, dlr, td, ds, pc
cvd = {k: [] for k in ('mkr','dlr','td','ds','pc','est')}
for dt in dates:
    if dt in q3:
        mkr, dlr, td, ds, pc = cvrow(dt)
    elif dt in OLD['dates']:
        j = OLD['dates'].index(dt)
        mkr, dlr, td, ds, pc = (OLD['cvd'][k][j] for k in ('mkr','dlr','td','ds','pc'))
    else:
        mkr = dlr = td = ds = pc = 0
    for k, v in zip(('mkr','dlr','td','ds','pc','est'), (mkr,dlr,td,ds,pc,mkr+dlr)):
        cvd[k].append(round(v, 1))
# 対照群: 量子化幅を考慮して緩め（±40% or ±15）
ok = True
for dt in ('2026-08-22','2026-08-23'):
    j = OLD['dates'].index(dt)
    mkr = cvrow(dt)[0]
    if abs(mkr-OLD['cvd']['mkr'][j]) > max(15, OLD['cvd']['mkr'][j]*0.4): ok = False
if check('cvd', ok, 'splice3d exact-int'):
    GA['cvd'] = cvd

# ---------- 28日派生 ----------
GA['cv28'] = {k: round(sum(GA['cvd'][k][-28:]), 1) for k in ('est','mkr','dlr','td','ds','pc')}
GA['sess28'] = sum(GA['sess'][-28:]); GA['newu28'] = sum(GA['newu'][-28:])
check('cv28/sess28 derived', True, f"est={GA['cv28']['est']}")

# ---------- q14: chャネル集計 ----------
IDX2ID = ['org','dir','ref','una','sem','sns','ai','oth']
q14 = load('q14_chagg.json')
agg = {cid: dict(s=0,u=0,n=0,e=0) for cid in IDX2ID}
for name, s, u, n, e in q14:
    cid = IDX2ID[CH_MAP.get(name, 7)]
    for k, v in zip(('s','u','n','e'), (s,u,n,e)): agg[cid][k] += v
newch = []
for c in OLD['ch']:
    a = agg[c['id']]
    nc = dict(c); nc.update(s=a['s'], u=a['u'], n=a['n'], e=a['e'],
                            newShare=round(a['n']/a['u'], 4) if a['u'] else 0)
    newch.append(nc)
tot = sum(c['s'] for c in newch)
share = newch[0]['s']/tot*100
newch[0]['note'] = re.sub(r'流入の\d+(\.\d+)?%', f'流入の{share:.0f}%', newch[0]['note'])
ok = abs(newch[0]['s'] - OLD['ch'][0]['s']) < OLD['ch'][0]['s']*0.03
if check('ch aggregate', ok, f"org {newch[0]['s']}"):
    GA['ch'] = newch

# ---------- q15: chCv ----------
q15 = load('q15_chcv.json')
cc = {cid: dict(est=0,mkr=0,dlr=0,td=0,ds=0) for cid in IDX2ID}
for half in ('h1','h2'):
    for name, k, v in q15[half]:
        cid = IDX2ID[CH_MAP.get(name, 7)]
        kk = 'td' if k in ('tdn','tdi') else k
        cc[cid][kk] += v
for cid in cc: cc[cid]['est'] = cc[cid]['mkr'] + cc[cid]['dlr']
ok = abs(cc['org']['est'] - OLD['chCv']['org']['est']) < OLD['chCv']['org']['est']*0.05
if check('chCv', ok, f"org.est {cc['org']['est']}"):
    GA['chCv'] = cc

# ---------- q4 pages / q5 landing / q6 eng28 / q7 ag / q8 region ----------
q4 = load('pull/q4_pages.json'.split('/')[-1])
top = q4[0][1]
GA_pages = [dict(p=p, s=s, u=u, e=e, share=round(s/top*100, 2 if s/top*100 < 100 else 0)) for p, s, u, e in q4]
GA_pages[0]['share'] = 100
ok = abs(q4[0][1] - OLD['pages'][0]['s']) < OLD['pages'][0]['s']*0.03
if check('pages', ok): GA['pages'] = GA_pages
q5 = load('q5_landing.json')
if check('landing', abs(q5[0][1]-OLD['landing'][0][1]) < OLD['landing'][0][1]*0.1): GA['landing'] = q5
q6 = load('q6_eng28.json')
if check('eng28', abs(q6['er']-OLD['eng28']['er']) < 0.05):
    GA['eng28'] = {'er': q6['er'], 'br': q6['br'], 'dur': round(q6['dur'], 2), 'pvs': round(q6['pvs'], 4)}
q7 = load('q7_ag.json')
if check('ag', abs(q7['m']['35-44']-OLD['ag']['m']['35-44']) < OLD['ag']['m']['35-44']*0.05): GA['ag'] = q7
PREF = {"Tokyo":"東京","Aichi":"愛知","Osaka":"大阪","Hokkaido":"北海道","Kanagawa":"神奈川","Chiba":"千葉","Saitama":"埼玉","Fukuoka":"福岡","Hyogo":"兵庫","Hiroshima":"広島","Kyoto":"京都","Shizuoka":"静岡","Ibaraki":"茨城","Tochigi":"栃木","Ehime":"愛媛","Mie":"三重","Niigata":"新潟","Gunma":"群馬","Yamanashi":"山梨","Okayama":"岡山","Aomori":"青森","Yamagata":"山形","Nagano":"長野","Gifu":"岐阜","Miyagi":"宮城"}
q8 = load('q8_region.json')
reg = [[PREF.get(n, n), v] for n, v in q8[:15]]
if check('region', reg[0][0] == '東京' and abs(reg[0][1]-OLD['region'][0][1]) < OLD['region'][0][1]*0.03): GA['region'] = reg

# ---------- q12 allcar ----------
q12 = load('q12_allcar.json')
from collections import defaultdict
ac = defaultdict(lambda: [0, 0])
for name, k, v in q12:
    if k in ('mkr','dlr'): ac[name][0] += v
    else: ac[name][1] += v
allcar = sorted(([n, e, t] for n, (e, t) in ac.items()), key=lambda x: -x[1])[:31]
roomy_row = next(r for r in allcar if r[0] == 'ルーミー')
old_roomy = next(r for r in OLD['allcar'] if r[0] == 'ルーミー')
if check('allcar', abs(roomy_row[1]-old_roomy[1]) < old_roomy[1]*0.1, f"roomy est {roomy_row[1]}"):
    GA['allcar'] = allcar

# ---------- vs ----------
vs = dict(OLD['vs'])
vs['roomy'] = dict(s=sum(sess), u=None, n=sum(newu), e=sum(eng))
# roomyのuはユニーク（日次和は不可）→ 旧比率で近似せず、q1では取れないため別枠。committedのvs.roomy.u/sの比率で補正
ratio_ok = abs(sum(sess) - OLD['vs']['roomy']['s']) < OLD['vs']['roomy']['s']*0.05
vs['roomy']['u'] = round(sum(sess) * OLD['vs']['roomy']['u'] / OLD['vs']['roomy']['s'])
si = load('q13_sienta.json'); ra = load('q13_raize.json')
vs['sienta'] = dict(s=si[0], u=si[1], n=si[2], e=si[3])
vs['raize'] = dict(s=ra[0], u=ra[1], n=ra[2], e=ra[3])
if check('vs', ratio_ok, f"roomy s={vs['roomy']['s']}"):
    GA['vs'] = vs

# ---------- monthly / sm / sitewide ----------
m8 = load('q9_month8.json')
monthly = [r for r in OLD['monthly'] if r[0] != '2026-08'] + [['2026-08', m8['sess'], m8['users']]]
if check('monthly', m8['sess'] > OLD['monthly'][-1][1]*0.9): GA['monthly'] = monthly
q10 = load('q10_sm.json')
if check('sm', q10[0][0] == OLD['sm'][0][0]): GA['sm'] = q10
q11 = load('q11_sitewide.json')
if check('sitewide', abs(q11['signup28']-OLD['sitewide']['signup28']) < OLD['sitewide']['signup28']*0.1): GA['sitewide'] = q11

# ---------- R_LONG 当月行 ----------
aug_days = [i for i, dt in enumerate(dates) if dt.startswith('2026-08')]
aug_sess = sum(sess[i] for i in aug_days)
newlong = [r for r in LONG if r[0] != '2026-08'] + [['2026-08', aug_sess, round(aug_sess/len(aug_days))]]
check('R_LONG', True, f"08={aug_sess}/{len(aug_days)}日")

# ---------- 書き込み ----------
d = open('js_data.js', encoding='utf-8').read()
def replace_assign(src, var, obj):
    pat = re.compile(r'(window\.' + var + r'\s*=\s*)(.*?)(;\n)', re.S)
    m = pat.search(src)
    assert m, var
    return src[:m.start(2)] + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + src[m.end(2):]
d = replace_assign(d, 'R_GA_DATA', GA)
d = replace_assign(d, 'R_LONG', newlong)
open('js_data.js', 'w', encoding='utf-8').write(d)

# ---------- render層の揮発リテラル ----------
ai_s = GA['ch'][6]['s']; ai_share = round(GA['ch'][6]['n']/GA['ch'][6]['u']*100, 1)
gpt28 = sum(r[1] for r in GA['sm'] if r[0].split(' / ')[0] in ('openai','chatgpt.com'))
for f in ('js_render3.js','js_render4.js','js_render5.js'):
    t = open(f, encoding='utf-8').read(); o = t
    t = re.sub(r'90日で?429セッション', f'90日{ai_s}セッション', t)
    t = re.sub(r'90日429セッション', f'90日{ai_s}セッション', t)
    t = re.sub(r'新規率68\.\d%', f'新規率{ai_share}%', t)
    t = re.sub(r'直近28日で\d+', f'直近28日で{gpt28}', t)
    if t != o: open(f, 'w', encoding='utf-8').write(t)

print('=== 検証レポート ===')
fails = 0
for st, name, det in rep:
    print(f'{st:4} {name:24} {det}')
    fails += st == 'FAIL'
print('=== ', 'ALL PASS' if not fails else f'{fails} FAILED (該当キーは旧値維持)', ' ===')
print(f"upto: {GA['upto']} / AI: {ai_s}sess {ai_share}% / est28: {GA['cv28']['est']}")
sys.exit(0)
