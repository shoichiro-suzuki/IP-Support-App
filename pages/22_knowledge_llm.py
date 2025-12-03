import json
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

from api.knowledge_api import KnowledgeAPI
from azure_.openai_service import AzureOpenAIService

st.set_page_config(page_title="ナレッジ創出（LLM）", layout="wide")

FIELDS = [
    "contract_type",
    "knowledge_title",
    "target_clause",
    "review_points",
    "action_plan",
    "clause_sample",
]

PROMPT_FILES = {
    "A: 深掘り重視（system_prompt_A.md）": Path("system_prompt_A.md"),
    "B: 汎用インタビュー（system_prompt_B.md）": Path("system_prompt_B.md"),
}


def init_state():
    st.session_state.setdefault("knowledge_llm_chat", [])
    st.session_state.setdefault("knowledge_llm_outputs", [])
    if "knowledge_api" not in st.session_state:
        st.session_state["knowledge_api"] = KnowledgeAPI()
    if "openai_service" not in st.session_state:
        st.session_state["openai_service"] = AzureOpenAIService()


def load_samples() -> List[Dict]:
    path = Path("docs/review-ui-llm-support/knowledge_samples.json")
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def load_prompts() -> Dict[str, str]:
    prompts = {}
    for label, path in PROMPT_FILES.items():
        try:
            prompts[label] = path.read_text(encoding="utf-8")
        except Exception:
            prompts[label] = ""
    return prompts


def extract_texts(files) -> List[str]:
    texts: List[str] = []
    for f in files:
        try:
            texts.append(f.getvalue().decode("utf-8", errors="ignore"))
        except Exception:
            texts.append("")
    return texts


def parse_json_block(text: str) -> Optional[List[Dict]]:
    if not text:
        return None
    snippet = text
    if "```" in text:
        parts = text.split("```")
        # 期待: ```json ... ```
        for part in parts:
            if part.strip().startswith("{") or part.strip().startswith("["):
                snippet = part
                break
    try:
        data = json.loads(snippet)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
    except Exception:
        return None
    return None


def validate_entries(data: List[Dict]) -> Optional[List[Dict]]:
    if not isinstance(data, list):
        return None
    cleaned = []
    for item in data:
        if not isinstance(item, dict):
            return None
        if any(k not in item for k in FIELDS):
            return None
        normalized = {k: str(item.get(k, "") or "") for k in FIELDS}
        cleaned.append(normalized)
    return cleaned


def call_llm(
    user_text: str, file_texts: List[str], system_prompt: str
) -> Dict[str, Optional[List[Dict]]]:
    content_blocks = []
    if user_text:
        content_blocks.append(f"ユーザー指示:\n{user_text}")
    if file_texts:
        merged = "\n\n".join(file_texts)
        content_blocks.append(f"添付テキスト:\n{merged}")
    payload = "\n\n".join(content_blocks)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": payload},
    ]
    try:
        raw = st.session_state["openai_service"].get_openai_response_gpt51_chat(
            messages
        )
        parsed = parse_json_block(raw)
        validated = validate_entries(parsed) if parsed is not None else None
        return {"raw": raw, "parsed": validated}
    except Exception as e:
        st.error("LLM呼び出しに失敗しました。環境変数とモデル設定を確認してください。")
        return {"raw": "", "parsed": None}


def render_generated():
    outputs: List[Dict] = st.session_state.get("knowledge_llm_outputs", [])
    st.subheader("生成結果")
    if not outputs:
        st.info("まだ生成結果がありません。指示とファイルを送信してください。")
        return

    for idx, item in enumerate(outputs):
        title = item.get("knowledge_title") or f"生成ナレッジ {idx+1}"
        with st.expander(f"{idx+1}. {title}", expanded=False):
            st.markdown(f"- 契約種別: {item.get('contract_type', '')}")
            st.markdown(f"- 対象条項: {item.get('target_clause', '')}")
            st.markdown(f"- 審査観点:\n{item.get('review_points', '')}")
            st.markdown(f"- 対応策:\n{item.get('action_plan', '')}")
            st.markdown(f"- 条項サンプル:\n{item.get('clause_sample', '')}")

    json_str = json.dumps(outputs, ensure_ascii=False, indent=2)
    st.download_button(
        "JSONダウンロード",
        json_str,
        file_name="knowledge_generated.json",
        mime="application/json",
    )


def render_sidebar(samples: List[Dict]):
    st.sidebar.subheader("既存ナレッジ例")
    for idx, s in enumerate(samples[:5]):
        with st.sidebar.expander(
            f"サンプル {idx+1}: {s.get('knowledge_title','')}", expanded=False
        ):
            st.markdown(f"- 契約種別: {s.get('contract_type','')}")
            st.markdown(f"- 対象条項: {s.get('target_clause','')}")
            st.markdown(f"- 審査観点:\n{s.get('review_points','')}")
            st.markdown(f"- 対応策:\n{s.get('action_plan','')}")
    st.sidebar.markdown("---")
    st.sidebar.caption("出力JSONは機能2/3のスキーマを前提に整形済み。")


def main():
    init_state()
    samples = load_samples()
    prompts = load_prompts()
    st.sidebar.subheader("システムプロンプト")
    prompt_choice = st.sidebar.selectbox(
        "プロンプト選択",
        options=list(prompts.keys()),
        index=0 if prompts else None,
        help="A: 深掘り重視 / B: 汎用インタビュー",
    )
    if prompt_choice and prompts.get(prompt_choice):
        with st.sidebar.expander("プロンプト内容", expanded=False):
            st.markdown(f"```\n{prompts[prompt_choice]}\n```")
    system_prompt = prompts.get(prompt_choice, "")

    outputs: List[Dict] = st.session_state.get("knowledge_llm_outputs", [])
    if outputs:
        json_str = json.dumps(outputs, ensure_ascii=False, indent=2)
        st.sidebar.download_button(
            "生成ナレッジJSONをダウンロード",
            json_str,
            file_name="knowledge_generated.json",
            mime="application/json",
        )
    st.title("ナレッジ創出（LLM）")
    st.caption(
        "チャットで指示とファイルを送信し、CosmosDBスキーマのナレッジJSONを生成。"
    )

    for msg in st.session_state.get("knowledge_llm_chat", []):
        with st.chat_message(msg["role"]):
            st.markdown(msg.get("content", ""))
            if msg.get("file_names"):
                st.caption(f"添付: {', '.join(msg['file_names'])}")

    submission = st.chat_input(
        "指示や要件を入力し、必要ならファイルを添付",
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
        file_texts = extract_texts(files)
        st.session_state["knowledge_llm_chat"].append(
            {"role": "user", "content": user_text, "file_names": file_names}
        )
        with st.spinner("ナレッジを生成中..."):
            result = call_llm(user_text, file_texts, system_prompt=system_prompt)
        raw_text = result.get("raw", "")
        if result["parsed"]:
            st.session_state["knowledge_llm_outputs"] = result["parsed"]
            st.session_state["knowledge_llm_chat"].append(
                {
                    "role": "assistant",
                    "content": raw_text or "JSONを生成しました。サイドバーからダウンロードできます。",
                }
            )
        else:
            st.session_state["knowledge_llm_outputs"] = []
            fallback = raw_text or "JSONスキーマを満たす出力が得られませんでした。プロンプト/入力を確認してください。"
            st.session_state["knowledge_llm_chat"].append(
                {
                    "role": "assistant",
                    "content": fallback,
                }
            )
        st.rerun()


if __name__ == "__main__":
    main()
