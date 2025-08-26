import streamlit as st

st.set_page_config(page_title="IP Support App", layout="wide", page_icon="📜")

st.title("契約審査サポートアプリ📜")
st.markdown("<div style='text-align: right'>Ver. 0.2</div>", unsafe_allow_html=True)
# st.page_link("pages/new_contract.py", label="契約登録・修正", icon="📝")
st.page_link("pages/examination.py", label="契約審査", icon="🔍")
# st.page_link("pages/view_contract.py", label="契約閲覧", icon="📄")
st.page_link("pages/knowledge.py", label="ナレッジ管理", icon="📚")

st.markdown("---")
st.markdown(
    """### 変更ログ
- Ver. 0.0: 初版リリース
- Ver. 0.1: GPT-5モデル追加
- Ver. 0.2: CORSをキャンセルするStreamlit configを追加
"""
)
