# ROOMY COMMAND 日次データ更新（完全自動）

毎朝、GA4実測（Windsor.ai・property 324699885）で R_GA_DATA を前日まで更新し、再暗号化してデプロイする。
鍵素材（ROOMY_GATE_KEY="id:pw"）は**リポジトリに絶対に書かない。**

## 一次経路（人手ゼロ）: GitHub Actions
`.github/workflows/daily.yml` が毎朝 06:53 JST に自動実行する:
`tools/fetch_windsor.py`（Windsor REST・下記クエリ仕様）→ `tools/recover.py` → `tools/refresh.py`（対照群検証。FAIL≥3で中止）→ `tools/build.py` → `tools/verify.js`（14セクション描画確認）→ `tools/encrypt.py` → index.html をコミット → GitHub Pages 自動デプロイ。
必要シークレット（Settings > Secrets and variables > Actions）: `WINDSOR_API_KEY` / `ROOMY_GATE_KEY`。未登録の間は緑のまま何もしない。

## 二次経路（Actionsが動かなかった日の保険）: Claude定例セッション
スケジュールセッションは **git push も Chrome も使えない**（プロキシ制約・構造的）。次だけ行う:
1. `git clone --depth 1 https://github.com/ketrketr2/roomy-command` → 最新コミット日時を確認。前日データ反映済みなら**何もせず報告のみ**。
2. 未反映なら: `pip install cryptography --break-system-packages && npm install playwright --no-save` → `ROOMY_GATE_KEY=... python3 tools/recover.py` → Windsor **MCP** で下記クエリを実行し pull/ に保存 → `python3 tools/refresh.py`（ALL PASS確認。FAIL≥3なら中止して報告）→ `tools/build.py` → `PW_CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome node tools/verify.js` → `ROOMY_GATE_KEY=... python3 tools/encrypt.py` → index_new.html を **index.html にリネームして SendUserFile で届け**、「roomy-command 直下に手動アップロード」と明記。git push は試みない。

## Windsorクエリ仕様（connector: googleanalytics4 / accounts: "324699885"）
REST実装は tools/fetch_windsor.py（このMD と同一仕様）。MCP手動時も**保存形式を厳守**（refresh.py が読む）。
共通: W90 = 前日を終端とする90日間、W28 = 同28日間、L3 = 直近3日
- q1_daily.json: W90 [date,sessions,totalusers,newusers,engaged_sessions] filter page_path contains /roomy/ → {"dates":[...],"sess":[...],"users":[...],"newu":[...],"eng":[...]}（90要素）
- q2_chdaily3.json: L3 [date,session_default_channel_group,sessions] 同filter → {"日付":{"チャネル名":数,...},...}
- q3_cv3.json: L3 [date,event_name,event_count] filter customevent_car_model contains ルーミー AND event_name in [maker_estimate_complete,dealer_estimate_complete,dealer_search,test_drive_normal_reserve_complete,test_drive_instant_reserve_complete,purchase_consultation,tel] → {"日付":{"イベント名":数,...},...}
- q4_pages.json: W90 [page_path,sessions,totalusers,engaged_sessions] 同filter 上位15件 → [[p,s,u,e],...]
- q5_landing.json: W28 [landing_page,sessions,engaged_sessions] filter landing_page contains /roomy 上位10件 → [[p,s,e],...]
- q6_eng28.json: W28 [engagement_rate,bounce_rate,average_session_duration,screen_page_views_per_session] filter page_path contains /roomy/ → {"er":,"br":,"dur":,"pvs":}
- q7_ag.json: W90 [age,gender,sessions] 同filter → {"m":{6年代},"f":{6年代},"unknown":判明外合計}
- q8_region.json: W90 [region,sessions] 同filter (not set)除外 上位15件（英名のまま）→ [[region,sess],...]
- q9_month.json: 当月1日〜前日 [sessions,totalusers] 同filter → {"sess":,"users":}（旧名 q9_month8.json も読める）
- q10_sm.json: W28 [source,medium,sessions,engaged_sessions] 同filter 上位20件 → [["source / medium",sess,eng],...]
- q11_sitewide.json: W28 [event_name,event_count] filter event_name in [sign_up,estimate_simulation_complete]（サイト全体・pageフィルタなし）→ {"signup28":,"estAll28":}
- q12_allcar.json: W28 [customevent_car_model,event_name,event_count] filter event_name in [maker_estimate_complete,dealer_estimate_complete,test_drive_normal_reserve_complete,test_drive_instant_reserve_complete] → [[車種名(先頭の;を除去),"mkr"|"dlr"|"tdn"|"tdi",数],...]
- q13_sienta.json / q13_raize.json: W90 [sessions,totalusers,newusers,engaged_sessions] filter page_path contains /sienta/ (/raize/) → [s,u,n,e]
- q14_chagg.json: W90 [session_default_channel_group,sessions,totalusers,newusers,engaged_sessions] filter page_path contains /roomy/ → [[チャネル名,s,u,n,e],...]
- q15_chcv.json: q3と同じfilter（tel/purchase_consultation除く5イベント）で W90 [session_default_channel_group,event_name,event_count]。90日1発はタイムアウトするため**45日×2分割**し {"h1":[[チャネル名,"mkr"|"dlr"|"ds"|"tdn"|"tdi",数],...],"h2":[...]} で保存

## 注意
- Windsorがタイムアウトしたら期間分割で再試行（q15参照）。前日分が0行のときは対照群（一昨日を同クエリ）で手法の正常性を確認してから「未反映」と報告。デモ値・推定値は絶対に書かない。
- refresh.py の検証は js_data.js の既存値との重複期間比較。定義ズレはFAILになるので、クエリ仕様を勝手に変えないこと。
- 対話セッションからの手動デプロイは従来どおり Chrome MCP（Mac mini cddb1e00 のみ・MacBook Air 5250eb1c 絶対禁止）で https://github.com/ketrketr2/roomy-command/upload/main へ。

## v6追記（2026-08-27）
- 描画層は js_render6.js（第6層）を追加。build.py / recover.py / verify.js は対応済み。ビューは search（検索状況）を含む15画面。
- 毎朝の自動更新には tools/ai_trend.py（GEOボードのスナップショットから車種別AI言及トレンドを再抽出→ pull/ai_trend.json → refresh.py が R_V6.aiTrend に反映）が加わる。失敗しても本体更新は継続（前日までのトレンドを保持）。
- R_V6内の静的比較データ（carSess=車種別セッション28日 / ds28 / landing / regionCmp / trends=Googleトレンド / salesLong=自販連月次2023〜）は月1回の手動リフレッシュ対象。取得手順はこのリポジトリの経緯ドキュメント参照（Windsor REST同一キー・pytrends・自販連公表PDF）。
