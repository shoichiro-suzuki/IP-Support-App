import streamlit as st
import pandas as pd
from api.knowledge_api import KnowledgeAPI
import io

st.set_page_config(layout="wide", page_title="ナレッジ管理")


def convert_knowledge_to_df(knowledge_list):
    """ナレッジデータをDataFrameに変換"""
    if not knowledge_list:
        return pd.DataFrame()

    df_data = []
    for k in knowledge_list:
        df_data.append(
            {
                "id": k.get("id", ""),  # IDを追加
                "knowledge_number": k.get("knowledge_number", ""),
                "version": k.get("version", ""),
                "contract_type": k.get("contract_type", ""),
                "target_clause": k.get("target_clause", ""),
                "knowledge_title": k.get("knowledge_title", ""),
                "review_points": k.get("review_points", ""),
                "action_plan": k.get("action_plan", ""),
                "clause_sample": k.get("clause_sample", ""),
                "record_status": k.get("record_status", ""),
                "approval_status": k.get("approval_status", ""),
            }
        )

    return pd.DataFrame(df_data)


def convert_df_to_knowledge(df):
    """DataFrameをナレッジデータに変換"""
    knowledge_list = []
    for _, row in df.iterrows():
        knowledge_dict = {
            "knowledge_number": (
                int(row["knowledge_number"]) if pd.notna(row["knowledge_number"]) else 0
            ),
            "version": int(row["version"]) if pd.notna(row["version"]) else 1,
            "contract_type": (
                str(row["contract_type"]) if pd.notna(row["contract_type"]) else ""
            ),
            "target_clause": (
                str(row["target_clause"]) if pd.notna(row["target_clause"]) else ""
            ),
            "knowledge_title": (
                str(row["knowledge_title"]) if pd.notna(row["knowledge_title"]) else ""
            ),
            "review_points": (
                str(row["review_points"]) if pd.notna(row["review_points"]) else ""
            ),
            "action_plan": (
                str(row["action_plan"]) if pd.notna(row["action_plan"]) else ""
            ),
            "clause_sample": (
                str(row["clause_sample"]) if pd.notna(row["clause_sample"]) else ""
            ),
            "record_status": (
                str(row["record_status"])
                if pd.notna(row["record_status"])
                else "latest"
            ),
            "approval_status": (
                str(row["approval_status"])
                if pd.notna(row["approval_status"])
                else "draft"
            ),
        }

        # IDがある場合は含める（既存レコードの場合）
        if "id" in row and pd.notna(row["id"]) and str(row["id"]).strip():
            knowledge_dict["id"] = str(row["id"])

        knowledge_list.append(knowledge_dict)

    return knowledge_list


def main():
    st.title("ナレッジ管理")

    if "knowledge_api" not in st.session_state:
        st.session_state["knowledge_api"] = KnowledgeAPI()
    api = st.session_state["knowledge_api"]

    # データロード
    if "knowledge_all" not in st.session_state:
        try:
            st.session_state["knowledge_all"] = api.get_knowledge_list()
        except Exception as e:
            st.error(f"データの取得に失敗しました: {e}")
            st.session_state["knowledge_all"] = []

    knowledge_list = st.session_state["knowledge_all"]

    # Excel ダウンロード機能
    st.subheader("データのダウンロード")
    if knowledge_list:
        df = convert_knowledge_to_df(knowledge_list)

        # Excel形式での出力
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="ナレッジデータ", index=False)

        excel_data = output.getvalue()

        st.download_button(
            label="ナレッジデータをExcelでダウンロード",
            data=excel_data,
            file_name="knowledge_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.info("ダウンロードできるデータがありません。")

    st.markdown("---")

    # データエディター機能
    st.subheader("ナレッジデータのリスト編集")

    if knowledge_list:
        # DataFrameに変換
        df = convert_knowledge_to_df(knowledge_list)

        # 列の表示順序とヘッダー名を設定
        column_config = {
            "id": st.column_config.TextColumn("ID", disabled=True),  # IDは編集不可
            "knowledge_number": st.column_config.NumberColumn(
                "ナレッジNo", format="%d"
            ),
            "version": st.column_config.NumberColumn("バージョン", format="%d"),
            "contract_type": st.column_config.SelectboxColumn(
                "契約種別",
                options=["汎用", "秘密保持", "業務委託", "共同開発", "共同出願"],
            ),
            "target_clause": st.column_config.TextColumn("対象条項"),
            "knowledge_title": st.column_config.TextColumn("タイトル"),
            "review_points": st.column_config.TextColumn("審査観点"),
            "action_plan": st.column_config.TextColumn("対応策"),
            "clause_sample": st.column_config.TextColumn("条項サンプル"),
            "record_status": st.column_config.SelectboxColumn(
                "レコード状態", options=["latest", "archived"]
            ),
            "approval_status": st.column_config.SelectboxColumn(
                "承認状態", options=["draft", "approved", "rejected"]
            ),
        }

        # データエディターで表示
        edited_df = st.data_editor(
            df,
            column_config=column_config,
            num_rows="dynamic",
            height=600,
        )

        # 一括更新ボタン
        if st.button("一括更新", type="primary"):
            try:
                # DataFrameをナレッジデータに変換
                updated_knowledge_list = convert_df_to_knowledge(edited_df)

                # 各ナレッジを更新
                success_count = 0
                error_count = 0

                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, knowledge in enumerate(updated_knowledge_list):
                    try:
                        api.save_knowledge(knowledge)
                        success_count += 1
                    except Exception as e:
                        st.warning(
                            f"ナレッジNo.{knowledge.get('knowledge_number')}の更新に失敗: {e}"
                        )
                        error_count += 1

                    # プログレス更新
                    progress = (i + 1) / len(updated_knowledge_list)
                    progress_bar.progress(progress)
                    status_text.text(f"更新中... {i + 1}/{len(updated_knowledge_list)}")

                # 完了メッセージ
                progress_bar.empty()
                status_text.empty()

                if error_count == 0:
                    st.success(f"全{success_count}件のナレッジを正常に更新しました。")
                else:
                    st.warning(f"更新完了: 成功{success_count}件、失敗{error_count}件")

                # データを再読み込み
                st.session_state["knowledge_all"] = api.get_knowledge_list()
                st.rerun()

            except Exception as e:
                st.error(f"一括更新に失敗しました: {e}")
        st.write(
            """レコード(行)の追加が可能です。\n
レコードの削除は、個別のナレッジ詳細画面で削除してください。"""
        )
    else:
        st.info("編集できるデータがありません。")


if __name__ == "__main__":
    main()
