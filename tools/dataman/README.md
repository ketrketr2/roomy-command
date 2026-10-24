# dataman-digest（データマンへのボード資料の受け渡し）

ID/PW付きボード6枚の中身を、データマン（Mac mini のSlackアシスタント）が読める資料にして、毎朝渡す仕組み。

| 段 | 場所 | 中身 |
|---|---|---|
| 復号 | GitHub Actions（このリポジトリ） | `decrypt_boards.py`。鍵素材は Secrets の `ROOMY_GATE_KEY` のみ。平文はジョブ内だけで、最後に消す |
| 描画・書き出し | 同上 | `extract_roomy_aio.js` / `extract_boards.js`。全画面を描画し、表示された文字・表・図の元データを書き出す |
| 資料化 | 同上 | `build_digest.py`。ボードごとに README・画面本文・元データ（data_*.json）・台帳 `_boards.md`・`_manifest.json` |
| 封 | 同上 | `pack_and_seal.py`。データマンの公開鍵（toyota-geo-board/config/dataman_recipient.pub）で封をして `dataman-sealed` ブランチへ |
| 開封 | Mac mini | toyota-geo-board/tools/dataman_open_sealed.py（boards_sync.py の最後に自動実行）。秘密鍵は Mac mini の中だけ |

- 実行: 毎朝 09:15 JST と予備 12:15 JST。`tools/dataman/**` を変更して push しても走る
- 失敗の見え方: Actions が赤になる／Mac mini の `kb/boards/_取り込み状況.md` に「失敗」「古い」と出て、けんけんさんにDMが飛ぶ
- ボードを増やすとき: `decrypt_boards.py` の `PAGES` と `build_digest.py` の `BOARDS`、`extract_boards.js` の `CFG` に1行ずつ足す
