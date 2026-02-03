# 契約審査サポートアプリ_v2

## 概要
- Streamlit製の契約審査支援。`Home.py` から `pages/` を起動。
- 契約書アップロード→条文抽出→ナレッジ紐付け→LLM審査→CSV出力。

## 主な機能
- 契約審査: 条文抽出、ナレッジ照合、審査結果表示/CSV。
- ナレッジ管理: CRUD、一覧編集、一括更新。
- 管理者制御: `KNOWLEDGE_ADMIN_PASSWORD` で編集権限。

## ユーザーができること
- 契約審査: `.docx/.pdf` をアップロードし、条文抽出→審査結果を確認。
- 懸念点の把握: 条項ごとの指摘有無、懸念あり条項の自動展開、未紐付けナレッジの確認。
- 審査結果の出力: 契約基本情報+条項結果をCSVでダウンロード。
- 審査チャット: 審査結果に関するチャットで追加確認。
- ナレッジ運用: 契約種別/キーワードで検索、フォーム/一覧で編集、Excelダウンロード。

## 主要構成
- `Home.py` / `pages/`: UI
- `services/`: 文書抽出/認証/LLM周辺
- `api/`: Cosmos/LLM連携のAPI
- `azure_/`: Azure接続
- `configs/knowledge_llm/`: LLM出力/ナレッジスキーマ
- `docs/`: 仕様/運用

## セットアップ
- 仮想環境: `python -m venv .venv`
- 有効化: Windows `.venv\Scripts\activate` / Linux/Mac `source .venv/bin/activate`
- 依存: `pip install -r requirements.txt`

## 起動
- `streamlit run Home.py`

## 環境変数
- `OPENAI_API_KEY`
- `OPENAI_API_BASE`
- `OPENAI_API_VERSION`
- `COSMOSDB_CORE_ENDPOINT`
- `COSMOSDB_CORE_API_KEY`
- `DOCUMENT_INTELLIGENCE_ENDPOINT`
- `DOCUMENT_INTELLIGENCE_API_KEY`
- `KNOWLEDGE_ADMIN_PASSWORD`

## テスト
- `pytest`

## ドキュメント
- `docs/overview.md`
- `docs/ui.md`
- `docs/api.md`
- `docs/PROMPT_FLOW_STATE_SPEC.md`
- `docs/プロンプト説明.md`
- `docs/infographic_feature_brief.md`

---

## 機能説明（情報共有用）

![infographic.jpg](infographic-20260203\infographic-20260203.png)

---

![text](infographic-20260203\system_summary.md)