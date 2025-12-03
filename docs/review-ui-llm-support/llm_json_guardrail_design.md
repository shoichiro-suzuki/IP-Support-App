# 契約審査ナレッジ生成用 LLM 応答構造 & ガードレール設計（Python 実装前提）

## 1. 目的

本ドキュメントは、契約審査ナレッジを対話的に生成するシステムにおいて、以下を満たすための設計を定義する。

- LLM の応答を **JSON 形式**で統一し、  
  - ユーザー向けメッセージ (`assistant_message`)  
  - 内部状態 (`state`)  
  - ナレッジ JSON（`knowledge_json`）  
  を分離する。
- JSON スキーマを **最低限＋超有用な状態管理**に絞ることで、LLM の思考負荷を抑える。
- **JSON パース & スキーマバリデーション（Python）** により、壊れた出力を検知する。
- 壊れた出力に対して **自動リトライ**を行うことで、プロダクション運用可能な堅牢性を確保する。
- トップレベルの `control` フィールドで、バージョン管理やモード管理などのメタ情報を扱う。

Python 3.10+ を想定し、サンプル実装は標準ライブラリ＋一般的な JSON Schema バリデーションライブラリ（`jsonschema`）を前提とする。

---

## 2. 全体アーキテクチャ概要

### 2.1 コンポーネント

- **ユーザー UI**
  - LLM 応答 JSON のうち `assistant_message` フィールドのみを表示。
- **バックエンド（Python アプリケーションサーバ）**
  - LLM 呼び出し、JSON パース、スキーマバリデーション、リトライ制御、ログ保存を担当。
- **LLM**
  - プロンプトに従い、指定された JSON 構造のみを返却。

### 2.2 処理フロー（1 ターン）

1. バックエンドが、前ターンまでの `state` と `knowledge_json` を含むメッセージ群を LLM に送信。
2. LLM が **JSON 文字列のみ**を返却。
3. バックエンド（Python）が JSON パース → スキーマバリデーションを実行。
4. 成功した場合：
   - `assistant_message` を UI に表示。
   - JSON 全体（`control`, `state`, `assistant_message`, `knowledge_json`）を DB に保存。
5. 失敗した場合：
   - リトライロジックを実行（JSON 修復モード）。
   - リトライ結果が OK なら 4 と同様。
   - リトライ失敗時はエラー扱い（ユーザーには「一時的なエラー」として返却、詳細はログに保存）。

---

## 3. LLM 応答 JSON スキーマ設計

### 3.1 設計方針

- トップレベルのフィールドを **4 つに限定**することで、LLM の出力負荷を最小化する。
  - `control`
  - `state`
  - `assistant_message`
  - `knowledge_json`
- 状態管理は「今どのフェーズか」と「まだ不足している情報は何か」に絞る。
- 実際の契約審査ナレッジ構造（`knowledge_json`）は別スキーマで管理し、本設計では型を `object | null` にとどめる。

### 3.2 スキーマ概要

#### 3.2.1 トップレベル構造

```json
{
  "control": {
    "schema_version": "1.0",
    "mode": "interview"
  },
  "state": {
    "phase": "collect_case",
    "missing_info": []
  },
  "assistant_message": "ユーザーに表示する日本語メッセージ",
  "knowledge_json": null
}
```

#### 3.2.2 各フィールドの意味

- `control`
  - `schema_version`: 応答 JSON のバージョン。将来スキーマ変更時の後方互換性に利用する。
  - `mode`: 対話モード（例：`interview`, `clarify`, `finalize`）。  
    UI やサーバ側の分岐のフックとして利用する。
- `state`
  - `phase`: 現在の対話フェーズ。
    - `collect_case`（事例ヒアリング）
    - `organize_risks`（リスク整理）
    - `draft_knowledge`（ナレッジ草案作成）
    - `review_knowledge`（ナレッジレビュー・確定）
  - `missing_info`: まだユーザーから聞き出すべき情報を短い日本語で列挙した配列。
- `assistant_message`
  - ユーザーに表示する日本語メッセージ。
- `knowledge_json`
  - 契約審査ナレッジのドラフトまたは確定版。生成途中では `null` でもよい。  
  - 詳細構造: `configs/knowledge_llm/knowledge_llm_entry.schema.json`（CosmosDB準拠）

### 3.3 JSON Schema 定義（契約審査ナレッジ生成 1.0）

