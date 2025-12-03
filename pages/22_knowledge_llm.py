import json, os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import streamlit as st
from jsonschema import Draft202012Validator, ValidationError

from api.knowledge_api import KnowledgeAPI
from azure_.openai_service import AzureOpenAIService
from services.document_input import extract_text_from_document

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
    "A: 深掘り重視（system_prompt_A.md）": Path("prompts/system_prompt_A.md"),
    "B: 汎用インタビュー（system_prompt_B.md）": Path("prompts/system_prompt_B.md"),
}

TURN_SCHEMA_PATH = Path("configs/knowledge_llm/knowledge_llm_turn.schema.json")
KNOWLEDGE_SCHEMA_PATH = Path("configs/knowledge_llm/knowledge_llm_entry.schema.json")
DEBUG_MODE = os.getenv("DEBUG", "").lower() in ("1", "true", "on")
FEW_SHOT_TURN = json.dumps(
    {
        "control": {"schema_version": "1.0", "mode": "interview"},
        "state": {"phase": "collect_case", "missing_info": []},
        "assistant_message": "次の質問をしてください",
        "knowledge_json": None,
    },
    ensure_ascii=False,
)


def load_schema(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        st.error(f"スキーマ読み込みに失敗しました: {path.name} / {e}")
        return {}


TURN_SCHEMA = load_schema(TURN_SCHEMA_PATH)
KNOWLEDGE_SCHEMA = load_schema(KNOWLEDGE_SCHEMA_PATH)
TURN_VALIDATOR = Draft202012Validator(TURN_SCHEMA) if TURN_SCHEMA else None
KNOWLEDGE_VALIDATOR = (
    Draft202012Validator(KNOWLEDGE_SCHEMA) if KNOWLEDGE_SCHEMA else None
)


def append_debug_log(entry: Dict[str, Any]):
    if not DEBUG_MODE:
        return
    st.session_state.setdefault("knowledge_llm_debug_logs", []).append(entry)


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


def flatten_document_result(doc: Dict[str, Any]) -> str:
    """document_inputの結果dictをシンプルなテキストに整形"""
    if not isinstance(doc, dict):
        return ""
    parts: List[str] = []
    if doc.get("title"):
        parts.append(str(doc["title"]))
    if doc.get("introduction"):
        parts.append(str(doc["introduction"]))
    for clause in doc.get("clauses", []):
        if isinstance(clause, dict):
            num = clause.get("clause_number", "")
            text = clause.get("text", "")
            if num:
                parts.append(f"{num}\n{text}")
            else:
                parts.append(str(text))
    if doc.get("signature_section"):
        parts.append(str(doc["signature_section"]))
    for att in doc.get("attachments", []):
        parts.append(str(att))
    return "\n\n".join(p for p in parts if p)


def render_text_with_breaks(content: str) -> str:
    """Markdownで単一改行も反映させるため \\n を明示的に改行に置換"""
    if not content:
        return ""
    return content.replace("\n", "  \n")


def extract_texts(files) -> List[str]:
    texts: List[str] = []
    for f in files:
        try:
            ext = Path(f.name).suffix.lower()
            if ext in (".pdf", ".docx"):
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                tmp.write(f.getvalue())
                tmp.flush()
                tmp_path = tmp.name
                tmp.close()
                try:
                    doc = extract_text_from_document(tmp_path)
                    texts.append(flatten_document_result(doc))
                finally:
                    try:
                        Path(tmp_path).unlink(missing_ok=True)
                    except Exception as cleanup_err:
                        append_debug_log({"file_cleanup_error": str(cleanup_err)})
            else:
                texts.append(f.getvalue().decode("utf-8", errors="ignore"))
        except Exception as e:
            err_msg = f"file:{getattr(f,'name','unknown')} error:{e}"
            append_debug_log({"file_error": err_msg})
            texts.append(err_msg if DEBUG_MODE else "")
    return texts


def parse_and_validate_turn(raw: str) -> Dict[str, Union[bool, str, List[Dict]]]:
    """LLM出力(JSON文字列)を turn/knowledge スキーマで検証"""
    if not raw:
        return {"ok": False, "error": "empty", "error_type": "empty"}
    if not TURN_VALIDATOR or not KNOWLEDGE_VALIDATOR:
        return {"ok": False, "error": "validator_not_ready", "error_type": "config"}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"json_parse: {e}", "error_type": "parse"}

    try:
        TURN_VALIDATOR.validate(parsed)
    except ValidationError as e:
        return {
            "ok": False,
            "error": f"turn_schema: {list(e.path)} {e.message}",
            "error_type": "turn_schema",
        }

    knowledge = parsed.get("knowledge_json")
    knowledge_list: List[Dict] = []
    if knowledge is not None:
        if not isinstance(knowledge, dict):
            return {
                "ok": False,
                "error": "knowledge_json_type",
                "error_type": "knowledge_schema",
            }
        try:
            KNOWLEDGE_VALIDATOR.validate(knowledge)
        except ValidationError as e:
            return {
                "ok": False,
                "error": f"knowledge_schema: {list(e.path)} {e.message}",
                "error_type": "knowledge_schema",
            }
        normalized = {k: str(knowledge.get(k, "") or "") for k in FIELDS}
        knowledge_list.append(normalized)

    return {
        "ok": True,
        "assistant_message": str(parsed.get("assistant_message", "") or ""),
        "knowledge": knowledge_list,
    }


