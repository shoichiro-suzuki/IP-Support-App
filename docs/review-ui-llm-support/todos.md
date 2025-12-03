# ToDo
- [x] `pages/22_knowledge_llm.py` にナレッジ創出チャットUIとプロンプトフロー実装（テキスト+契約書入力）
- [ ] `docs/review-ui-llm-support/llm_json_guardrail_design.md` に沿った JSON 固定（control/state/assistant_message/knowledge_json）、response_format+スキーマバリデーション+リトライ実装
- [ ] 抽出結果を `knowledge_title` などCosmosDBスキーマへ整形し、同ページでJSONダウンロード可能にする（`pages/22_knowledge_llm.py`）
- [ ] JSONアップロードで `knowledge_number` 採番しCosmosDBへ登録（`pages/20_knowledge.py`、`configs/knowledge_llm/knowledge_llm_entry.schema.json` 検証）
- [ ] 入力バリデーション・エラーハンドリング・動作確認（UI/DB）
