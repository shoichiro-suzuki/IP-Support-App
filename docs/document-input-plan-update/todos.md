# TODO
- [x] `services/document_input.py` のPDF抽出を `result.paragraphs.content` に変更
- [x] 境界監査クラスを `services/` 配下に分離
- [x] 末尾分割のルール候補挿入を実装
- [x] 境界監査用LLMプロンプトを新規作成
- [x] LLM監査のJSONスキーマバリデーション追加
- [x] JSONパース失敗時は1回リトライ
- [x] `docs/document_input.md` を実装内容で更新
- [x] 末尾分割のテストケース作成（英日/別紙/署名/ページフッター）

**Other**
- 改行欠落はOCRモデル精査で対応（擬似行生成は原則使わない）
