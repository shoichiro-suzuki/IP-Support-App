# ToDo
- [x] `pages/22_knowledge_llm.py` にナレッジ創出チャットUIとプロンプトフロー実装（テキスト+契約書入力）
- [ ] 抽出結果を `knowledge_title` などCosmosDBスキーマへ整形し、同ページでJSONダウンロード可能にする（`pages/22_knowledge_llm.py`）
- [ ] JSONアップロードで `id`/`knowledge_number` 採番、ベクトル付与しCosmosDBへ登録（`pages/22_knowledge_llm.py`）
- [ ] 入力バリデーション・エラーハンドリング・動作確認（UI/DB）