以下は JSON Schema（Draft 2020-12 を想定）の例。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ContractReviewKnowledgeTurn",
  "type": "object",
  "required": ["control", "state", "assistant_message", "knowledge_json"],
  "properties": {
    "control": {
      "type": "object",
      "required": ["schema_version", "mode"],
      "properties": {
        "schema_version": {
          "type": "string",
          "const": "1.0"
        },
        "mode": {
          "type": "string",
          "description": "対話の意図を表すモード",
          "enum": ["interview", "clarify", "finalize"]
        }
      },
      "additionalProperties": false
    },
    "state": {
      "type": "object",
      "required": ["phase", "missing_info"],
      "properties": {
        "phase": {
          "type": "string",
          "description": "現在の対話フェーズ",
          "enum": [
            "collect_case",
            "organize_risks",
            "draft_knowledge",
            "review_knowledge"
          ]
        },
        "missing_info": {
          "type": "array",
          "description": "まだユーザーから聞き出すべき情報を短い日本語で列挙",
          "items": {
            "type": "string"
          }
        }
      },
      "additionalProperties": false
    },
    "assistant_message": {
      "type": "string",
      "minLength": 1,
      "description": "ユーザーに表示する日本語メッセージ"
    },
    "knowledge_json": {
      "description": "契約審査ナレッジのドラフトまたは確定版。構造は別スキーマで定義。",
      "type": ["object", "null"]
    }
  },
  "additionalProperties": false
}
```

### 3.4 JSON 出力例

#### 例 1: 事例ヒアリング中（ナレッジ未生成）

```json
{
  "control": {
    "schema_version": "1.0",
    "mode": "interview"
  },
  "state": {
    "phase": "collect_case",
    "missing_info": [
      "契約書の種類（売買契約、業務委託契約など）",
      "問題となった条文の見出し・条番号"
    ]
  },
  "assistant_message": "ありがとうございます。まず、この事例がどの種類の契約書に関するものか教えてください（例：売買契約、業務委託契約など）。また、問題になった条文の見出しや条番号が分かれば併せて教えてください。",
  "knowledge_json": null
}
```

#### 例 2: ナレッジドラフト生成フェーズ

```json
{
  "control": {
    "schema_version": "1.0",
    "mode": "finalize"
  },
  "state": {
    "phase": "draft_knowledge",
    "missing_info": [
      "このナレッジを適用すべき条件の具体的な表現"
    ]
  },
  "assistant_message": "ヒアリングした内容をもとに、ナレッジのドラフトを作成しました。内容をご確認いただき、適用条件の表現が実務に合っているかコメントをいただけますか？",
  "knowledge_json": {
    "title": "秘密保持義務の期間設定（3 年 vs. 5 年）",
    "contract_types": ["秘密保持契約", "業務委託契約"],
    "problem_pattern": "相手方が秘密保持期間を 3 年に限定しているが、こちらとしては 5 年を希望したいケース",
    "risk": "システム運用・保守の期間が 3 年を超える場合、情報漏えいリスクや紛争時の立証が困難になる。",
    "recommended_clause": "秘密情報の保持義務は、本契約終了後も 5 年間継続するものとする。",
    "note": "プロジェクト期間が明確に 3 年以内で終了する場合は 3 年でも実務上問題ないことが多い。"
  }
}
```

`knowledge_json` の詳細スキーマは別ドキュメントとして定義する。

---

## 4. プロンプト設計（フォーマット指定）

### 4.1 基本方針

- LLM は常に **1 つの JSON オブジェクトのみ**を出力する。
- JSON の外側に一切の文字列（説明、日本語、コードブロック記号 ``` など）を出力してはならない。
- `assistant_message` フィールドにのみ自然言語を書き、その内容が UI に表示される前提で設計する。

### 4.2 System プロンプト例（フォーマット指定）

以下はテキストベースでのフォーマット指定例。  
実際の実装では、これにタスク定義（契約審査ナレッジ生成方針など）を加える。

```text
あなたは契約審査ナレッジ生成のためのアシスタントです。

出力は必ず「単一の JSON オブジェクト」のみとし、
JSON 以外の文字（説明文、日本語、改行だけの行、コードブロック記号 ``` など）は一切出力してはいけません。

出力 JSON のトップレベル構造は、必ず次の 4 つのフィールドのみを持ちます。

{
  "control": {
    "schema_version": "1.0",
    "mode": "interview" | "clarify" | "finalize"
  },
  "state": {
    "phase": "collect_case" | "organize_risks" | "draft_knowledge" | "review_knowledge",
    "missing_info": string の配列
  },
  "assistant_message": string,
  "knowledge_json": object または null
}

