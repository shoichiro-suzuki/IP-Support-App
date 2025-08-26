import asyncio
import json
import os
from typing import Any, Dict, List
from dotenv import load_dotenv

# LangChain
# pip install langchain_openai langchain_core
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable

load_dotenv()
azure_endpoint = os.getenv(
    "OPENAI_API_BASE", "https://openai-main-eastus2.openai.azure.com/"
)
azure_api_key = os.getenv("OPENAI_API_KEY")
azure_api_version = os.getenv("OPENAI_API_VERSION", "2024-12-01-preview")


# 共有リソース
def get_llm(model: str = "gpt-4.1") -> AzureChatOpenAI:
    return AzureChatOpenAI(
        openai_api_key=azure_api_key,
        openai_api_version=azure_api_version,
        azure_endpoint=azure_endpoint,
        azure_deployment=model,
        temperature=0.0,
        timeout=30,
        max_retries=0,
    )


def get_llm_semaphore(max_concurrency: int = 8) -> asyncio.Semaphore:
    return asyncio.Semaphore(max_concurrency)


llm = get_llm()
sem = get_llm_semaphore()


# LangChain用: セマフォ+バックオフ付き非同期呼び出し
async def ainvoke_with_limit(chain: Runnable, inp: dict | str) -> str:
    delay = 0.5
    async with sem:
        for _ in range(5):
            try:
                variables = {"input": inp} if isinstance(inp, str) else inp
                return await chain.ainvoke(variables)
            except Exception as e:
                msg = str(e).lower()
                if "429" in msg or "timeout" in msg or "temporarily" in msg:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 8)
                else:
                    raise


async def run_batch_reviews(
    reviews: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """
    複数の条項審査をLangChainで並列実行
    reviews: [{"clauses": [...], "knowledge": [...]}]の形式
    """
    system_prompt = (
        "あなたは契約審査の専門家です。以下の審査対象データと審査知見をもとに、各条項ごとに懸念点(concern)と修正条文(amendment_clause)を出力してください。\n"
        "懸念点(concern)は、端的な箇条書きで提供してください。\n"
        "修正した条文(amendment_clause)は、要変更箇所を明示し、端的に示してください。\n"
        "審査の根拠とする knowledge_ids を必ず提示し、提供する審査知見以外を利用した審査は絶対にしないでください。\n"
        '審査の結果懸念がない場合は、"concern" および "amendment_clause" を null で出力してください。\n'
        "【出力形式】\n"
        "必ず以下の厳格なJSON配列形式で出力してください。\n"
        "[\n"
        "  {{\n"
        '    "clause_number": <条項番号（文字列）>,\n'
        '    "concern": <懸念点コメント> or null,\n'
        '    "amendment_clause": <修正条文> or null,\n'
        '    "knowledge_ids": [<ナレッジIDの配列>]\n'
        "  }}, ...\n"
        "]\n"
    )
    prompt_template = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", "{input}")]
    )
    chain: Runnable = prompt_template | llm | StrOutputParser()

    async def review_one(item: Dict[str, Any]) -> List[Dict[str, Any]]:
        prompt = (
            "【審査対象データ】\n"
            f"{json.dumps(item['clauses'], ensure_ascii=False)}\n"
            "【審査知見（knowledge）】\n"
            f"{json.dumps(item['knowledge'], ensure_ascii=False)}\n\n"
            "審査は提供する審査知見以外を絶対に利用しないでください。"
        )
        try:
            result = await ainvoke_with_limit(chain, prompt)
            return json.loads(result)
        except Exception as e:
            return [
                {
                    "clause_number": clause["clause_number"],
                    "concern": f"LLMエラー: {e}",
                    "amendment_clause": "",
                    "knowledge_ids": [],
                }
                for clause in item["clauses"]
            ]

    tasks = [review_one(item) for item in reviews]
    return await asyncio.gather(*tasks)


