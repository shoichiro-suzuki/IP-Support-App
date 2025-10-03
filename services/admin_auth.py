import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()


def check_admin_auth():
    """管理者権限の確認"""
    return st.session_state.get("is_admin", False)


def show_admin_sidebar():
    """サイドバーに管理者ログインUIを表示"""
    with st.sidebar:
        st.markdown("### 🔐 管理者認証")

        if not check_admin_auth():
            password = st.text_input(
                "管理者パスワード", type="password", key="admin_password_input"
            )
            if st.button("ログイン", key="admin_login_btn", use_container_width=True):
                admin_password = os.getenv("KNOWLEDGE_ADMIN_PASSWORD", "")
                if password == admin_password and password:
                    st.session_state["is_admin"] = True
                    st.success("管理者ログイン成功")
                    st.rerun()
                else:
                    st.error("パスワードが正しくありません")
        else:
            st.success("✅ 管理者権限でログイン中")
            if st.button(
                "ログアウト", key="admin_logout_btn", use_container_width=True
            ):
                st.session_state["is_admin"] = False
                st.info("ログアウトしました")
                st.rerun()

        st.markdown("---")
