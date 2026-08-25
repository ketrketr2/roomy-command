# ROOMY COMMAND 日次データ更新手順（自動セッション用）

毎朝、GA4実測（Windsor.ai MCP・property 324699885）で R_GA_DATA を前日まで更新し、再暗号化してデプロイする。
鍵素材（ROOMY_GATE_KEY="id:pw"）は定例タスクのプロンプトに記載。**リポジトリには絶対に書かない。**

## 手順
1. `git clone --depth 1 https://github.com/ketrketr2/roomy-command && cd roomy-command`
2. `pip install cryptography --break-system-packages && npm install playwright --no-save`
3. `ROOMY_GATE_KEY=... python3 tools/recover.py` → js_data.js 等が展開される
4. `mkdir pull` → 下記のWindsorクエリを実行し、結果を pull/ に保存（**ファイル形式は refresh.py 冒頭の load() 呼び出しと同じ構造**。過去分は js_data.js に入っているので、日次は q1/q2/q3 の「直近3日ぶんの再取得」と各集計クエリの再取得のみ）
5. `python3 tools/refresh.py` → 検証レポートが ALL PASS であること（FAILキーは旧値維持される。FAILが3つ以上なら中断して報告）
6. `python3 tools/build.py` → `node tools/verify.js`（14セクション描画・エラーなし確認）
7. `ROOMY_GATE_KEY=... python3 tools/encrypt.py` → index_new.html
8. index_new.html を index.html という名前で /mnt/user-data/outputs/ にコピーし、Chrome MCP（Mac mini deviceId cddb1e00-101d-488b-9a2a-21c2f0aba9eb のみ・MacBook Air 5250eb1c は絶対操作禁止）で https://github.com/ketrketr2/roomy-command/upload/main にアップロード→コミット
9. 60秒後、本番 https://ketrketr2.github.io/roomy-command/ でログイン（保存済み資格情報）→戦況ダッシュのヘッダー期間終端が前日日付であることを確認→タブ全閉じ

## Windsorクエリ仕様（connector: googleanalytics4 / accounts: "324699885"）
共通: W90 = 前日を終端とする90日間（date_from=前日-89日, date_to=前日）、W28 = 同28日間、L3 = 直近3日
- q1_daily.json: W90 [date,sessions,totalusers,newusers,engaged_sessions] filter page_path contains /roomy/ → {"dates":[...],"sess":[...],"users":[...],"newu":[...],"eng":[...]}（90要素）
- q2_chdaily3.json: L3 [date,session_default_channel_group,sessions] 同filter → {"日付":{"チャネル名":数,...},...}
- q3_cv3.json: L3 [date,event_name,event_count] filter customevent_car_model contains ルーミー AND event_name in [maker_estimate_complete,dealer_estimate_complete,dealer_search,test_drive_normal_reserve_complete,test_drive_instant_reserve_complete,purchase_consultation,tel] → {"日付":{"イベント名":数,...},...}
- q4_pages.json: W90 [page_path,sessions,totalusers,engaged_sessions] 同filter 上位15件 → [[p,s,u,e],...]
- q5_landing.json: W28 [landing_page,sessions,engaged_sessions] filter landing_page contains /roomy 上位10件 → [[p,s,e],...]
- q6_eng28.json: W28 [engagement_rate,bounce_rate,average_session_duration,screen_page_views_per_session] filter page_path contains /roomy/ → {"er":,"br":,"dur":,"pvs":}
- q7_ag.json: W90 [age,gender,sessions] 同filter → {"m":{6年代},"f":{6年代},"unknown":判明外合計}
- q8_region.json: W90 [region,sessions] 同filter 上位15件（英名のまま）→ [[region,sess],...]
- q9_month8.json: 当月1日〜前日 [sessions,totalusers] 同filter → {"sess":,"users":}（キー名は q9_month8 固定）
- q10_sm.json: W28 [source,medium,sessions,engaged_sessions] 同filter 上位20件 → [["source / medium",sess,eng],...]
- q11_sitewide.json: W28 [event_name,event_count] filter event_name in [sign_up,estimate_simulation_complete]（サイト全体・pageフィルタなし）→ {"signup28":,"estAll28":}
- q12_allcar.json: W28 [customevent_car_model,event_name,event_count] filter event_name in [maker_estimate_complete,dealer_estimate_complete,test_drive_normal_reserve_complete,test_drive_instant_reserve_complete] → [[車種名(先頭の;を除去),"mkr"|"dlr"|"tdn"|"tdi",数],...]
- q13_sienta.json / q13_raize.json: W90 [sessions,totalusers,newusers,engaged_sessions] filter page_path contains /sienta/ (/raize/) → [s,u,n,e]
- q14_chagg.json: W90 [session_default_channel_group,sessions,totalusers,newusers,engaged_sessions] filter page_path contains /roomy/ → [[チャネル名,s,u,n,e],...]
- q15_chcv.json: q3と同じfilter（tel/purchase_consultation除く5イベント）で W90 [session_default_channel_group,event_name,event_count]。90日1発はタイムアウトするため**45日×2分割**し {"h1":[[チャネル名,"mkr"|"dlr"|"ds"|"tdn"|"tdi",数],...],"h2":[...]} で保存

## 注意
- Windsorがタイムアウトしたら期間分割で再試行（q15参照）。データが0行のときは対照群（前日分を同クエリで再取得）で手法の正常性を確認してから「未反映」と報告。デモ値・推定値は絶対に書かない。
- refresh.py の検証は js_data.js の既存値との重複期間比較。定義ズレはFAILになるので、クエリ仕様を勝手に変えないこと。
