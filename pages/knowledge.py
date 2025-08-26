# 先頭の import 群はあなたのままでOK
import streamlit as st
from api.knowledge_api import KnowledgeAPI
from collections import deque
import math

st.set_page_config(layout="wide")

PAGE_SIZE_DEFAULT = 5  # 1ページの件数


def apply_filters(all_items, ctype: str, q: str):
    """契約種別とテキストで絞り込み"""
    q = (q or "").strip().lower()

    def hit(k):
        if ctype and ctype != "すべて" and k.get("contract_type") != ctype:
            return False
        if not q:
            return True
        blob = " ".join(
            str(k.get(f, ""))
            for f in [
                "knowledge_number",
                "knowledge_title",
                "review_points",
                "action_plan",
                "clause_sample",
                "target_clause",
            ]
        ).lower()
        return q in blob

    return [k for k in all_items if hit(k)]


def paginate(items, page: int, page_size: int):
    total = len(items)
    max_page = max(1, math.ceil(total / page_size))
    page = max(1, min(page, max_page))
    start = (page - 1) * page_size
    end = min(start + page_size, total)
    return items[start:end], page, max_page, start, end, total


def knowledge_label(k, highlight=False):
    base = f"No: {k.get('knowledge_number')}　{(k.get('knowledge_title') or '')}"
    return f"✔️ {base}" if highlight else base


@st.dialog("削除の確認")
def show_delete_dialog():
    if "knowledge_api" not in st.session_state:
        st.session_state["knowledge_api"] = KnowledgeAPI()
    api = st.session_state["knowledge_api"]
    st.write("本当に削除しますか？")
    col_ok, col_cancel = st.columns(2)
    with col_ok:
        if st.button("OK", key="delete_ok_dialog"):
            try:
                api.delete_knowledge(st.session_state["selected"])
                st.session_state["knowledge_all"] = api.get_knowledge_list()
                st.session_state["knowledge_filtered"] = apply_filters(
                    st.session_state["knowledge_all"],
                    st.session_state.get("contract_filter", "すべて"),
                    st.session_state.get("q", ""),
                )
                if st.session_state["knowledge_all"]:
                    st.session_state["selected"] = st.session_state["knowledge_all"][0]
                else:
                    st.session_state["selected"] = {}
                st.session_state["knowledge_page_status"] = "delete"
                st.rerun()
            except Exception as e:
                st.error(f"削除に失敗しました: {e}")
    with col_cancel:
        if st.button("キャンセル", key="delete_cancel_dialog"):
            st.rerun()


