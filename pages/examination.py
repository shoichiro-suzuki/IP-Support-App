### examination.py

import streamlit as st
import asyncio
from api.contract_api import ContractAPI
from api.knowledge_api import KnowledgeAPI
from api.examination_api import examination_api
from api import async_llm_service
from services.document_input import extract_text_from_document
import tempfile
import os

st.set_page_config(layout="wide")


def main():
    st.title("契約審査")
    if "contract_api" not in st.session_state:
        st.session_state["contract_api"] = ContractAPI()
    api = st.session_state["contract_api"]
    if "knowledge_api" not in st.session_state:
        st.session_state["knowledge_api"] = KnowledgeAPI()
    if "knowledge_all" not in st.session_state:
        try:
            kn_api = st.session_state["knowledge_api"]
            st.session_state["knowledge_all"] = kn_api.get_knowledge_list()
        except Exception:
            st.session_state["knowledge_all"] = []

    # --- state initialization --------------------------------------------------
    if "exam_contract_id" not in st.session_state:
        st.session_state["exam_contract_id"] = None
    if "exam_contract_type" not in st.session_state:
        st.session_state["exam_contract_type"] = ""
    if "exam_partys" not in st.session_state:
        st.session_state["exam_partys"] = ""
    if "exam_background" not in st.session_state:
        st.session_state["exam_background"] = ""
    if "exam_title" not in st.session_state:
        st.session_state["exam_title"] = ""
    if "exam_clauses" not in st.session_state:
        st.session_state["exam_clauses"] = []
    if "exam_intro" not in st.session_state:
        st.session_state["exam_intro"] = ""
    if "exam_page_status" not in st.session_state:
        st.session_state["exam_page_status"] = "start"

    # --- file upload -----------------------------------------------------------
    uploaded = st.file_uploader(
        "契約ファイル選択", type=[".docx", ".pdf"], accept_multiple_files=False
    )
    if st.button("契約案から条文抽出", disabled=uploaded is None):
        if uploaded is not None:
            with st.spinner("解析中...", show_time=True):
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=os.path.splitext(uploaded.name)[1]
                ) as tmp_file:
                    tmp_file.write(uploaded.read())
                    tmp_path = tmp_file.name
                try:
                    result = extract_text_from_document(tmp_path)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state["exam_title"] = result.get("title", "")
                        st.session_state["exam_intro"] = result.get("introduction", "")
                        st.session_state["exam_clauses"] = [
                            {
                                "clause_number": c.get("clause_number", ""),
                                "clause": c.get("text", ""),
                                "review_points": "",
                                "action_plan": "",
                            }
                            for c in result.get("clauses", [])
                        ]
                        st.session_state["exam_signature_section"] = result.get(
                            "signature_section", ""
                        )
                        st.session_state["exam_attachments"] = result.get(
                            "attachments", ""
                        )
                        st.success("解析完了")
                        st.session_state["exam_page_status"] = "document_loaded"
                except Exception as e:
                    st.error(f"解析に失敗しました: {e}")
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
        else:
            st.warning("ファイルを選択してください。")
    st.markdown("---")

    if (
        st.session_state["exam_page_status"] == "document_loaded"
        or st.session_state["exam_page_status"] == "examination"
    ):
        col_partys, col_contract_type = st.columns([2, 1])
        # --- contract type ---------------------------------------------------------
        with col_contract_type:
            if "exam_contract_types" not in st.session_state:
                try:
                    st.session_state["exam_contract_types"] = api.get_contract_types()
                except Exception:
                    st.session_state["exam_contract_types"] = []
            contract_types = st.session_state["exam_contract_types"]
            try:
                type_map = {
                    t.get("contract_type", ""): t.get("id")
                    for t in contract_types
                    if isinstance(t, dict) and t.get("contract_type")
                }
                if not type_map:
                    raise ValueError("no contract types")
            except Exception:
                type_map = {"汎用": None}
            current_type = st.selectbox(
                "契約種別", list(type_map.keys()), key="exam_contract_type"
            )

        # --- basic information -----------------------------------------------------
        with col_partys:
            st.text_input(
                "契約当事者（カンマ区切り）",
                key="exam_partys",
                placeholder="例: 甲社,乙社",
            )

        col_title, col_background = st.columns([1, 3])
        with col_title:
            st.text_input("タイトル", key="exam_title")
        with col_background:
            st.text_area("背景情報", height=75, key="exam_background")

        # --- introductionを条項リストの1つ目として表示 ---
        st.subheader("条文")
        # introduction部分
        col_intro_num, col_intro_clause = st.columns([1, 9])
        with col_intro_num:
            st.text_input(
                "条項番号",
                value="前文",
                key="exam_clause_number_intro",
                disabled=True,
            )
        with col_intro_clause:
            st.text_area(
                "条文",
                value=st.session_state.get("exam_intro", ""),
                key="exam_clause_intro",
                height="content",
            )
            # 審査結果（懸念事項）の表示（introduction用）
            if st.session_state.get("analyzed_clauses"):
                for analyzed in st.session_state["analyzed_clauses"]:
                    if analyzed.get("clause_number") == "前文":
                        call_analyze_function(analyzed)
        st.markdown("---")

        # 通常の条項リスト
        for idx, clause in enumerate(st.session_state["exam_clauses"]):
            col_num, col_clause = st.columns([1, 9])
            with col_num:
                st.text_input(
                    "条項番号",
                    value=clause.get("clause_number", ""),
                    key=f"exam_clause_number_{idx}",
                )
            with col_clause:
                st.text_area(
                    "条文",
                    clause.get("clause", ""),
                    key=f"exam_clause_{idx}",
                    height="content",
                )

                # 審査結果（懸念事項）の表示
                if st.session_state.get("analyzed_clauses"):
                    for analyzed in st.session_state["analyzed_clauses"]:
                        if analyzed.get("clause_number") == clause.get("clause_number"):
                            call_analyze_function(analyzed)

            st.markdown("---")

        def collect_exam_clauses():
            clauses = []
            intro_clause = {
                "clause_number": "前文",
                "clause": st.session_state.get("exam_intro", ""),
            }
            clauses.append(intro_clause)
            for idx in range(len(st.session_state["exam_clauses"])):
                clauses.append(
                    {
                        "clause_number": st.session_state.get(
                            f"exam_clause_number_{idx}", ""
                        ),
                        "clause": st.session_state.get(f"exam_clause_{idx}", ""),
                    }
                )
            return clauses

        # --- action buttons -------------------------------------------------------
        llm_model = st.selectbox(
            "LLMモデル",
            [
                "gpt-4.1",
                "gpt-4.1-mini",
                "gpt-5-mini",
                "gpt-5-nano",
                "gpt-5",
            ],
        )
        exam_clicked = st.button("審査開始")

        if exam_clicked:
            contract_type = st.session_state["exam_contract_type"]
            background_info = st.session_state["exam_background"]
            partys = [
                p.strip()
                for p in st.session_state["exam_partys"].split(",")
                if p.strip()
            ]
            title = st.session_state["exam_title"]
            clauses = collect_exam_clauses()
            _, clauses_augmented, _ = asyncio.run(
                async_llm_service.amatching_clause_and_knowledge(
                    st.session_state["knowledge_all"], clauses
                )
            )
            with st.spinner("審査中...", show_time=True):
                try:
                    analyzed_clauses = examination_api(
                        contract_type=contract_type,
                        background_info=background_info,
                        partys=partys,
                        title=title,
                        clauses=clauses_augmented,
                        knowledge_all=st.session_state["knowledge_all"],
                        llm_model=llm_model,
                    )
                    if not analyzed_clauses:
                        st.info("審査結果がありません。")
                    else:
                        st.session_state["analyzed_clauses"] = analyzed_clauses
                        st.session_state["exam_page_status"] = "examination"
                        st.rerun()
                except Exception as e:
                    st.error(f"審査処理でエラーが発生しました: {e}")
    if st.session_state["exam_page_status"] == "examination":
        st.success("審査結果を表示しました。")


