# ドキュメント管理ガイド

## 目的
- docs配下に設計/仕様/運用情報を集約し、コード変更と同期させる
- 作業前後の参照・更新ルールを明示する

## ドキュメント配置
- docs/ : 設計、API仕様、データ定義、運用メモをここに追加（無ければ作成）
- AGENTS.md : エージェント運用ルール
- プロンプト説明.md : プロンプト運用メモ（更新時はdocsにも要点を残す）

## 更新義務
- 作業前: 関連メモを確認。無い場合は docs/<topic>.md を作成し前提・スコープを箇条書き化。
- 作業後: 仕様/I-O/フロー/依存/環境変数の変更点を更新。機密ファイル追加時は .gitignore を調整。
- データ/ナレッジ変更: 定義、作成手順、バージョン、配置パスを記録。
- リリース・運用変更: セットアップ手順、必要権限、ロールバック方法を追記。

## 参照・更新マトリクス
| 作業内容 | 参照 | 更新 |
|---|---|---|
| 画面・UI (Home.py, pages/) | 画面仕様メモ | 画面遷移/I-O/入力制約 |
| サービスロジック (services/, api/) | ユースケース/フロー | 入出力・例外・依存関係 |
| 外部連携 (azure_/...) | 接続設定・認証情報 | エンドポイント・必要ENV |
| データ/ナレッジ (CosmosDB: knowledge_entry, docs/review-ui-llm-support/knowledge_samples.json) | データモデル/更新手順 | バージョン・生成条件・スクリプト手順 |
| 環境/運用 | セットアップ・運用手順 | 手順更新・トラブルシュート |

※該当メモが無い場合は docs/ 以下に新規作成。

## 品質基準
- 正確性: コード/設定値と一致
- 最新性: 変更直後に反映し日付やバージョンを残す
- 簡潔性: 箇条書きで要点のみ
- 可視性: 参照先・担当・想定環境を明記
- 再現性: 手順/コマンド/必要権限を記載し再実行可能にする

## プロジェクト情報
```
契約審査サポートアプリ_v2/
├── Home.py
├── pages/              # Streamlit画面
├── services/           # ビジネスロジック
├── api/                # API関連
├── azure_/             # Azure OpenAI/Cosmos/Document Intelligence
├── pages/              # Streamlit画面
├── scripts/            # メンテ/データ操作（例: export_knowledge_samples.py）
├── docs/               # ドキュメント・ナレッジサンプル
├── tests/              # テスト
├── requirements.txt
├── AGENTS.md
└── プロンプト説明.md
```

## 技術スタックと環境変数
- 言語: Python 3.10+ / フレームワーク: Streamlit
- 外部サービス: Azure OpenAI, Azure Cosmos DB, Azure Document Intelligence
- 主要ライブラリ: openai, azure-ai-documentintelligence, azure-cosmos, pandas, langchain, streamlit
- 環境変数例:
```bash
OPENAI_API_KEY=...
OPENAI_API_BASE=...
OPENAI_API_VERSION=...
COSMOSDB_CORE_ENDPOINT=...
COSMOSDB_CORE_API_KEY=...
DOCUMENT_INTELLIGENCE_ENDPOINT=...
DOCUMENT_INTELLIGENCE_API_KEY=...
```