def main():
    st.title("ナレッジ管理")
    if "knowledge_api" not in st.session_state:
        st.session_state["knowledge_api"] = KnowledgeAPI()
    api = st.session_state["knowledge_api"]

    # ---------------- 初期ロードと状態 ----------------
    if "knowledge_all" not in st.session_state:
        try:
            st.session_state["knowledge_all"] = api.get_knowledge_list()
        except Exception:
            st.session_state["knowledge_all"] = []

    if "knowledge_filtered" not in st.session_state:
        st.session_state["knowledge_filtered"] = st.session_state["knowledge_all"]

    if "selected" not in st.session_state and st.session_state["knowledge_all"]:
        st.session_state["selected"] = st.session_state["knowledge_all"][0]

    if "knowledge_page_status" not in st.session_state:
        st.session_state["knowledge_page_status"] = "default"

    # ページネーション用の状態
    st.session_state.setdefault("page_size", PAGE_SIZE_DEFAULT)
    st.session_state.setdefault("page", 1)

    left_col, right_col = st.columns([1, 2])

    with left_col:
        # 契約種別の取得
        if "contract_types" not in st.session_state:
            try:
                st.session_state["contract_types"] = api.get_contract_types()
            except Exception:
                st.session_state["contract_types"] = []
        contract_types = st.session_state["contract_types"]
        type_names = [
            t.get("contract_type")
            for t in contract_types
            if isinstance(t, dict) and t.get("contract_type")
        ]
        if not type_names:
            type_names = ["汎用", "秘密保持", "業務委託", "共同開発", "共同出願"]

        # ---- ページネーション ----
        subset, page, max_page, start, end, total = paginate(
            st.session_state["knowledge_filtered"],
            st.session_state["page"],
            st.session_state["page_size"],
        )
        st.session_state["page"] = page

        # ---- 新規追加 ----
        if st.button("新規追加", use_container_width=True):
            st.session_state["knowledge_page_status"] = "new"
            try:
                new_number = api.get_max_knowledge_number() + 1
            except Exception:
                new_number = 1
            st.session_state["selected"] = {
                "knowledge_number": new_number,
                "version": 1,
                "contract_type": type_names[0] if type_names else "",
                "target_clause": "",
                "knowledge_title": "",
                "review_points": "",
                "action_plan": "",
                "clause_sample": "",
                "record_status": "latest",
                "approval_status": "draft",
            }
            st.rerun()
        st.markdown("---")

        # ---- リスト本体（ボタンで開く）----
        selected = st.session_state.get("selected")
        selected_no = str(selected.get("knowledge_number")) if selected else None

        for k in subset:
            no = str(k.get("knowledge_number"))
            is_selected = no == selected_no
            label = knowledge_label(k, highlight=is_selected)
            if st.button(label, key=f"open_{no}", use_container_width=True):
                st.session_state["selected"] = k
                st.session_state["knowledge_page_status"] = "draft"
                st.rerun()

        # ページコントロール（前/次 & 直接指定）
        cols = st.columns([1, 1, 2, 1, 1])
        with cols[0]:
            if st.button("≪", use_container_width=True, disabled=(page == 1)):
                st.session_state["page"] = 1
                st.rerun()
        with cols[1]:
            if st.button("＜", use_container_width=True, disabled=(page == 1)):
                st.session_state["page"] = page - 1
                st.rerun()
        with cols[3]:
            if st.button("＞", use_container_width=True, disabled=(page == max_page)):
                st.session_state["page"] = page + 1
                st.rerun()
        with cols[4]:
            if st.button("≫", use_container_width=True, disabled=(page == max_page)):
                st.session_state["page"] = max_page
                st.rerun()
        st.markdown("---")

        # # ---- フィルタUI（入力のたびに反映）----
        # st.markdown("#### フィルタ機能")
        # contract_filter = st.selectbox(
        #     "契約種別",
        #     ["すべて"] + type_names,
        #     key="contract_filter",
        #     on_change=lambda: st.rerun(),
        # )
        # search_text = st.text_input(
        #     "検索（番号/タイトル/本文に部分一致）",
        #     key="q",
        #     on_change=lambda: st.rerun(),
        # )

        # # 並び順（任意：番号降順/昇順）
        # sort_key = st.selectbox(
        #     "並び順", ["番号 降順", "番号 昇順"], index=1, on_change=lambda: st.rerun()
        # )
        # page_size = st.selectbox(
        #     "1ページの件数",
        #     [10, 20, 50],
        #     index=[10, 20, 50].index(PAGE_SIZE_DEFAULT),
        #     on_change=lambda: st.rerun(),
        # )
        # st.session_state["page_size"] = page_size

        # # フィルタ適用
        # base = st.session_state["knowledge_all"]
        # filtered = apply_filters(base, contract_filter, search_text)

        # # 並び替え
        # reverse = sort_key == "番号 降順"
        # filtered.sort(key=lambda k: int(k.get("knowledge_number", 0)), reverse=reverse)

        # st.session_state["knowledge_filtered"] = filtered

        # # 検索や件数を変えたら1ページ目へ
        # if st.session_state.get("page", 1) != 1:
        #     st.session_state["page"] = 1

    # ---- 右ペイン：詳細フォーム（あなたの既存コードほぼ流用）----
    with right_col:
        selected = st.session_state.get("selected")
        if selected:
            with st.form("detail_form"):
                knowledge_number = selected.get("knowledge_number", "")
                st.markdown(f"**No:** {knowledge_number}")

                contract_type = st.selectbox(
                    "契約種別",
                    type_names,
                    index=(
                        type_names.index(selected.get("contract_type", type_names[0]))
                        if selected.get("contract_type", type_names[0]) in type_names
                        else 0
                    ),
                    key=f"contract_type_{knowledge_number}",
                )
                title = st.text_input(
                    "タイトル",
                    selected.get("knowledge_title", ""),
                    placeholder="ナレッジのタイトルを簡潔に入力",
                    key=f"title_{knowledge_number}",
                )
                target_clause = st.text_input(
                    "対象条項",
                    selected.get("target_clause", ""),
                    placeholder="対象条項の条件を入力",
                    key=f"target_clause_{knowledge_number}",
                )
                review = st.text_area(
                    "審査観点",
                    selected.get("review_points", ""),
                    placeholder="審査で注意する観点を入力",
                    key=f"review_{knowledge_number}",
                    height="content",
                )
                action = st.text_area(
                    "対応策",
                    selected.get("action_plan", ""),
                    placeholder="リスクに対する対応策を入力",
                    key=f"action_{knowledge_number}",
                    height="content",
                )
                clause = st.text_area(
                    "条項サンプル",
                    selected.get("clause_sample", ""),
                    placeholder="対応するための条項サンプルを入力",
                    key=f"clause_{knowledge_number}",
                    height="content",
                )

                col1, col2 = st.columns(2)
                with col1:
                    save_btn = st.form_submit_button("保存")
                with col2:
                    delete_btn = st.form_submit_button(
                        "削除",
                        disabled=(
                            st.session_state.get("knowledge_page_status") == "new"
                        ),
                    )

            if save_btn:
                # 保存 → 成功時に全件リロードして現在の選択を維持
                data = dict(selected)
                data.update(
                    {
                        "contract_type": contract_type,
                        "target_clause": target_clause,
                        "knowledge_title": title,
                        "review_points": review,
                        "action_plan": action,
                        "clause_sample": clause,
                    }
                )
                # （各フォーム値でdataを更新）
                try:
                    saved = api.save_knowledge(data)
                    st.session_state["selected"] = saved
                    st.session_state["knowledge_all"] = api.get_knowledge_list()
                    # フィルタリングされたリストを更新
                    st.session_state["knowledge_filtered"] = apply_filters(
                        st.session_state["knowledge_all"],
                        st.session_state.get("contract_filter", "すべて"),
                        st.session_state.get("q", ""),
                    )
                    st.session_state["knowledge_page_status"] = "save"
                    st.rerun()
                except Exception as e:
                    st.error(f"保存に失敗しました: {e}")

            if delete_btn:
                show_delete_dialog()

        if st.session_state.get("knowledge_page_status") == "save":
            st.success("保存しました")
            st.session_state["knowledge_page_status"] = "draft"
        if st.session_state.get("knowledge_page_status") == "delete":
            st.success("削除しました")
            st.session_state["knowledge_page_status"] = "draft"


if __name__ == "__main__":
    main()