制約:
- 上記 4 フィールド以外のフィールドを追加してはいけません。
- "knowledge_json" には、契約審査ナレッジのドラフトまたは確定版を入れてください。まだ確定していない場合は null でもかまいません。
- "assistant_message" には、ユーザーに表示する日本語のメッセージのみを書いてください。
- "missing_info" には、ユーザーから追加で聞き出したい情報を短い日本語の箇条書きとして列挙してください。

次にユーザーからの入力が与えられます。
あなたは上記の仕様に完全に従う JSON オブジェクトのみを出力してください。
```

### 4.3 API レベルのフォーマット指定

OpenAI / Azure OpenAI 等の API で `response_format` や JSON スキーマ指定が利用可能な場合は、  
テキストでのフォーマット指定に加えて、API レベルでも JSON 出力を強制する。

Python の簡易イメージ（OpenAI ライブラリを想定）：

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-4.1-mini",
    input=messages,
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "ContractReviewKnowledgeTurn",
            "schema": {  # 上記 JSON Schema と同等の dict
                # ...
            }
        }
    },
)
raw_output: str = response.output[0].content[0].text
```

---

## 5. JSON パース & スキーマバリデーション（Python 実装例）

### 5.1 使用ライブラリ

- `json`（標準ライブラリ）
- `jsonschema`（JSON Schema バリデーション用の第三者ライブラリ）

`jsonschema` のインストール：

```bash
pip install jsonschema
```

### 5.2 型定義のイメージ（任意）

厳密な型チェックを行いたい場合は `typing.TypedDict` や `pydantic` を使う。  
ここではシンプルに `TypedDict` の例を示す。

```python
from typing import Literal, TypedDict, List, Dict, Any, Optional


Mode = Literal["interview", "clarify", "finalize"]
Phase = Literal["collect_case", "organize_risks", "draft_knowledge", "review_knowledge"]


class Control(TypedDict):
    schema_version: str
    mode: Mode


class State(TypedDict):
    phase: Phase
    missing_info: List[str]


class LlmTurn(TypedDict):
    control: Control
    state: State
    assistant_message: str
    knowledge_json: Optional[Dict[str, Any]]
```

### 5.3 JSON パース & スキーマバリデーション関数

```python
import json
from dataclasses import dataclass
from typing import Union, Dict, Any
from jsonschema import Draft202012Validator, ValidationError


# 事前に JSON Schema を Python dict として読み込む
with open("configs/knowledge_llm/knowledge_llm_turn.schema.json", "r", encoding="utf-8") as f:
    CONTRACT_REVIEW_TURN_SCHEMA: Dict[str, Any] = json.load(f)

VALIDATOR = Draft202012Validator(CONTRACT_REVIEW_TURN_SCHEMA)


@dataclass
class ValidationResult:
    ok: bool
    data: Union[LlmTurn, None] = None
    error_type: Union[str, None] = None  # "parse_error" | "schema_error"
    errors: Union[str, None] = None


def parse_and_validate_llm_output(raw: str) -> ValidationResult:
    # JSON パース
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        return ValidationResult(
            ok=False,
            error_type="parse_error",
            errors=str(e),
        )

    # スキーマバリデーション
    try:
        VALIDATOR.validate(parsed)
    except ValidationError as e:
        # e.message や e.path などからメッセージを組み立てる
        return ValidationResult(
            ok=False,
            error_type="schema_error",
            errors=f"{list(e.path)}: {e.message}",
        )

    return ValidationResult(
        ok=True,
        data=parsed,  # 型チェックを厳密にするならここで LlmTurn への変換・検証も追加する
    )
```

---

## 6. 壊れたときのリトライ設計（Python 実装例）

### 6.1 リトライ方針

- JSON 出力が壊れている場合は、**1〜2 回まで自動リトライ**を行う。
- リトライでは、元の出力を LLM に渡し、「同じ意味内容を保ったまま指定スキーマに従う JSON に修正せよ」と指示する。
- それでも失敗した場合は、ユーザーには汎用的なエラーメッセージを返し、ログを残して人間が調査できるようにする。

### 6.2 修復プロンプトのイメージ（User メッセージ）

```text
以下は、あなたが直前に出力した JSON 文字列です。

---
{{assistant_output_here}}
---

この JSON をパースおよびスキーマバリデーションしたところ、エラーが発生しました。

エラー種別: {{error_type}}  // "parse_error" または "schema_error"
エラー内容: {{error_detail}}

元の意味内容はできるだけ維持したまま、指定されているスキーマに完全に準拠する JSON オブジェクトのみを出力してください。

制約:
- JSON 以外の文字を一切出力しないでください。
- フィールド構造は control, state, assistant_message, knowledge_json の 4 つのみを使用してください。
```

