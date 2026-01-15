# 実装計画書
- 対象: `services/document_input.py`
- 目的: 境界監査の共通化と末尾分割精度向上
- 範囲: テキスト抽出/PDF整形/条文分割/末尾分割/LLM監査

## 前提
- 既存OCRは Document Intelligence を利用
- 既存LLM接続は `azure_.openai_service` を利用
- 境界監査用のプロンプトは新規作成
- スクリプト単体で完結し、外部I/Fは変更最小

## 変更方針
### 1. PDF抽出の変更
- `result.content` → `result.paragraphs.content` を使用
- paragraphsを1行として結合し、OCR崩れの過分割を回避
- サンプル: `tests/ocr_result_test_加工済.json`

### 2. 境界監査クラスの分離
- 役割: 候補境界挿入 + 行番号付与 + LLM監査
- 入力: 任意テキストブロック（全文/一部）
- 出力: 境界確定済みセクション
- 再利用: 末尾塊/条文境界の補正

### 3. 末尾分割ロジック
- ルールで `SIG_CAND_n` / `ATTACH_CAND_n` を挿入
- 行番号付きコンテキストをLLMに渡す
- LLMは境界の accept/move/remove を返却
- `final_sections` に基づき抽出
- JSONパース失敗時は1回リトライ

### 4. 条文分割補正（任意）
- `第X条`/`Article X` 検出後、境界監査クラスで再評価
- 誤分割が多い場合のみ適用

### 5. OCR改行欠落の扱い
- 改行欠落リスクはOCRモデル精査で対応する方針

## 影響範囲
- `services/document_input.py`
- `docs/document_input.md`
- テストデータ: `tests/ocr_result_test_加工済.json`

## 受け入れ基準
- PDF抽出が `paragraphs.content` ベースになる
- 末尾分割で `clause_last/signature/attachments` が安定
- LLM出力はJSONのみ、境界は accept/move/remove のみ
- 条文境界にも同クラスが適用可能な設計
