# JR東日本リアルタイム列車位置表示システム

ODPTからリアルタイム列車データを取得し、GTFS時刻表で位置を計算、SSEで配信するシステム。

## 🎯 機能

- ODPTから3秒ごとにリアルタイム列車データ取得
- GTFS時刻表との高精度マッチング（スコアリング方式）
- 駅間位置の補間計算
- SSEによるリアルタイム配信
- React Canvasでの60fps描画
- 線路データの可視化（国土数値情報）

## 📦 構成

### バックエンド（Python FastAPI）
- `backend/main.py` - FastAPIアプリケーション
- `backend/gtfs_loader.py` - GTFSデータローダー
- `backend/trip_matcher.py` - trip_idマッチングエンジン
- `backend/interpolator.py` - 位置補間計算
- `backend/odpt_client.py` - ODPT APIクライアント
- `backend/station_mapper.py` - 駅マッピング
- `backend/shapefile_loader.py` - Shapefileローダー

### フロントエンド（React + Vite）
- `frontend/src/App.jsx` - メインコンポーネント

## 🚀 起動方法

### 1. 環境準備

**ODPT APIキーの取得:**
1. https://developer.odpt.org/ でアカウント作成
2. APIキーを取得

**環境変数設定:**
```bash
export ODPT_API_KEY="your_api_key_here"
```

### 2. バックエンド起動

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

起動ログ例:
```
============================================================
JR East Real-time Train Tracking System
============================================================

[Startup] Loading GTFS data...
[GTFSLoader] Loaded: 1234 stops, 56 routes, 18567 trips
[Startup] Loading Shapefile data...
[Shapefile] Loaded 5678 stations
[Shapefile] Loaded 234 rail paths
[Startup] Fetching ODPT stations...
[Mapper] Creating station mapping...
[Mapper] Mapped 123/150 stations (300m), 12 (500m), 0 overrides
[TripMatcher] Building train number index...
[TripMatcher] Indexed 456 unique train numbers
[Startup] Starting polling loop...
============================================================
Startup complete! Server is ready.
============================================================

[poll_loop] Seq 1 | Fetched 34 trains | Matched: 32/34 | Failed: {'no-candidate': 2}
```

### 3. フロントエンド起動

別のターミナルで:
```bash
cd frontend
npm install
npm run dev
```

ブラウザで http://localhost:3000 を開く

## 📊 エンドポイント

- `GET /api/trains/stream` - SSEストリーム（リアルタイムデータ）
- `GET /api/health` - ヘルスチェック
- `GET /debug/last-snapshot` - デバッグ用（最新スナップショット）

## 🔧 設定

### 対象路線の追加

`backend/config.py` の `INITIAL_RAILWAYS` を編集:

```python
INITIAL_RAILWAYS = [
    "odpt.Railway:JR-East.ChuoRapid",
    "odpt.Railway:JR-East.Chuo",
    "odpt.Railway:JR-East.Yamanote",
    "odpt.Railway:JR-East.Sobu",  # 追加
]
```

### 駅マッピングの手動設定

`backend/data/config/overrides.stations.json` に追加:

```json
{
  "odpt.Station:JR-East.Chuo.Shinjuku": "1001",
  "odpt.Station:JR-East.Yamanote.Shinjuku": "1001"
}
```

## 📁 データファイル

### 既存リソース

- `train_json/` - GTFSデータ（stops, routes, trips, stop_times）
- `N02-05_GML/` - 国土数値情報（駅・線路Shapefile）

### 生成ファイル

なし（すべてメモリ上で処理）

## 🐛 トラブルシューティング

### マッチング成功率が低い（<80%）

1. ログで `no-candidate` を確認
   - 列車番号抽出ロジックを確認
   - GTFSデータの trip_id 形式を確認

2. `low-score` の場合
   - 時刻が大幅にずれていないか確認
   - 駅マッピングが正しいか確認

### 駅マッピングエラー

1. overrides に手動追加
2. Shapefileデータの精度を確認

### ODPT API エラー

- 429エラー: 指数バックオフで自動リトライ
- 認証エラー: APIキーを確認

## 📝 ログレベル

起動時:
- データ件数、マッピング結果、インデックス構築

ポーリング毎（3秒）:
- 取得数、マッチ成功/失敗内訳

## 🎨 UI操作

- **理論進捗補間チェックボックス**: サーバー座標 or 理論進捗補間の切り替え
- **列車の色**:
  - 緑: 定時
  - オレンジ: 1分以上遅延
  - 赤: 5分以上遅延

## 📄 ライセンス

このプロジェクトはMITライセンスです。

## 📚 参考資料

- ODPT API: https://developer.odpt.org/
- GTFS仕様: https://gtfs.org/
- 国土数値情報: https://nlftp.mlit.go.jp/
