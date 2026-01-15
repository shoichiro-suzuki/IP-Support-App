# document_input 改造計画
- 対象: `services/document_input.py`
- 目的: 契約書テキストを条文ごとに分割し、末尾（署名欄/別紙）を高精度に切り出す
- 実装: `services/boundary_audit.py` / `prompts/document_input_boundary_audit.md` / `configs/document_input/boundary_audit.schema.json`

## 課題
- 「第X条に基づき」等の引用で誤分割が頻発
- LLM再結合が不安定（再結合すべき箇所の見落とし）

## 改造方針
### テキスト抽出
- Word: 現行のテキスト抽出方法から変更なし
- PDF:
  - 変更: `result.paragraphs.content` を1行単位で連結（無い場合は中断して通知）
  - 参考: `tests/ocr_result_test_加工済.json`

### 条文分割
- 行頭の `第X条` または `Article X` を条文セクション開始と判定
- 文頭から第1条直前までを前文（title/introduction）
- 最終条文以降は末尾塊として後段仕様で分割

### LLM利用（境界監査）
- ルールベースで境界候補を挿入
- 行番号（段落番号）付きコンテキストに変換
- LLMは境界の妥当性を判断し、修正後の行番号境界をJSONで返却
- 末尾塊に限らず、条文境界全体/一部にも適用可能
- 仕様は「末条文末尾ルール分割 & LLM監査 仕様書」を適用
- 全条文境界のLLM監査は既定で有効

### 境界監査クラス（共通化）
- 目的: 境界候補挿入＋段落番号付与＋LLM監査を共通処理として切り出す
- 入力: 任意のテキストブロック（全文/一部）
- 出力: 境界確定済みセクション（任意数）
- 想定利用:
  - 末尾塊（署名/別紙）
  - 条文境界（第X条/Articleの補正）
  - 特定区間のみの再監査

### 境界監査クラス 入出力（段落=1行）
- 前提: LLM入力は「段落=1行」。紙面端の見た目改行は含まれない
- 入力:
  - `paragraphs: list[str]`（段落配列）
  - `boundary_rules: list[BoundaryRule]`
  - `preprocess: BoundaryPreprocessOptions`
    - `preserve_empty_lines: bool`
    - `line_number_width: int`
  - `llm_config: LlmAuditConfig`
- 出力:
  - `final_sections: list[AuditedSection]`（`name/start_line/end_line`）
  - `boundaries: list[BoundaryDecision]`（`id/status/move_to_line/confidence/rationale`）
  - `warnings: list[AuditWarning]`

---

# 末条文末尾（署名欄・別紙）ルール分割 & LLM監査 仕様書

## 1. 目的
- 出力:
  - `clause_last`: 最終条文本文（署名・別紙以前）
  - `signature`: 署名欄
  - `attachments`: 別紙・添付
- 手順: ルールで候補境界挿入 → LLMで境界監査

## 2. スコープ
- 対象: 最終条文 + 末尾ブロック（署名/別紙/脚注/ページ番号等）
- 入力: `\n` 区切りテキスト
- 非対象: 条文分割全体、OCR改行復元（擬似行生成は可）

## 3. 全体フロー
- 前処理（行正規化/行番号付与）
- ルール候補境界挿入（複数）
- LLM監査（accept/move/remove）
- 境界適用 → セクション抽出 → 整合性チェック

## 4. 前処理
- 行分割: `\n` で `lines[]` 生成（空行保持）
- 擬似行生成（任意）:
  - 改行欠落リスクはOCRモデル精査で対応する方針
  - 適用する場合は `。`/`.`/`;` 後の改行挿入や連続スペース境界を保守的に利用
- 行番号付与: `"[NNN] "`（1始まり/ゼロ埋め推奨）

## 5. ルールベース候補境界
### 5.1 境界トークン
- 行として単独挿入: `---BOUNDARY:<ID>---`
- 原文は改変しない

### 5.2 種類/上限
- 署名候補: `SIG_CAND_n`（最大3）
- 別紙候補: `ATTACH_CAND_n`（最大5）
- 近接候補（±2行）は強い指標を優先して統合

### 5.3 署名候補ルール
- 強指標（直前に挿入）:
  - `署名`, `記名`, `押印`, `捺印`, `締結の証`, `署名押印欄`
  - `IN WITNESS WHEREOF`, `Signed`, `Signature`
  - 日付行（`YYYY年MM月DD日`, `YYYY/MM/DD`, `YYYY-MM-DD`）
  - 当事者欄（`（甲）`, `（乙）`, `Company`, `Address`, `Name`, `Title`）
