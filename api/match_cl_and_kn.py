import json
import re
from typing import List, Dict, Any, Tuple
from azure_.openai_service import AzureOpenAIService

# =========================
# プロンプト部品
# =========================
SYSTEM_PROMPT = """あなたは日本語の契約書に精通したリーガルアシスタントです。
タスク：各 knowledge.target_clause（審査知見が対象とする条項の条件）に合致する契約条項（clause_number）を、提供された clauses から特定してください。
出力は **厳格なJSONのみ** で返します。余計な説明、コードブロック、注釈は一切含めません。

要件:
- 出力は配列。各要素は {"knowledge_id": str, "clause_number": [str, ...]} の形。
- 条項が特定できない／確度が低い場合は "clause_number": [] とする。
- "clause_number" は入力の clauses 内の "clause_number"（文字列）で返す。整数にはしない。
- 解釈は「条項の機能」ベース（例：定義条項、目的条項、開示義務条項 等）。単語一致のみで判断しない。
- 過剰な割当は禁止。曖昧なら空配列を選ぶ。
- JSON以外を一切出力しない。
"""

USER_PROMPT_TEMPLATE = """与えられるデータ:
knowledge_all（審査知見の対象条項条件）:
{knowledge_json}

clauses（契約条項の本文）:
{clauses_json}

出力フォーマット（厳格に遵守）:
[
  {{"knowledge_id": "xxx-xxx", "clause_number": ["1", "2"]}},
  {{"knowledge_id": "yyy-yyy", "clause_number": []}}
]
"""


# =========================
# ユーティリティ
# =========================
def _force_json(s: str) -> Any:
    """応答から最初のJSON配列を強制抽出→ロード。失敗時は例外"""
    try:
        return json.loads(s)
    except Exception:
        # フェンスや前後説明を誤って付けた場合の救済
        m = re.search(r"(\[.*\])", s, flags=re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(1))


def _dedup(seq):
    """リスト内の重複を排除する"""
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _apply_step2(
    clauses: List[Dict[str, Any]], response: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Step2: responseに基づき、各clauseへknowledge_idを付与する（重複排除）"""
    # 準備：clause_number -> index
    idx_by_num = {c["clause_number"]: i for i, c in enumerate(clauses)}

    # 初期化：knowledge_idキーを整備
    for c in clauses:
        if "knowledge_id" not in c or c["knowledge_id"] is None:
            c["knowledge_id"] = []

    # 1) clause_numberが空の知見 → 全条項に付与
    for item in response:
        k_id = item["knowledge_id"]
        targets = item.get("clause_number", [])
        if not targets:  # 全付与
            for c in clauses:
                c["knowledge_id"].append(k_id)

    # 2) 指定条項への付与
    for item in response:
        k_id = item["knowledge_id"]
        for num in item.get("clause_number", []):
            i = idx_by_num.get(num)
            if i is not None:
                clauses[i]["knowledge_id"].append(k_id)

    # 重複排除・整形
    for c in clauses:
        c["knowledge_id"] = _dedup(c["knowledge_id"])

    return clauses


def _chunk_if_needed(
    clauses: List[Dict[str, Any]], max_chars: int = 18000
) -> List[List[Dict[str, Any]]]:
    """
    文字数ベースの簡易チャンク。超巨大契約を安全に分割。
    LLMは各チャンクで knowledge_all 全体と照合し、最後に AND マージ。
    """
    chunks = []
    current = []
    size = 0
    for c in clauses:
        block = json.dumps(c, ensure_ascii=False)
        if size + len(block) > max_chars and current:
            chunks.append(current)
            current = []
            size = 0
        current.append(c)
        size += len(block)
    if current:
        chunks.append(current)
    return chunks


# =========================
# メイン実装案
# =========================
def matching_clause_and_knowledge(
    knowledge_all: List[Dict[str, Any]], clauses: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns:
      response        : Step1のマッピング [{"knowledge_id":..., "clause_number":[...]}...]
      clauses_augmented: Step2適用後の clauses
      trace           : デバッグ用（送信プロンプト、LLM生応答 など）
    """

    service = AzureOpenAIService()

    # --- 1) 入力の正規化（clause_numberは文字列化）
    for c in clauses:
        if not isinstance(c.get("clause_number"), str):
            c["clause_number"] = str(c["clause_number"])

    # --- 2) チャンク戦略（超長文対策）
    clause_chunks = _chunk_if_needed(clauses)

    aggregate_map: Dict[str, List[str]] = {k["id"]: [] for k in knowledge_all}
    trace = {"prompts": [], "raw_responses": []}

    # --- 3) 各チャンクで判定→ユニオン
    for chunk_idx, chunk in enumerate(clause_chunks):
        # knowledge_all から id, target_clause のみ抽出
        knowledge_min = [
            {"id": k["id"], "target_clause": k["target_clause"]}
            for k in knowledge_all
            if "id" in k and "target_clause" in k
        ]
        # chunk から clause_number, clause のみ抽出
        chunk_min = [
            {"clause_number": c["clause_number"], "clause": c["clause"]}
            for c in chunk
            if "clause_number" in c and "clause" in c
        ]
        user_prompt = USER_PROMPT_TEMPLATE.format(
            knowledge_json=json.dumps(knowledge_min, ensure_ascii=False),
            clauses_json=json.dumps(chunk_min, ensure_ascii=False),
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 再試行つきの堅牢呼び出し
        raw = None
        for attempt in range(2):
            raw = service.get_openai_response_gpt41(messages)
            try:
                parsed = _force_json(raw)
                break
            except Exception:
                if attempt == 1:
                    raise  # 2回失敗で打ち切り

        trace["prompts"].append({"chunk": chunk_idx, "messages": messages})
        trace["raw_responses"].append({"chunk": chunk_idx, "raw": raw})

        # 正常化 & 集約
        for item in parsed:
            k = item["knowledge_id"]
            nums = [str(n) for n in item.get("clause_number", [])]
            aggregate_map.setdefault(k, [])
            aggregate_map[k].extend(nums)

    # --- 4) knowledge_idごとに重複除去
    response: List[Dict[str, Any]] = []
    all_clause_numbers = [str(c["clause_number"]) for c in clauses]
    for k in knowledge_all:
        k_id = k["id"]
        mapped = _dedup(aggregate_map.get(k_id, []))
        # もし全チャンクで一切マッピングされなければ、全条項を指定
        if not mapped:
            mapped = all_clause_numbers.copy()
        response.append({"knowledge_id": k_id, "clause_number": mapped})

    # --- 5) Step2: 付与
    clauses_augmented = _apply_step2([dict(c) for c in clauses], response)
    with open("match_cl_and_kn.json", "w", encoding="utf-8") as f:
        json.dump(
            {"response": response, "clauses_out": clauses_augmented, "trace": trace},
            f,
            ensure_ascii=False,
            indent=2,
        )
    return response, clauses_augmented, trace