### 6.3 LLM 呼び出し＋ガードレールの統合（Python 擬似コード）

```python
from typing import List, Dict, Any


def call_llm_api(messages: List[Dict[str, Any]]) -> str:
    """
    実際の LLM 呼び出しを行う関数。
    戻り値は「LLM が出力した生の文字列」（JSON のはず、だが壊れている可能性あり）。
    """
    # OpenAI の例（responses API）
    from openai import OpenAI

    client = OpenAI()

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=messages,
    )
    # output[0].content[0].text が JSON 文字列である前提
    return response.output[0].content[0].text


def build_repair_instruction(error_type: str, errors: str, raw_output: str) -> str:
    return "
".join(
        [
            "以下は、あなたが直前に出力した JSON 文字列です。",
            "",
            "---",
            raw_output,
            "---",
            "",
            "この JSON をパースおよびスキーマバリデーションしたところ、エラーが発生しました。",
            "",
            f"エラー種別: {error_type}",
            f"エラー内容: {errors}",
            "",
            "元の意味内容はできるだけ維持したまま、指定されているスキーマに完全に準拠する JSON オブジェクトのみを出力してください。",
            "",
            "制約:",
            "- JSON 以外の文字を一切出力しないでください。",
            "- フィールド構造は control, state, assistant_message, knowledge_json の 4 つのみを使用してください。",
        ]
    )


def call_llm_with_guardrails(
    messages: List[Dict[str, Any]],
    max_retries: int = 1,
) -> LlmTurn:
    """
    - LLM を呼び出し
    - JSON パース & スキーマバリデーション
    - 必要ならリトライ（修復モード）
    をまとめて行い、最終的に妥当な LlmTurn を返す。
    """
    raw = call_llm_api(messages)
    result = parse_and_validate_llm_output(raw)

    retries = 0
    while not result.ok and retries < max_retries:
        retries += 1

        repair_message = build_repair_instruction(
            error_type=result.error_type or "unknown_error",
            errors=result.errors or "",
            raw_output=raw,
        )

        repair_messages: List[Dict[str, Any]] = [
            *messages,
            {"role": "assistant", "content": raw},
            {"role": "user", "content": repair_message},
        ]

        raw = call_llm_api(repair_messages)
        result = parse_and_validate_llm_output(raw)

    if not result.ok:
        # ログ用に詳細を残す
        # logger.error("LLM output invalid", extra={...})
        raise RuntimeError(
            f"LLM output is invalid after {retries} retries: "
            f"{result.error_type} - {result.errors}"
        )

    # result.data は LlmTurn として扱う
    return result.data  # type: ignore[return-value]
```

---

## 7. UI / ログ設計のポイント

### 7.1 UI 側の扱い

- ユーザーに表示するのは **常に `assistant_message` のみ** とする。
- `assistant_message` が空文字列または極端に短い場合は、サーバ側で警告ログを出し、必要に応じて再生成を検討する。

### 7.2 ログ / データストア

- 1 ターンごとに LLM 応答 JSON 全体を保存する。
  - `control`, `state`, `assistant_message`, `knowledge_json` をそのまま保存。
- 別テーブル・別コレクションで `knowledge_json` を集約し、  
  契約審査ナレッジベースとして二次利用（RAG、few-shot、評価など）することを想定する。
- `control.mode` や `state.phase` を軸に、以下のような分析も可能になる：
  - 何ターンで `draft_knowledge` / `finalize` に到達するか
  - どのフェーズでユーザーが離脱しやすいか など

---

## 8. 拡張方針

将来的に、より複雑な状態管理やマルチエージェント構成が必要になった場合でも、
- トップレベル構造（`control`, `state`, `assistant_message`, `knowledge_json`）は維持
- `control.schema_version` を更新（例: `"2.0"`）
- `state` 内に必要なフィールドを追加（既存フィールドは可能な限り維持）
という方針で進化させる。

Python 実装側では、
- JSON Schema のバージョンごとに Validator を切り替える
- `schema_version` ごとに薄いアダプタ層を設ける
ことで、既存ログやナレッジを利用しつつ、徐々に高度なフローへ移行できる。

以上が、Python 実装前提での最低限のガードレール（JSON パース & スキーマバリデーション＋壊れたときのリトライ）付き設計となる。
