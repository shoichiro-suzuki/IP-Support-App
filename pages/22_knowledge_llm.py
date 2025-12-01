import json

import streamlit as st
from api.knowledge_api import KnowledgeAPI

st.set_page_config(page_title="ナレッジ生成/修正（LLMモック-開発中）", layout="wide")

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
    # サイドバー: 選択済みナレッジと生成結果
    selected_items = [
        k
        for k in st.session_state["knowledge_all"]
        if k.get("id") in st.session_state.get("knowledge_llm_selected", [])
    ]
    selected_export = [
        {
            "contract_type": k.get("contract_type"),
            "target_clause": k.get("target_clause"),
            "knowledge_title": k.get("knowledge_title"),
            "review_points": k.get("review_points"),
            "action_plan": k.get("action_plan"),
            "clause_sample": k.get("clause_sample"),
        }
        for k in selected_items
    ]
    sidebar = st.sidebar
    sidebar.subheader("選択済みナレッジ")
    for idx, k in enumerate(selected_export):
        label = f"選択ナレッジ {idx+1}: {k.get('knowledge_title','')}"
        with sidebar.expander(label, expanded=False):
            st.markdown(f"**契約種別**: {k.get('contract_type','')}")
            st.markdown(f"**対象条項**: {k.get('target_clause','')}")
            st.markdown(f"**審査観点**: {k.get('review_points','')}")
            st.markdown(f"**対応策**: {k.get('action_plan','')}")
            st.markdown(f"**条項サンプル**: {k.get('clause_sample','')}")

    sidebar.markdown("---")
    sidebar.subheader("ナレッジ生成結果（モック）")
    last_user_msg = next(
        (
            m
            for m in reversed(st.session_state.get("knowledge_chat", []))
            if m["role"] == "user"
        ),
        None,
    )
    if sidebar.button("ナレッジ再生成（モック）"):
        user_hint = last_user_msg["content"] if last_user_msg else ""
        file_texts = last_user_msg.get("file_texts", []) if last_user_msg else []
        merged_files = "\n".join(t[:200] for t in file_texts if t)
        merged_clause = (merged_files + "\n" + user_hint).strip()
        draft = {
            "knowledge_title": (
                (
                    last_user_msg.get("file_names", [None])[0]
                    or "ドラフトタイトル（モック）"
                )
                if last_user_msg
                else "ドラフトタイトル（モック）"
            ),
            "target_clause": merged_clause,
            "review_points": "- チャット指示と添付に基づき審査観点を整理（モック）",
            "action_plan": "- 修正方針を踏まえて条文案を更新（モック）",
            "clause_sample": merged_clause or "修正文案をここに追記（モック）",
            "contract_type": (
                selected_export[0].get("contract_type") if selected_export else "汎用"
            ),
        }
        if user_hint:
            draft["review_points"] += f"\n- 指示: {user_hint[:200]}"
        if selected_export:
            draft["action_plan"] += "\n- 既存ナレッジとの差分を確認"
        sidebar.json(draft)

    # メイン: チャット欄
    st.subheader("チャット（修正方針入力）")
    st.caption("st.chat_inputでテキスト/添付を送信（LLMモック）")

    st.session_state.setdefault("knowledge_chat", [])

    for msg in st.session_state["knowledge_chat"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("file_names"):
                st.caption(f"添付: {', '.join(msg['file_names'])}")

    submission = st.chat_input(
        "修正方針や追加入力を送信（添付可）",
        accept_file=True,
        file_type=["txt", "md", "pdf", "docx"],
    )
    if submission:
        if isinstance(submission, str):
            user_text = submission
            files = []
        else:
            user_text = getattr(submission, "text", "") or ""
            files = getattr(submission, "files", []) or []
        file_names = [f.name for f in files]
        file_texts = []
        for f in files:
            try:
                file_texts.append(f.getvalue().decode("utf-8", errors="ignore"))
            except Exception:
                file_texts.append("")
        st.session_state["knowledge_chat"].append(
            {
                "role": "user",
                "content": user_text or "",
                "file_names": file_names,
                "file_texts": file_texts,
            }
        )
        st.session_state["knowledge_chat"].append(
            {
                "role": "assistant",
                "content": "LLMモック: 指示を受領しました。サイドバーで再生成してください。",
            }
        )
        st.rerun()