- 弱指標:
  - `印` 単独は不可
  - `印` + 役職/署名語の共起、または近接5行以内の日付行で候補化

### 5.4 別紙候補ルール
- 直前に挿入:
  - `別紙`, `添付`, `別添`, `付録`
  - `Annex`, `Appendix`, `Attachment`, `Schedule`
  - `別紙1`, `別紙 第1`, `Appendix A`, `Annex 1`

## 6. LLM監査
### 6.1 役割
- 既存境界の `accept/move/remove`
- 最終セクション範囲を確定
- 新規境界追加は禁止

### 6.2 入力
- 行番号付きテキスト（境界行含む）
- 任意特徴量:
  - `has_date_pattern`, `has_company_marker`, `has_title_marker`,
    `looks_like_heading`, `page_marker`

### 6.3 出力（JSONのみ）
```json
{
  "verdict": "accept" | "adjust" | "reject",
  "boundaries": [
    {
      "id": "SIG_CAND_1",
      "status": "accept" | "move" | "remove",
      "move_to_line": 1,
      "section_after_boundary": "signature" | "attachments" | "unknown",
      "confidence": 0.0,
      "rationale": "string (<= 25 words)"
    }
  ],
  "final_sections": [
    { "name": "clause_last", "start_line": 1, "end_line": 10 },
    { "name": "signature", "start_line": 11, "end_line": 20 },
    { "name": "attachments", "start_line": 21, "end_line": 30 }
  ],
  "warnings": [
    { "code": "NEEDS_HUMAN_REVIEW" | "AMBIGUOUS_BOUNDARY" | "INCONSISTENT_FORMAT", "message": "string" }
  ]
}
```

### 6.4 制約
- `move_to_line`: `status="move"` のみ必須、1..N
- `final_sections`: 昇順/重複禁止、境界トークン行のみのギャップは許容
- `rationale`: 25 words以内
- `verdict`: 変更なし=accept、move/remove有り=adjust、確定不能=reject+warning

### 6.5 判断ガイド
- 署名開始: 締結文/日付/当事者欄の直前
- 別紙開始: 別紙/Annex/Appendix等の見出し直前
- Page表記は原則 `clause_last` 側（必要なら warning）

### 6.6 失敗時
- 低信頼: `NEEDS_HUMAN_REVIEW`
- JSON不正/制約違反: 監査失敗として `reject`
- JSONパース失敗時は1回リトライ

## 7. ポスト処理
- `final_sections` に従い抽出（`[NNN]` は除去可）
- 整合性チェック:
  - 全行を完全被覆（欠落/重複なし）
  - `final_sections` は昇順/範囲内/重複禁止
  - 不整合は `NEEDS_HUMAN_REVIEW`
- 出力:
  - `clause_last_text`
  - `signature_text`（任意）
  - `attachments[]`（任意）
  - `review_flags[]`（任意）

## 8. 監査プロンプト要件
- 既存境界の accept/move/remove のみ
- 新規境界追加禁止
- JSONのみ出力
- `final_sections` は欠落/重複禁止
- 低信頼時は `NEEDS_HUMAN_REVIEW`

## 9. テスト観点
- 署名欄が「以上」だけで始まる
- `印` が本文に出る（誤爆なし）
- 英文契約（IN WITNESS WHEREOF / Signed / Annex）
- 別紙複数、署名欄なしで別紙のみ
- OCR崩れ（改行欠落/全角半角混在）
- ページフッター混入

## 10. 実装メモ
- 境界監査: `services/boundary_audit.py`
- 監査プロンプト: `prompts/document_input_boundary_audit.md`
- スキーマ: `configs/document_input/boundary_audit.schema.json`
- テスト: `tests/test_tail_split.py`
- テスト: `tests/test_document_input_full_split.py`
- テスト: `tests/test_clause_boundary_audit.py`
- 機能テスト: `scripts/functional_test_tail_split.py`
- 機能テスト: `scripts/functional_test_clause_boundary_audit.py`

## 10. 期待効果
- ルール: 高速・説明可能（候補広め）
- LLM: 境界監査に限定し曖昧さ吸収
- 失敗は `NEEDS_HUMAN_REVIEW` へ明示
