import argparse
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.boundary_audit import split_tail_sections
from services.document_input import _merge_clauses_with_llm


def _load_clauses(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("clauses", [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=os.path.join("tests", "ocr_clause_split_misaligned.json"),
        help="Misaligned clauses JSON",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("tmp", "clause_boundary_audit_result.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    if not (
        os.getenv("OPENAI_API_KEY")
        and os.getenv("OPENAI_API_BASE")
        and os.getenv("OPENAI_API_VERSION")
    ):
        raise EnvironmentError("Azure OpenAIの環境変数が未設定です。")

    clauses = _load_clauses(args.input)
    merged = _merge_clauses_with_llm(clauses, None)
    if merged is None:
        raise RuntimeError("LLM監査に失敗しました。")

    signature_section = ""
    attachments = []
    if merged:
        last_clause = merged[-1]
        last_lines = last_clause.get("text", "").splitlines()
        tail_result = split_tail_sections(last_lines)
        merged[-1]["text"] = tail_result["clause_last_text"].strip()
        signature_section = tail_result["signature_text"]
        attachments = tail_result["attachments"]

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    payload = {
        "input_path": args.input,
        "input_clause_count": len(clauses),
        "output_clause_count": len(merged),
        "clauses": merged,
        "signature_section": signature_section,
        "attachments": attachments,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"output_file={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
