# 画面仕様
- Home: タイトル/バージョン表示、審査・ナレッジ管理へのリンク。

## 契約審査 (`pages/10_examination.py`)
- 入力: `.docx/.pdf` アップロード→`services/document_input.extract_text_from_document` でタイトル/前文/条項抽出（Document Intelligence OCR+LLM分割補正）。
- 審査: LLMで条項とナレッジをマッチング (`api.async_llm_service.amatching_clause_and_knowledge`)、非同期で審査/要約 (`api.examination_api.examination_api`)。モデル選択可。
- 状態: 条項ごとに未審査/懸念有無を表示、懸念ありを自動展開。ナレッジ未紐付けリストを別枠表示。
- 出力: 審査結果CSV（契約基本情報+条項結果、BOM付き）、ナレッジCSVダウンロード。

## ナレッジ管理フォーム (`pages/20_knowledge.py`)
- 検索/フィルタ: 契約種別・キーワードで絞り込み、ページネーション。
- CRUD: 管理者のみ保存/削除/新規作成可。ナレッジ番号は `get_max_knowledge_number` で自動採番。保存時に一覧・フィルタをリロード。
- 項目: 契約種別/対象条項/タイトル/審査観点/対応策/条項サンプル、ステータス（record_status, approval_status）。

## ナレッジ一覧編集 (`pages/21_knowledge_datalist.py`)
- 表示: DataFrame化したナレッジをData Editorで編集、Excelダウンロード。
- 一括更新: 管理者のみ有効。各行を `api.KnowledgeAPI.save_knowledge` で保存、進捗バー表示。
- 編集不可: `id`、`knowledge_number` は固定。契約種別/ステータスはセレクト。新規追加はフォーム画面で実施。
