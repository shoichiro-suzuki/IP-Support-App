### examination.py

import streamlit as st
import asyncio
import json
from api.contract_api import ContractAPI
from api.knowledge_api import KnowledgeAPI
from api.examination_api import examination_api
from api import async_llm_service
from services.document_input import extract_text_from_document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
import tempfile
import os
from datetime import datetime

st.set_page_config(layout="wide")


def export_knowledge_to_csv(knowledge_data):
    """
    ナレッジデータをCSV形式に変換（BOM付きUTF-8）

    Args:
        knowledge_data: st.session_state["knowledge_all"]のデータ

    Returns:
        BOM付きUTF-8でエンコードされたCSVバイト文字列
    """
    import csv
    import io

    # CSVヘッダー定義（元データの構造に合わせて修正）
    headers = [
        "knowledge_number",
        "version",
        "contract_type",
        "target_clause",
        "knowledge_title",
        "review_points",
        "action_plan",
        "clause_sample",
        "record_status",
        "approval_status",
        "id",
        "created_at",
        "updated_at",
    ]

    # CSV書き込み処理
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, quoting=csv.QUOTE_ALL)
    writer.writeheader()

    for knowledge in knowledge_data:
        # データをクリーンアップしてCSV形式に適合させる
        row = {}
        for header in headers:
            value = knowledge.get(header, "")
            if isinstance(value, str):
                # ダブルクォートを除去し、改行文字をスペースに変換
                value = (
                    value.strip('"')
                    .replace("\n", " ")
                    .replace("\r", "")
                    .replace("\\n", " ")
                )
            row[header] = value
        writer.writerow(row)

    # BOM付きUTF-8でエンコード
    csv_string = output.getvalue()
    return csv_string.encode("utf-8-sig")


def reset_review_status():
    """審査状態をリセットする"""
    st.session_state["clause_review_status"] = {}
    if "analyzed_clauses" in st.session_state:
        del st.session_state["analyzed_clauses"]


def initialize_clause_status(clauses):
    """条項リストから初期状態を設定"""
    status_dict = {"前文": "unreviewed"}  # 前文を含む
    for clause in clauses:
        clause_number = clause.get("clause_number", "")
        if clause_number:
            status_dict[clause_number] = "unreviewed"
    st.session_state["clause_review_status"] = status_dict


def update_review_status_from_analysis(analyzed_clauses):
    """審査結果から状態を更新"""
    for analyzed in analyzed_clauses:
        clause_number = analyzed.get("clause_number", "")
        has_concern = bool(analyzed.get("amendment_clause"))

        if clause_number in st.session_state["clause_review_status"]:
            if has_concern:
                st.session_state["clause_review_status"][
                    clause_number
                ] = "reviewed_concern"
            else:
                st.session_state["clause_review_status"][
                    clause_number
                ] = "reviewed_safe"


def get_clause_label(clause_number, clause_review_status, analyzed_clauses=None):
    """
    条項番号と状態に基づいてexpanderラベルを生成

    Args:
        clause_number: 条項番号
        clause_review_status: 審査状態辞書
        analyzed_clauses: 審査結果リスト

    Returns:
        tuple: (ラベル文字列, 展開状態のbool)
    """
    status = clause_review_status.get(clause_number, "unreviewed")

    if status == "unreviewed":
        return f"{clause_number} - 🔍未審査", False
    elif status == "reviewed_safe":
        return f"{clause_number} - ✅懸念事項なし", False
    elif status == "reviewed_concern":
        return f"{clause_number} - ❌懸念事項あり", True

    return f"{clause_number}", False


def build_chat_context():
    """チャット用に必要なコンテキストを収集（対象条文/審査結果/ナレッジ/契約基本情報を生データで付与）"""
    clauses = [
        {
            "clause_number": "前文",
            "clause": st.session_state.get("exam_intro", ""),
        }
    ]
    for idx, clause in enumerate(st.session_state.get("exam_clauses", [])):
        clauses.append(
            {
                "clause_number": st.session_state.get(
                    f"exam_clause_number_{idx}", clause.get("clause_number", "")
                ),
                "clause": st.session_state.get(
                    f"exam_clause_{idx}", clause.get("clause", "")
                ),
            }
        )

    # ナレッジから必要なフィールドのみを抽出（ベクトルデータを除外）
    knowledge_all = st.session_state.get("knowledge_all", [])
    essential_fields = [
        "knowledge_number",
        "contract_type",
        "target_clause",
        "knowledge_title",
        "review_points",
        "action_plan",
        "clause_sample",
    ]
    filtered_knowledge = [
        {field: kn.get(field, "") for field in essential_fields}
        for kn in knowledge_all
    ]

    return {
        "contract_info": {
            "title": st.session_state.get("exam_title", ""),
            "contract_type": st.session_state.get("exam_contract_type", ""),
            "partys": st.session_state.get("exam_partys", ""),
            "background": st.session_state.get("exam_background", ""),
        },
        "clauses": clauses,
        "analysis": st.session_state.get("analyzed_clauses", []),
        "knowledge": filtered_knowledge,
    }