async def run_batch_summaries(summaries: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    複数の要約処理をLangChainで並列実行
    summaries: [{"clause_number": "...", "concerns": [...], "amendments": [...]}]の形式
    """
    system_prompt = (
        "あなたは契約審査の専門家です。以下の複数の指摘事項・修正条項案を統合し、重複や類似内容をまとめて簡潔にしてください。\n"
        "【出力形式】\n"
        '{{"concern": <要約した懸念点>, "amendment_clause": <統合した修正条項案>}}'
    )
    prompt_template = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", "{input}")]
    )
    chain: Runnable = prompt_template | llm | StrOutputParser()

    async def summarize_one(item: Dict[str, Any]) -> Dict[str, str]:
        prompt = (
            f"【条項番号】{item['clause_number']}\n"
            f"【指摘事項一覧】{json.dumps(item['concerns'], ensure_ascii=False)}\n"
            f"【修正文案一覧】{json.dumps(item['amendments'], ensure_ascii=False)}\n"
        )
        try:
            result = await ainvoke_with_limit(chain, prompt)
            parsed = json.loads(result)
            return {
                "concern": parsed.get("concern", ""),
                "amendment_clause": parsed.get("amendment_clause", ""),
            }
        except Exception as e:
            return {"concern": "要約エラー: " + str(e), "amendment_clause": ""}

    tasks = [summarize_one(item) for item in summaries]
    return await asyncio.gather(*tasks)


async def amatching_clause_and_knowledge(
    knowledge_all: List[Dict[str, Any]], clauses: List[Dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """
    match_cl_and_kn.pyのmatching_clause_and_knowledgeの非同期・LangChain版
    Returns:
      response        : Step1のマッピング [{"knowledge_id":..., "clause_number":[...]}...]
      clauses_augmented: Step2適用後の clauses
      trace           : デバッグ用（送信プロンプト、LLM生応答 など）
    """
    import re

    # --- 1) 入力の正規化（clause_numberは文字列化）
    for c in clauses:
        if not isinstance(c.get("clause_number"), str):
            c["clause_number"] = str(c["clause_number"])

    # --- 2) チャンク戦略（超長文対策）
    def _chunk_if_needed(
        clauses: List[Dict[str, Any]], max_chars: int = 18000
    ) -> List[List[Dict[str, Any]]]:
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

    clause_chunks = _chunk_if_needed(clauses)

    aggregate_map: dict[str, list[str]] = {k["id"]: [] for k in knowledge_all}
    trace = {"prompts": [], "raw_responses": []}

    # LangChainプロンプト
    SYSTEM_PROMPT = """あなたは日本語の契約書に精通したリーガルアシスタントです。
タスク：各 knowledge.target_clause（審査知見が対象とする条項の条件）に合致する契約条項（clause_number）を、提供された clauses から特定してください。
出力は **厳格なJSONのみ** で返します。余計な説明、コードブロック、注釈は一切含めません。

要件:
- 出力は配列。各要素は {{"knowledge_id": str, "clause_number": [str, ...]}} の形。
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
    prompt_template = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", "{input}")]
    )
    chain: Runnable = prompt_template | llm | StrOutputParser()

    def _force_json(s: str) -> Any:
        try:
            return json.loads(s)
        except Exception:
            m = re.search(r"(\[.*\])", s, flags=re.DOTALL)
            if not m:
                raise
            return json.loads(m.group(1))

    def _dedup(seq):
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
        idx_by_num = {c["clause_number"]: i for i, c in enumerate(clauses)}
        for c in clauses:
            if "knowledge_id" not in c or c["knowledge_id"] is None:
                c["knowledge_id"] = []
        for item in response:
            k_id = item["knowledge_id"]
            targets = item.get("clause_number", [])
            if not targets:
                for c in clauses:
                    c["knowledge_id"].append(k_id)
        for item in response:
            k_id = item["knowledge_id"]
            for num in item.get("clause_number", []):
                i = idx_by_num.get(num)
                if i is not None:
                    clauses[i]["knowledge_id"].append(k_id)
        for c in clauses:
            c["knowledge_id"] = _dedup(c["knowledge_id"])
        return clauses

    # --- 3) 各チャンクで判定→ユニオン（非同期並列）
    async def process_chunk(chunk, chunk_idx):
        knowledge_min = [
            {"id": k["id"], "target_clause": k["target_clause"]}
            for k in knowledge_all
            if "id" in k and "target_clause" in k
        ]
        chunk_min = [
            {"clause_number": c["clause_number"], "clause": c["clause"]}
            for c in chunk
            if "clause_number" in c and "clause" in c
        ]
        user_prompt = USER_PROMPT_TEMPLATE.format(
            knowledge_json=json.dumps(knowledge_min, ensure_ascii=False),
            clauses_json=json.dumps(chunk_min, ensure_ascii=False),
        )
        try:
            raw = await ainvoke_with_limit(chain, user_prompt)
            parsed = _force_json(raw)
        except Exception as e:
            raw = str(e)
            parsed = []
        trace["prompts"].append({"chunk": chunk_idx, "messages": user_prompt})
        trace["raw_responses"].append({"chunk": chunk_idx, "raw": raw})
        return parsed

    chunk_tasks = [process_chunk(chunk, idx) for idx, chunk in enumerate(clause_chunks)]
    chunk_results = await asyncio.gather(*chunk_tasks)

    # 正常化 & 集約
    for parsed in chunk_results:
        for item in parsed:
            k = item["knowledge_id"]
            nums = [str(n) for n in item.get("clause_number", [])]
            aggregate_map.setdefault(k, [])
            aggregate_map[k].extend(nums)

    # --- 4) knowledge_idごとに重複除去
    response: list[dict[str, Any]] = []
    all_clause_numbers = [str(c["clause_number"]) for c in clauses]
    for k in knowledge_all:
        k_id = k["id"]
        mapped = _dedup(aggregate_map.get(k_id, []))
        if not mapped:
            mapped = all_clause_numbers.copy()
        response.append({"knowledge_id": k_id, "clause_number": mapped})

    # --- 5) Step2: 付与
    clauses_augmented = _apply_step2([dict(c) for c in clauses], response)
    return response, clauses_augmented, trace
