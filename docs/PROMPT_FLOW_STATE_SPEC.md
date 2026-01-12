# LLM プロンプトフロー状態管理 共通仕様

- 目的: 状態管理付きプロンプトフローを任意のUI/バックエンドで再実装できるよう、フレームワーク非依存の仕様に抽出。
- 関連: `knowledge_llm_turn.schema.json`, `knowledge_llm_entry.schema.json`, システムプロンプト群(`system_prompt_*.md`), 添付テキスト抽出ユーティリティ。

## 状態JSON設計
- ターンJSONは4フィールド固定: `control`(schema_version=1.0, mode=interview|clarify|finalize), `state`(phase=collect_case|organize_risks|draft_knowledge|review_knowledge, missing_info[]), `assistant_message`(ユーザー表示文), `knowledge_json`(nullable; 別スキーマ準拠)。
- ナレッジ本体スキーマは `knowledge_llm_entry.schema.json`（contract_type/knowledge_title/target_clause/review_points/action_plan/clause_sample の文字列必須）。

## LLM呼び出しフロー
- メッセージ積み上げ: system にシステムプロンプト、assistant に `FEW_SHOT_TURN`（スキーマ準拠サンプル）、履歴(user/assistant)を順番に追加し、最後に user に結合済みペイロード（指示 + 添付テキスト）。
- `response_format` に `json_schema` を設定し、LLM側でスキーマ制約を強制（スキーマ未取得時は None）。
- 出力処理: `parse_and_validate_turn` で JSON parse → ターンスキーマ検証 → `knowledge_json` をナレッジスキーマで検証し、正規化（空は ""、リストで返却）。

## リトライと修復
- 1回目失敗時の生出力とバリデーションエラーを `build_repair_instruction` で再提示し、同じプロンプトスタックに assistant=生出力・user=修復指示を足して最大2回再呼び出し。
- すべて失敗した場合は `ok=False` として生出力とエラー種別を返却しUI側で通知。

## セッション状態とUI更新
- UI種別に依存せず、セッション状態には少なくとも `chat`(会話履歴), `knowledge_outputs`(ナレッジ配列), `llm_client`(LLM呼び出しクライアント), `debug_logs`(DEBUG時のみ) を保持。
- 入力受付後に履歴へ即時追加 → LLM呼び出し → 成功時はナレッジ配列を置換し `assistant_message` を履歴に追加、失敗時は生出力+エラー種別を履歴に追加するだけでUI再描画。
- 添付ファイル処理: 一時ファイルや in-memory で安全にテキスト抽出 → 段落化 → ユーザー指示と結合してプロンプトに投入。ストレージへの恒久保存は行わない。

## 移植手順（最小）
1. 上記2つの JSON Schema をプロジェクトに配置し、`Draft202012Validator` でバリデーションを用意。
2. システムプロンプトと `FEW_SHOT_TURN` をスキーマ準拠のJSON文字列で準備（フィールド追加禁止）。
3. `call_llm` 相当を実装: メッセージスタック構築 → `response_format=json_schema` で呼び出し → バリデーション → リトライ/修復 → `assistant_message` と `knowledge`（正規化済み配列）の形で返す。
4. UI/コントローラ層で会話履歴・出力をステート管理し、失敗時は生出力とエラー種別をそのまま提示して再入力を促す。
5. DEBUG用途でリクエスト/レスポンス/再試行結果をログ化する場合は、セッション内配列に追記するだけに留め、外部I/Oは行わない。
6. LLMクライアントとストレージ周辺は依存性注入で差し替え可能にし、UI種別（Web/CLI/チャットボット）に合わせて入力・再描画処理だけを実装すれば移植可能。

## 実装例（抜粋）
```python
# FEW_SHOT_TURN 例（JSON文字列）
FEW_SHOT_TURN = json.dumps({
  "control": {"schema_version": "1.0", "mode": "interview"},
  "state": {"phase": "collect_case", "missing_info": []},
  "assistant_message": "次の質問をしてください",
  "knowledge_json": None
}, ensure_ascii=False)

def call_llm(user_text, file_texts, system_prompt, history, client, turn_schema, entry_schema):
    messages = [{"role": "system", "content": system_prompt},
                {"role": "assistant", "content": FEW_SHOT_TURN}]
    for h in history or []:
        if h["role"] in ("user", "assistant"):
            messages.append({"role": h["role"], "content": h["content"]})
    payload = "\n\n".join(filter(None, [
        f"ユーザー指示:\n{user_text}" if user_text else "",
        f"添付テキスト:\n{'\n\n'.join(file_texts)}" if file_texts else ""
    ]))
    messages.append({"role": "user", "content": payload})
    fmt = {"type": "json_schema", "json_schema": {"name": "Turn", "schema": turn_schema}}
    raw = client.chat(messages, format=fmt)
    validated = parse_and_validate_turn(raw, turn_schema, entry_schema)
    if validated["ok"]:
        return validated
    # 修復リトライ（最大2回）
    for _ in range(2):
        repair = build_repair_instruction(raw, validated["error"], validated["error_type"])
        retry_msgs = messages + [{"role": "assistant", "content": raw},
                                 {"role": "user", "content": repair}]
        raw = client.chat(retry_msgs, format=fmt)
        validated = parse_and_validate_turn(raw, turn_schema, entry_schema)
        if validated["ok"]:
            return validated
    return {"ok": False, "raw": raw, "error": validated["error"]}

def parse_and_validate_turn(raw, turn_schema, entry_schema):
    parsed = json.loads(raw)
    Draft202012Validator(turn_schema).validate(parsed)
    kj = parsed.get("knowledge_json")
    knowledge = []
    if kj is not None:
        Draft202012Validator(entry_schema).validate(kj)
        knowledge.append({k: str(kj.get(k, "") or "") for k in ("contract_type","knowledge_title","target_clause","review_points","action_plan","clause_sample")})
    return {"ok": True, "assistant_message": parsed.get("assistant_message",""), "knowledge": knowledge, "raw": raw}
```

- UI例（疑似コード）: 入力受信 → 履歴に user 追加 → `call_llm` → 成功: 履歴に assistant_message 追加 + knowledge_outputs を状態に保存し描画。失敗: 生出力+エラー種別を履歴に追加し再描画。
- 添付ファイル例: 一時ファイル経由で PDF/DOCX を `extract_text_from_document(path)` → 行区切りで段落化 → プロンプトに連結。テキストファイルはUTF-8で直接読み込み。