async def run_examination_chat(prompt: str, llm_model: str) -> str:
    """サイドバーでの審査チャット呼び出し"""
    context = build_chat_context()
    system_prompt = (
        "あなたは契約審査アシスタントです。"
        "以下のコンテキスト（対象条文、審査結果、ナレッジ、契約基本情報）が全てです。"
        "コンテキストに含まれない前提は置かず、日本語で回答してください。"
    )
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "質問:\n{question}\n\nコンテキスト:\n{context_json}"),
        ]
    )
    chain = (
        prompt_template
        | async_llm_service.get_llm(llm_model)
        | StrOutputParser()
    )
    return await async_llm_service.ainvoke_with_limit(
        chain,
        {
            "question": prompt,
            "context_json": json.dumps(context, ensure_ascii=False),
        },
    )


def render_sidebar_controls():
    """サイドバーに審査操作コントロールを表示"""
    with st.sidebar:
        st.header("審査操作")

        # LLMモデル選択
        llm_model = st.selectbox(
            "LLMモデル",
            [
                "gpt-4.1",
                "gpt-4.1-mini",
                "gpt-5-mini",
                "gpt-5-nano",
                "gpt-5",
            ],
            key="sidebar_llm_model",
        )

        # 審査開始ボタン（条件付き表示）
        if st.session_state["exam_page_status"] in ["document_loaded", "examination"]:
            return st.button("審査開始", type="primary"), llm_model

        return False, llm_model


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
    if "no_target_knowledges" not in st.session_state:
        st.session_state["no_target_knowledges"] = []
    if "clause_review_status" not in st.session_state:
        st.session_state["clause_review_status"] = {}
    if "last_uploaded_file" not in st.session_state:
        st.session_state["last_uploaded_file"] = None

    # サイドバーコントロールの表示
    # sidebar_start_review, llm_model = render_sidebar_controls()

    # --- file upload -----------------------------------------------------------
    uploaded = st.file_uploader(
        "契約ファイル選択", type=[".docx", ".pdf"], accept_multiple_files=False
    )

    # ファイル再読み込み時の状態リセット処理
    if uploaded is not None and uploaded != st.session_state.get("last_uploaded_file"):
        reset_review_status()
        st.session_state["last_uploaded_file"] = uploaded

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
                        # 条項状態を初期化
                        initialize_clause_status(st.session_state["exam_clauses"])
                except Exception as e:
                    st.error(f"解析に失敗しました: {e}")
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    st.rerun()
        else:
            st.warning("ファイルを選択してください。")
    st.markdown("---")

    if (
        st.session_state["exam_page_status"] == "document_loaded"
        or st.session_state["exam_page_status"] == "examination"
    ):
        # ナレッジ未ロード時は続行しない
        if not st.session_state.get("knowledge_all"):
            st.error("ナレッジが取得できませんでした。再読み込み後も改善しない場合は接続設定を確認してください。")
            return

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
        intro_analyzed = None
        if st.session_state.get("analyzed_clauses"):
            for analyzed in st.session_state["analyzed_clauses"]:
                if analyzed.get("clause_number") == "前文":
                    intro_analyzed = analyzed
                    break

        # expanderの展開状態を決定
        intro_has_amendment = intro_analyzed and bool(
            intro_analyzed.get("amendment_clause")
        )
        intro_expanded = bool(intro_has_amendment)  # 懸念事項があるときは展開状態

        # expanderのラベルを決定
        intro_label, intro_expanded = get_clause_label(
            "前文",
            st.session_state["clause_review_status"],
            st.session_state.get("analyzed_clauses"),
        )
        # 懸念事項がある場合は展開状態を上書き
        if intro_has_amendment:
            intro_expanded = True

        with st.expander(intro_label, expanded=intro_expanded):
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
                if intro_analyzed:
                    call_analyze_function(intro_analyzed)

        # 通常の条項リスト
        for idx, clause in enumerate(st.session_state["exam_clauses"]):
            # 対応する審査結果を検索
            clause_analyzed = None
            if st.session_state.get("analyzed_clauses"):
                for analyzed in st.session_state["analyzed_clauses"]:
                    if analyzed.get("clause_number") == clause.get("clause_number"):
                        clause_analyzed = analyzed
                        break

            # expanderの展開状態を決定
            clause_has_amendment = clause_analyzed and bool(
                clause_analyzed.get("amendment_clause")
            )
            clause_expanded = bool(clause_has_amendment)  # 懸念事項があるときは展開状態

            # expanderのラベルを決定
            clause_number = clause.get("clause_number", "")
            clause_label, clause_expanded = get_clause_label(
                clause_number,
                st.session_state["clause_review_status"],
                st.session_state.get("analyzed_clauses"),
            )
            # 懸念事項がある場合は展開状態を上書き
            if clause_has_amendment:
                clause_expanded = True

            with st.expander(clause_label, expanded=clause_expanded):
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
                    if clause_analyzed:
                        call_analyze_function(clause_analyzed)

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

        # --- action buttons (サイドバーに移動) -------------------------------------------------------
        # サイドバーからの審査開始フラグをチェック

        with st.sidebar:
            st.header("審査操作")

            # LLMモデル選択
            llm_model = st.selectbox(
                "LLMモデル",
                [
                    "gpt-4.1",
                    "gpt-4.1-mini",
                    "gpt-5-mini",
                    "gpt-5-nano",
                    "gpt-5",
                ],
                key="sidebar_llm_model",
            )

            # 審査開始ボタン（条件付き表示）
            if st.button("審査開始", type="primary"):
                with st.spinner("審査中...", show_time=True):
                    contract_type = st.session_state["exam_contract_type"]
                    background_info = st.session_state["exam_background"]
                    partys = [
                        p.strip()
                        for p in st.session_state["exam_partys"].split(",")
                        if p.strip()
                    ]
                    title = st.session_state["exam_title"]
                    clauses = collect_exam_clauses()
                    # knowledgeとclauseのマッピング結果を取得
                    try:
                        mapping_response, clauses_augmented, _ = asyncio.run(
                            async_llm_service.amatching_clause_and_knowledge(
                                st.session_state["knowledge_all"], clauses
                            )
                        )
                    except Exception as e:
                        st.error(f"ナレッジマッピングでエラーが発生しました: {e}")
                        return

                    # マッピング結果が全て空なら警告して終了
                    mapped_total = sum(
                        len(m.get("clause_number", [])) for m in mapping_response or []
                    )
                    if mapped_total == 0:
                        st.warning("ナレッジと条項の対応付けができませんでした。対象条項条件や入力条文を確認してください。")
                        return

                    # 関連条項が無いナレッジを抽出
                    no_target_knowledges = []
                    for m in mapping_response:
                        if not m.get("clause_number"):
                            kid = m["knowledge_id"]
                            kn = next(
                                (
                                    k
                                    for k in st.session_state["knowledge_all"]
                                    if str(k.get("id")) == str(kid)
                                ),
                                None,
                            )
                            if kn:
                                no_target_knowledges.append(kn)
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
                            # 審査結果から状態を更新
                            update_review_status_from_analysis(analyzed_clauses)
                            st.session_state["exam_page_status"] = "examination"
                            st.session_state["no_target_knowledges"] = (
                                no_target_knowledges
                            )
                            st.rerun()
                    except Exception as e:
                        st.error(f"審査処理でエラーが発生しました: {e}")
            st.markdown("---")
            st.subheader("審査チャット")

            # チャット履歴リセットボタン
            if st.button("🗑️ 履歴リセット", help="チャット履歴をクリアします"):
                st.session_state["exam_chat_history"] = []
                st.rerun()

            chat_box = st.container(border=True)
            for msg in st.session_state["exam_chat_history"]:
                chat_box.chat_message(msg["role"]).write(msg["content"])

            if prompt := st.chat_input("質問を入力", key="exam_chat_input"):
                st.session_state["exam_chat_history"].append(
                    {"role": "user", "content": prompt}
                )
                try:
                    reply = asyncio.run(run_examination_chat(prompt, llm_model))
                    # None チェック（防御的処理）
                    if reply is None:
                        reply = "エラーが発生しました: LLMからの応答がありませんでした"
                except Exception as e:
                    reply = f"エラーが発生しました: {e}"
                st.session_state["exam_chat_history"].append(
                    {"role": "assistant", "content": reply}
                )
                st.rerun()
    if st.session_state["exam_page_status"] == "examination":
        st.success("審査結果を表示しました。")
        # 関連条項が無いナレッジを審査結果の後に表示
        no_target_knowledges = st.session_state.get("no_target_knowledges", [])
        if no_target_knowledges:
            st.markdown("---")
            st.subheader("関連条項が無いナレッジ")
            for kn in no_target_knowledges:
                knowledge_number = kn.get("knowledge_number", "")
                with st.expander(
                    f"ナレッジNo.{knowledge_number} (該当条項なし)", expanded=False
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
        with st.sidebar:
            now = str(datetime.now().strftime("%Y%m%d%H%M%S"))

            # CSV出力用のデータを準備
            def collect_exam_clauses_for_csv():
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

            csv_data = api.export_examination_result_to_csv(
                analyzed_clauses=st.session_state.get("analyzed_clauses", []),
                original_clauses=collect_exam_clauses_for_csv(),
                contract_info={
                    "title": st.session_state.get("exam_title", ""),
                    "contract_type": st.session_state.get("exam_contract_type", ""),
                    "partys": st.session_state.get("exam_partys", ""),
                    "background": st.session_state.get("exam_background", ""),
                },
                clause_review_status=st.session_state.get("clause_review_status", {}),
                examination_datetime=now,
                llm_model=st.session_state.get("sidebar_llm_model", "gpt-4.1"),
            )

            st.download_button(
                "審査結果 Download",
                data=csv_data,
                file_name=f"審査結果_{now}.csv",
                mime="text/csv",
            )

            # ナレッジデータダウンロード機能
            knowledge_csv_data = export_knowledge_to_csv(
                st.session_state["knowledge_all"]
            )
            st.download_button(
                "ナレッジ Download",
                data=knowledge_csv_data,
                file_name=f"ナレッジデータ_{now}.csv",
                mime="text/csv",
            )


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
