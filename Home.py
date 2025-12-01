import streamlit as st

st.set_page_config(page_title="IP Support App", layout="wide", page_icon="📜")

st.title("契約審査サポートアプリ📜")
st.markdown("<div style='text-align: right'>Ver. 0.7</div>", unsafe_allow_html=True)
# st.page_link("pages/new_contract.py", label="契約登録・修正", icon="📝")
st.page_link("pages/10_examination.py", label="契約審査", icon="🔍")
# st.page_link("pages/view_contract.py", label="契約閲覧", icon="📄")
st.page_link("pages/20_knowledge.py", label="ナレッジ管理", icon="📚")
st.page_link(
    "pages/21_knowledge_datalist.py", label="ナレッジ管理_リスト表示", icon="📚"
)

st.markdown("---")
st.markdown(
    """### 変更ログ
- Ver. 0.0: 初版リリース
- Ver. 0.1: GPT-5モデル追加
- Ver. 0.2: CORSをキャンセルするStreamlit configを追加
- Ver. 0.3: 審査結果に使用したナレッジを表示
- Ver. 0.4: ナレッジの対象条項ですべての条項に該当しないナレッジは審査対象から除外
- Ver. 0.5: ナレッジ管理のUI改善
- Ver. 0.6: 審査結果ダウンロード機能追加、画面レイアウト修正
- Ver. 0.7: ナレッジデータを管理者のみ編集可能とする
- Ver. 1.0: 審査時にLLMチャット機能を追加
"""
)
