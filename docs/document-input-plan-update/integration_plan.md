# 統合計画書
- 対象: `services/document_input.py` / `services/boundary_audit.py` / `pages/10_examination.py`
- 目的: UI/機能で新条文分割・末尾監査を安定利用
- 前提: OCRは Document Intelligence、LLMは `azure_.openai_service` を利用

## 現状の統合状態
- `pages/10_examination.py`: `extract_text_from_document` の `error` をサイドバー `st.error` 表示
- `pages/10_examination.py`: 全条文LLM監査を常時有効（UI選択なし）
- `pages/10_examination.py`: `signature_section`/`attachments` は session_state に保存のみ（UI表示なし）
- `pages/22_knowledge_llm.py`: `error` をUI表示せず、空文字扱い
- 末尾監査: `split_tail_sections` を使用
- 全条文境界のLLM監査: 既定で有効（UI選択なし）
- 実LLM監査テスト: `tests/test_document_input_full_split.py` に追加済み
- 条文境界監査テスト: `tests/test_clause_boundary_audit.py`
- 条文境界監査の実行スクリプト: `scripts/functional_test_clause_boundary_audit.py`

## 統合方針
- UI統合: 全条文LLM監査は既定ON（UI選択なし）
- UI統合: `error` はサイドバーで `st.error` 表示、ログ出力、処理停止
- 実LLM監査の実行条件はアプリ側で制御（環境変数は本計画で扱わない）
- 末尾監査がLLM要因で失敗した場合はUI表示して処理停止（途中結果は返さない）
- 末尾監査: 既存のまま採用、ログ/デバッグ出力は最小
- 条文境界監査: 既定で有効、必要時に調整

## 作業計画
- `pages/10_examination.py` で全条文LLM監査を常時有効化
- `pages/10_examination.py` の `error` 表示維持のみ（`pages/22_knowledge_llm.py` は対象外）
- 必要なら `extract_text_from_document` の例外設計を統一
- 実LLM監査テストの実行手順を確定

## 受け入れ基準
- 全条文LLM監査＋末尾監査が常時実行される
- `error` 発生時はサイドバーに表示し処理停止
- 署名/別紙/条文は現行UIの受入れ範囲で維持（session_stateのみ）

## 想定シナリオ（現行UI）
- 全条文LLM監査: 条文抽出→全条文LLM監査→末尾監査
- LLM失敗: `st.error` 表示、処理停止（途中結果は出さない）
