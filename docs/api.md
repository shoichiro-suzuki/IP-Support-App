# API/サービス概要
- LLMは `azure_/openai_service.py` 経由でAzure OpenAIに接続。埋め込み`text-embedding-3-small`、各種GPT-4.1/5モデル呼び出しを提供。
- Cosmos DBクライアントは `azure_/cosmosdb.py`（`get_cosmosdb_client` キャッシュ）。基本CRUDとベクトル検索`search_similar_vectors`を保持。

## api/contract_api.py
- `search_similar_clauses(text, top_k)`: clause_entry の `clause_vector` へ埋め込み検索。
- `get_knowledge_entries(contract_type)`: 契約種別一致or汎用を取得。
- `get_contract_types/get_approved_contracts/get_draft_contracts/get_contract_by_id`: master系の読取。
- `upsert_contract/upsert_clause_entry`: 追記更新。
- `export_examination_result_to_csv(...)`: 審査結果をCSV文字列化（契約基本情報+条項結果、状態をマップ）。

## api/knowledge_api.py
- `get_knowledge_list(contract_type?, search_text?)`: フィルタ付き取得。
- `get_max_knowledge_number()`: 連番発行用に最大番号取得。
- `save_knowledge(data)`: id付与/更新日時管理後にupsert。`created_at` 引き継ぎ。
- `delete_knowledge(data)`: knowledge_numberをPartition Keyとして削除。
- 契約種別取得は `ContractAPI` を利用。

## api/examination_api.py
- `examination_api(...)`: 条項とナレッジの対応を受け取り、非同期で審査→複数ナレッジの指摘がある条項を要約。`api.async_llm_service` の `run_batch_reviews/run_batch_summaries` を利用。`DEBUG` 環境変数がある場合は `Examination_data_sample.py` に追記。
- `search_similar_clauses(...)`: `ContractAPI.search_similar_clauses` を呼び、条項番号ごとに類似条項をまとめる。

## services
- `document_input.extract_text_from_document(path)`: `.docx` はSDT含むテキスト抽出（`lxml.etree` 使用）、`.pdf` は Document Intelligence OCR。LLM結果が文字列以外なら失敗扱い。条文の結合指示を取得し、署名セクション/別紙を切り出した結果を返す。
- 詳細: `docs/document_input.md`
- `admin_auth`: `KNOWLEDGE_ADMIN_PASSWORD` で管理者判定。StreamlitサイドバーのログインUIを提供。