def build_repair_instruction(raw_output: str, error: str, error_type: str) -> str:
    return "\n".join(
        [
            "以下は直前の出力JSONです。",
            "",
            "---",
            raw_output,
            "---",
            "",
            f"バリデーションエラー種別: {error_type}",
            f"詳細: {error}",
            "",
            "同じ意味を維持しつつ、指定スキーマに完全準拠する単一のJSONオブジェクトのみを返してください。",
            "フィールドは control/state/assistant_message/knowledge_json の4つのみを使用してください。",
        ]
    )


def call_llm(
    user_text: str,
    file_texts: List[str],
    system_prompt: str,
    history: Optional[List[Dict[str, Any]]] = None,
    max_retries: int = 2,
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
        {"role": "assistant", "content": FEW_SHOT_TURN},
    ]
    if history:
        for msg in history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": payload})
    response_format = None
    if TURN_SCHEMA:
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "ContractReviewKnowledgeTurn",
                "schema": TURN_SCHEMA,
            },
        }
    debug_entry: Dict[str, Any] = {
        "payload_without_system": payload,
        "file_processed": bool(file_texts),
        "file_texts": file_texts if DEBUG_MODE else None,
        "retries": 0,
        "history_count": len(history) if history else 0,
    }
    try:
        raw = st.session_state["openai_service"].get_openai_response_gpt51_chat(
            messages, format=response_format
        )
        validated = parse_and_validate_turn(raw)
        debug_entry.update(
            {
                "raw": raw,
                "validation": validated,
            }
        )
        retries = 0
        while not validated.get("ok") and retries < max_retries:
            retries += 1
            debug_entry["retries"] = retries
            repair_msg = build_repair_instruction(
                raw_output=raw,
                error=str(validated.get("error", "")),
                error_type=str(validated.get("error_type", "unknown")),
            )
            repair_messages = [
                *messages,
                {"role": "assistant", "content": raw},
                {"role": "user", "content": repair_msg},
            ]
            raw = st.session_state["openai_service"].get_openai_response_gpt51_chat(
                repair_messages, format=response_format
            )
            validated = parse_and_validate_turn(raw)
            debug_entry.setdefault("retry_results", []).append(
                {"raw": raw, "validation": validated}
            )

        if not validated.get("ok"):
            append_debug_log(debug_entry)
            return {
                "ok": False,
                "raw": raw,
                "parsed": None,
                "error": validated.get("error"),
            }
        append_debug_log(debug_entry)
        return {
            "ok": True,
            "raw": raw,
            "parsed": validated.get("knowledge"),
            "assistant_message": validated.get("assistant_message", ""),
        }
    except Exception as e:
        st.error("LLM呼び出しに失敗しました。環境変数とモデル設定を確認してください。")
        return {"ok": False, "raw": "", "parsed": None}


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
            st.markdown(f"{prompts[prompt_choice]}")
    system_prompt = prompts.get(prompt_choice, "")

    if DEBUG_MODE:
        with st.sidebar.expander("デバッグログ (セッション内)", expanded=False):
            logs = st.session_state.get("knowledge_llm_debug_logs", [])
            if not logs:
                st.caption("ログなし")
            else:
                for i, log in enumerate(logs):
                    st.markdown(f"- リクエスト {i+1}: retries={log.get('retries',0)}")
                if st.checkbox("ログ詳細を表示", value=False):
                    st.json(logs)

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
            st.markdown(render_text_with_breaks(msg.get("content", "")))
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
        user_entry = {"role": "user", "content": user_text, "file_names": file_names}
        st.session_state["knowledge_llm_chat"].append(user_entry)
        # 即時表示してからLLM処理開始
        with st.chat_message("user"):
            st.markdown(render_text_with_breaks(user_text))
            if file_names:
                st.caption(f"添付: {', '.join(file_names)}")
        with st.spinner("ナレッジを生成中..."):
            history = st.session_state.get("knowledge_llm_chat", [])[:-1]
            result = call_llm(
                user_text,
                file_texts,
                system_prompt=system_prompt,
                history=history,
            )
        raw_text = result.get("raw", "")
        if result.get("ok"):
            st.session_state["knowledge_llm_outputs"] = result.get("parsed") or []
            assistant_msg = result.get("assistant_message") or "JSONを生成しました。"
            st.session_state["knowledge_llm_chat"].append(
                {
                    "role": "assistant",
                    "content": assistant_msg,
                }
            )
        else:
            st.session_state["knowledge_llm_outputs"] = []
            fallback = (
                raw_text
                or "JSONスキーマを満たす出力が得られませんでした。プロンプト/入力を確認してください。"
            )
            st.session_state["knowledge_llm_chat"].append(
                {
                    "role": "assistant",
                    "content": f"{fallback}\n\n検証エラー: {result.get('error','')}",
                }
            )
        st.rerun()


if __name__ == "__main__":
    main()
