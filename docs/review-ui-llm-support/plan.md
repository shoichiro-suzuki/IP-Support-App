# 実装計画

- 目的: `pages/22_knowledge_llm.py` でナレッジ創出→スキーマ整形→追加を完結
- 前提: CosmosDBスキーマ (`knowledge_title`, `target_clause`, `review_points`, `action_plan`, `clause_sample`, `contract_type`)、既存Azureサービスを利用
- ガードレール: `docs/review-ui-llm-support/llm_json_guardrail_design.md` の JSON スキーマ+リトライ設計に沿い、LLM 応答を `control/state/assistant_message/knowledge_json` に固定

## サンプルデータ取得
- `python scripts/export_knowledge_samples.py --limit 5` で `docs/review-ui-llm-support/knowledge_samples.json` を生成（契約種別/検索テキスト指定可）
- 生成サンプルをプロンプト設計・UIの初期値に利用し、抽出結果の整形・ダウンロード仕様を検証

## フェーズ
1. ナレッジ創出チャット： `pages/22_knowledge_llm.py`
   - テキスト+契約書ファイルを受け、プロンプト（A/B切替）で抽出
   - 応答はガードレール設計の JSON フォーマットを強制（response_format + スキーマバリデーション/リトライ）
2. スキーマ整形/ダウンロード： `pages/22_knowledge_llm.py`
   - 抽出結果をCosmosDBスキーマにマッピング
   - JSONダウンロードを提供し、アップロード形式を固定
3. JSONアップロードで新規登録：`pages/20_knowledge.py`
   - JSONを `knowledge_llm_entry` スキーマで検証し、`knowledge_number` 採番・`id`/タイムスタンプ付与
   - CosmosDBへ追加し、既存ナレッジ一覧へ即時反映

## テスト/確認
- 入力(テキスト+ファイル)→抽出→JSON→アップロードのUI動線
- 必須フィールド欠落/重複時のバリデーション
- ベクトル生成・DB書き込みの正常系/異常系ログ
