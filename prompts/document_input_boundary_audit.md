あなたは契約書末尾の境界監査を行う。
入力は行番号付きテキストで、境界候補は `---BOUNDARY:<ID>---` 行として挿入済み。

タスク:
- 既存境界のみを評価し `accept` / `move` / `remove` を決める
- `final_sections` を確定する

制約:
- 新規境界の追加は禁止
- 出力はJSONのみ
- `final_sections` は昇順/欠落なし/重複なし
- 低信頼時は `verdict=reject` と `warnings` を付与

出力フォーマット:
{
  "verdict": "accept" | "adjust" | "reject",
  "boundaries": [
    {
      "id": "SIG_CAND_1",
      "status": "accept" | "move" | "remove",
      "move_to_line": 1,
      "section_after_boundary": "signature" | "attachments" | "unknown",
      "confidence": 0.0,
      "rationale": "string"
    }
  ],
  "final_sections": [
    { "name": "clause_last", "start_line": 1, "end_line": 10 },
    { "name": "signature", "start_line": 11, "end_line": 20 },
    { "name": "attachments", "start_line": 21, "end_line": 30 }
  ],
  "warnings": [
    { "code": "NEEDS_HUMAN_REVIEW", "message": "string" }
  ]
}