def call_analyze_function(analyzed):
    if analyzed.get("amendment_clause"):
        st.markdown("---")
        col1, col2 = st.columns([1, 9])
        with col1:
            st.markdown("**修正条文：**")
        with col2:
            amendment_clause = analyzed.get("amendment_clause", "")
            if isinstance(amendment_clause, list):
                amendment_clause = "\n".join(str(x) for x in amendment_clause)
            st.markdown(
                amendment_clause.replace("\n", "<br>"),
                unsafe_allow_html=True,
            )
        col1, col2 = st.columns([1, 9])
        with col1:
            st.markdown("**懸念事項：**")
        with col2:
            concern = analyzed.get("concern", "")
            if isinstance(concern, list):
                concern = "\n".join(str(x) for x in concern)
            st.markdown(
                concern.replace("\n", "<br>"),
                unsafe_allow_html=True,
            )
    else:
        st.markdown("---")
        st.markdown("懸念事項なし")
    col1, col2 = st.columns([1, 9])
    with col1:
        st.markdown("**ナレッジ：**")
    with col2:
        knowledge_ids = analyzed.get("knowledge_ids", "")
        if not knowledge_ids:
            st.markdown("該当ナレッジなし")
        else:
            if not isinstance(knowledge_ids, list):
                knowledge_ids = [knowledge_ids]
            knowledge_all = st.session_state.get("knowledge_all", [])
            for kid in knowledge_ids:
                kn = next(
                    (k for k in knowledge_all if str(k.get("id")) == str(kid)),
                    None,
                )
                if kn:
                    knowledge_number = kn.get("knowledge_number", "")
                    with st.container():
                        with st.expander(
                            f"ナレッジNo.{knowledge_number}",
                            expanded=False,
                        ):
                            st.markdown(
                                f"<b>■ 対象条項</b>:<br>{kn.get('target_clause', '')}",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                f"<b>■ 審査観点</b>:<br>{kn.get('review_points', '').replace(chr(10), '<br>')}",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                f"<b>■ 対応策</b>:<br>{kn.get('action_plan', '').replace(chr(10), '<br>')}",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                f"<b>■ 条項サンプル</b>:<br>{kn.get('clause_sample', '').replace(chr(10), '<br>')}",
                                unsafe_allow_html=True,
                            )
                else:
                    st.markdown(
                        f"ID: {kid} のナレッジが見つかりません",
                        unsafe_allow_html=True,
                    )


if __name__ == "__main__":
    main()
