import json

import streamlit as st
from api.knowledge_api import KnowledgeAPI

st.set_page_config(page_title="ナレッジ生成/修正（LLMモック）", layout="wide")

# データロード
if "knowledge_api" not in st.session_state:
    st.session_state["knowledge_api"] = KnowledgeAPI()
if "knowledge_all" not in st.session_state:
    try:
        st.session_state["knowledge_all"] = st.session_state[
            "knowledge_api"
        ].get_knowledge_list()
    except Exception:
        st.session_state["knowledge_all"] = []
st.session_state.setdefault("knowledge_llm_selected", [])

st.title("ナレッジ生成/修正（モックUI）")
st.caption("LLM呼び出しなし。ナレッジ選択/修正タブのみ実装、生成タブは後続。")

tab_select, tab_generate = st.tabs(["ナレッジ選択", "ナレッジ生成（モック）"])


def _search_text(items, query):
    q = query.lower()
    hits = []
    for k in items:
        blob = " ".join(
            str(k.get(f, ""))
            for f in [
                "knowledge_title",
                "target_clause",
                "review_points",
                "action_plan",
                "clause_sample",
            ]
        ).lower()
        if q in blob:
            hits.append(k)
    return hits


with tab_select:
    st.subheader("ナレッジ指定")
    method = st.radio(
        "選択方法",
        [
            "テキスト検索",
            "ベクトル検索（モック・フィルタ方式）",
        ],
        horizontal=True,
    )

    knowledge_all = st.session_state["knowledge_all"]
    selected_ids = set(st.session_state.get("knowledge_llm_selected", []))
    if method == "テキスト検索":
        filter_text = st.text_input(
            "テキストフィルタ（タイトル/対象条項/審査観点/対応策/条項サンプル）",
            placeholder="キーワードで絞り込み",
        )
        filtered = (
            _search_text(knowledge_all, filter_text) if filter_text else knowledge_all
        )
    else:
        filter_text = st.text_input(
            "ベクトル検索クエリ（モック・フィルタ方式）",
            placeholder="類似検索キーワードで候補を絞り込み",
        )
        filtered = (
            _search_text(knowledge_all, filter_text) if filter_text else knowledge_all
        )

    options = [
        f"No.{k.get('knowledge_number')} {k.get('knowledge_title','')}"
        for k in filtered
    ]
    picked = st.multiselect(
        f"ナレッジを選択（{len(filtered)}件中）", options, default=[]
    )
    chosen_numbers = {int(lbl.split(" ")[0].replace("No.", "")) for lbl in picked}
    filtered_ids = {k.get("id") for k in filtered}
    new_selected = {
        k.get("id") for k in filtered if k.get("knowledge_number") in chosen_numbers
    }
    # フィルタに出ているものは選択を置き換え、フィルタ外の既存選択は維持
    selected_ids = (selected_ids - filtered_ids) | new_selected

    st.markdown("---")
    display_items = [
        k for k in knowledge_all if str(k.get("id")) in {str(x) for x in selected_ids}
    ]
    st.write(f"選択済み: {len(display_items)} 件")
    for idx, k in enumerate(display_items):
        kn_id = k.get("id", f"tmp-{idx}")
        label = f"No.{k.get('knowledge_number')} {k.get('knowledge_title','')}"
        with st.expander(label, expanded=False):
            st.markdown(f"**対象条項**: {k.get('target_clause','')}")
            st.markdown(f"**審査観点**: {k.get('review_points','')}")
            st.markdown(f"**対応策**: {k.get('action_plan','')}")
            st.markdown(f"**条項サンプル**: {k.get('clause_sample','')}")
    st.session_state["knowledge_llm_selected"] = list(selected_ids)

with tab_generate:
    st.subheader("入力コンテキスト")
    col1, col2 = st.columns(2)
    contract_title = col1.text_input("契約タイトル", placeholder="〇〇基本契約")
    contract_type = col1.text_input("契約種別", value="汎用")
    parties = col2.text_input("当事者", placeholder="甲: A社 / 乙: B社")
    background = col2.text_area("背景", height=80)

    clause_number = st.text_input("対象条文番号", placeholder="例: 第10条（責任）")
    clause_body = st.text_area("対象条文本文", height=160)

    selected_items = [
        k
        for k in st.session_state["knowledge_all"]
        if k.get("id") in st.session_state.get("knowledge_llm_selected", [])
    ]
    ref_note = st.text_area("参考ナレッジ追加入力（任意）", height=120)

    st.caption("選択済みナレッジ（コピー用JSON）")
    st.code(
        json.dumps(
            [
                {
                    "knowledge_number": k.get("knowledge_number"),
                    "knowledge_title": k.get("knowledge_title"),
                    "target_clause": k.get("target_clause"),
                    "review_points": k.get("review_points"),
                    "action_plan": k.get("action_plan"),
                    "clause_sample": k.get("clause_sample"),
                }
                for k in selected_items
            ],
            ensure_ascii=False,
            indent=2,
        )
    )

    system_prompt = (
        "あなたは契約ナレッジ編集者。入力コンテキストのみを根拠に既存フォーマットでドラフトを返す。\n"
        "推測/補完禁止。足りない項目は空文字。日本語で簡潔に。前置き/結論は不要。"
    )
    contract_info = {
        "title": contract_title,
        "contract_type": contract_type,
        "parties": parties,
        "background": background,
    }
    clauses = [{"number": clause_number, "text": clause_body}]
    knowledge_refs = {"selected": selected_items} if selected_items else {}
    if ref_note.strip():
        knowledge_refs["notes"] = ref_note.strip()

    user_prompt = (
        "以下コンテキストを踏まえ、ナレッジ下書きをJSONで返して。説明文やコードブロックは不要。\n"
        "[契約基本情報]\n"
        f"{json.dumps(contract_info, ensure_ascii=False, indent=2)}\n"
        "[対象条文]\n"
        f"{json.dumps(clauses, ensure_ascii=False, indent=2)}\n"
        "[参考ナレッジ（任意）]\n"
        f"{json.dumps(knowledge_refs or {}, ensure_ascii=False, indent=2)}"
    )

    st.markdown("---")
    st.subheader("LLM送信用プロンプト（プレビュー）")
    st.markdown("**System**")
    st.code(system_prompt)
    st.markdown("**User**")
    st.code(user_prompt)

    st.markdown("---")
    st.subheader("生成結果（モック）")
    if st.button("下書きをモック生成"):
        target_clause = (
            f"{clause_number} {clause_body}".strip()
            if clause_number or clause_body
            else ""
        )
        review_points = "- 条文要件と契約背景の整合性を確認（モック）"
        if background:
            review_points += f"\n- 背景: {background}"
        action_plan = "- 条文案を調整し、当事者と整合を確認（モック）"
        if ref_note:
            action_plan += "\n- 参考ナレッジに基づき差分チェック"
        draft = {
            "knowledge_title": contract_title or "ドラフトタイトル（モック）",
            "target_clause": target_clause,
            "review_points": review_points,
            "action_plan": action_plan,
            "clause_sample": clause_body[:200]
            or "修正文案をここに追記（モック）",
            "contract_type": contract_type or "汎用",
        }
        st.json(draft)
