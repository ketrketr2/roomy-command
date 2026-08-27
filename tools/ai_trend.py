#!/usr/bin/env python3
"""GEOボード（toyota-geo-board）の日次スナップショットから車種別AI言及トレンドを抽出し
pull/ai_trend.json に書き出す。GitHub Actions から毎朝呼ばれる（失敗しても本体は止めない）。
使い方: python3 tools/ai_trend.py [geoリポジトリのパス（省略時 ../_geo に clone）]
"""
import json, glob, os, subprocess, sys
path = sys.argv[1] if len(sys.argv)>1 else '../_geo'
if not os.path.isdir(os.path.join(path,'data','snapshots')):
    subprocess.run(['git','clone','--depth','1','https://github.com/ketrketr2/toyota-geo-board',path],check=True)
CARS={'roomy':'ルーミー','solio':'ソリオ','fit':'フィット','nbox':'N-BOX','thor':'トール','sienta':'シエンタ','freed':'フリード'}
out={}
for f in sorted(glob.glob(os.path.join(path,'data','snapshots','*.json'))):
    try: d=json.load(open(f))
    except Exception: continue
    cells=d.get('cells') or []
    if not cells: continue
    row={'cells':len(cells)}
    for k,name in CARS.items():
        row[k]=sum(1 for c in cells if name in (c.get('answer') or ''))
    out[d['date']]=row
days=sorted(out)
# 回答未保存期（全車ゼロ）の先頭日をトリム
while days and sum(out[days[0]][k] for k in CARS)==0: days.pop(0)
if len(days)<30: sys.exit(f'snapshots too few: {len(days)}')
trend={'dates':days,'cells':[out[d]['cells'] for d in days]}
for k in CARS: trend[k]=[out[d][k] for d in days]
os.makedirs('pull',exist_ok=True)
json.dump({'aiTrend':trend,'asof':days[-1]},open('pull/ai_trend.json','w'),ensure_ascii=False)
print(f'ai_trend: {len(days)} days through {days[-1]} (roomy last7 avg {sum(trend["roomy"][-7:])/7:.1f})')
