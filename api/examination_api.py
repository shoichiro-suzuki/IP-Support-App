### examination_api.py


def examination_api(
    contract_type: str,
    background_info: str,
    partys: list,
    title: str,
    clauses: list,
    knowledge_all: list,
    llm_model: str = "gpt-4.1",
):
    """
    Streamlit用: UI部品を使わず、値を直接受け取って審査処理を行う
    Args:
        contract_type (str): 契約種別
        background_info (str): 背景情報
        partys (list): 当事者リスト
        title (str): タイトル
        clauses (list): 条文リスト（dictのリスト、各要素はclause_number, clause, review_points, action_planを含む）
    Returns:
        analyzed_clauses (list): 審査結果リスト
    """

    import os
    import json
    import asyncio
    from collections import defaultdict
    from api import async_llm_service
    from dotenv import load_dotenv

    data = {
        "contract_master_id": "",
        "contract_type": contract_type,
        "background_info": background_info,
        "partys": partys,
        "title": title,
        "clauses": [
            {
                "clause_id": c.get("clause_id", ""),
                "clause_number": c.get("clause_number", ""),
                "clause": c.get("clause", ""),
                "knowledge_id": c.get("knowledge_id", []),
            }
            for c in clauses
        ],
    }

    analyzed_clauses = []
    similar_clauses_knowledge = []

    # knowledge_idのユニーク一覧を抽出
    all_knowledge_ids = set()
    for c in data["clauses"]:
        all_knowledge_ids.update(c.get("knowledge_id", []))
    all_knowledge_ids = list(all_knowledge_ids)

    # knowledge_idごとに該当条項を抽出し、knowledge_allから該当ナレッジを取得して審査
    # ここを非同期バッチ化
    async def process_reviews():
        # LLMモデルの設定
        async_llm_service.llm = async_llm_service.get_llm(llm_model)

        review_inputs = []
        for kid in all_knowledge_ids:
            target_clauses = [
                c for c in data["clauses"] if kid in c.get("knowledge_id", [])
            ]
            target_knowledge = [k for k in knowledge_all if k.get("id") == kid]
            if not target_clauses or not target_knowledge:
                continue
            review_inputs.append(
                {"clauses": target_clauses, "knowledge": target_knowledge}
            )
        if not review_inputs:
            return defaultdict(list)
        review_results_list = await async_llm_service.run_batch_reviews(review_inputs)
        clause_results = defaultdict(list)
        for review_results in review_results_list:
            for item in review_results:
                clause_results[item["clause_number"]].append(item)
        return clause_results

    # 条項ごとに複数ナレッジの指摘事項があれば要約
    async def process_summaries(clause_results):
        summarized_clauses = []
        summary_inputs = []
        clause_map = {}
        for clause in data["clauses"]:
            num = clause["clause_number"]
            results = clause_results.get(num, [])
            if not results:
                summarized_clauses.append(
                    {
                        "clause_number": num,
                        "concern": "",
                        "amendment_clause": "",
                        "knowledge_ids": [],
                    }
                )
                continue
            concerns = [r["concern"] for r in results if r["concern"]]
            amendments = [
                r["amendment_clause"] for r in results if r["amendment_clause"]
            ]
            knowledge_ids = []
            for r in results:
                knowledge_ids.extend(r.get("knowledge_ids", []))
            if len(concerns) > 1 or len(amendments) > 1:
                summary_inputs.append(
                    {
                        "clause_number": num,
                        "concerns": concerns,
                        "amendments": amendments,
                    }
                )
                clause_map[num] = {"knowledge_ids": list(set(knowledge_ids))}
            else:
                concern_summary = concerns[0] if concerns else ""
                amendment_summary = amendments[0] if amendments else ""
                summarized_clauses.append(
                    {
                        "clause_number": num,
                        "concern": concern_summary,
                        "amendment_clause": amendment_summary,
                        "knowledge_ids": list(set(knowledge_ids)),
                    }
                )
        # 非同期要約
        if summary_inputs:
            summary_results = await async_llm_service.run_batch_summaries(
                summary_inputs
            )
            for inp, res in zip(summary_inputs, summary_results):
                summarized_clauses.append(
                    {
                        "clause_number": inp["clause_number"],
                        "concern": res.get("concern", ""),
                        "amendment_clause": res.get("amendment_clause", ""),
                        "knowledge_ids": clause_map[inp["clause_number"]][
                            "knowledge_ids"
                        ],
                    }
                )
        return summarized_clauses

    async def main_async():
        clause_results = await process_reviews()
        summarized_clauses = await process_summaries(clause_results)

        # デバッグ用:
        load_dotenv()
        debug = os.getenv("DEBUG")
        if debug:
            sample_path = os.path.join(
                os.path.dirname(__file__), "..", "Examination_data_sample.py"
            )
            sample_path = os.path.abspath(sample_path)
            with open(sample_path, "w", encoding="utf-8") as f:
                f.write("Examination_data = ")
                json.dump(data, f, ensure_ascii=False, indent=4)
                f.write("\n")
                f.write("knowledge_all = ")
                json.dump(knowledge_all, f, ensure_ascii=False, indent=4)
                f.write("\n")
                # f.write("similar_clauses_knowledge = ")
                # json.dump(similar_clauses_knowledge, f, ensure_ascii=False, indent=4)
                # f.write("\n")
                f.write("Clause_results = ")
                json.dump(clause_results, f, ensure_ascii=False, indent=4)
                f.write("\n")
                f.write("Analyzed_clauses = ")
                json.dump(summarized_clauses, f, ensure_ascii=False, indent=4)
                f.write("\n")

        return summarized_clauses

    # 非同期関数を同期関数から呼び出すためのラッパー
    return asyncio.run(main_async())


def search_similar_clauses(clauses, contract_api):
    similar_clauses_knowledge = []
    for clause in clauses:
        clause_text = clause["clause"]
        clause_number = clause["clause_number"]

        # 類似条項の検索とナレッジ抽出
        try:
            similar_clauses = contract_api.search_similar_clauses(clause_text, top_k=3)
        except Exception as e:
            print(f"Error occurred: {e}")
            continue

        # clause_numberと対応付けて、抽出した similar_clauses のclause_id, c.clause, c.review_points, c.action_plan,を格納する
        similar_clauses_knowledge.append(
            {
                "clause_number": clause_number,
                "similar_clauses": [
                    {
                        "clause_id": c["clause_id"],
                        "clause": c["clause"],
                        "review_points": c["review_points"],
                        "action_plan": c["action_plan"],
                    }
                    for c in similar_clauses
                ],
            }
        )
