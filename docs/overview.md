# 概要
- Streamlit製「契約審査サポートアプリ」。`Home.py` を起点に `pages/` へ遷移。
- 主機能: 契約書アップロード→条文抽出→ナレッジ紐付け→LLM審査、結果CSV/ナレッジCSVダウンロード。
- ナレッジ管理: 管理者パスワード `KNOWLEDGE_ADMIN_PASSWORD` でCRUD/一括更新を制御。
- 外部サービス: Azure OpenAI（LLM/埋め込み）、Azure Cosmos DB（契約/ナレッジ）、Azure Document Intelligence（PDF OCR）。
- データ: ナレッジ/条文はCosmos DB管理（初期サンプルファイルは削除済み）。
- 環境変数（例）: `OPENAI_API_KEY`, `OPENAI_API_BASE`, `OPENAI_API_VERSION`, `COSMOSDB_CORE_ENDPOINT`, `COSMOSDB_CORE_API_KEY`, `DOCUMENT_INTELLIGENCE_ENDPOINT`, `DOCUMENT_INTELLIGENCE_API_KEY`, `KNOWLEDGE_ADMIN_PASSWORD`。
- セットアップ/起動: `README.md` 参照。
