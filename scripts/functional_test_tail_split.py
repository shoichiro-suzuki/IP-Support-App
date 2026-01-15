import argparse
import json
import os
import re
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.boundary_audit import LlmAuditConfig, split_tail_sections

# テスト実行例:
# py scripts/functional_test_tail_split.py  # デフォルト（末尾120行、擬似LLM）
# py scripts/functional_test_tail_split.py --tail-lines 80  # 末尾80行のみ
# py scripts/functional_test_tail_split.py --tail-lines 200  # 末尾200行のみ
# py scripts/functional_test_tail_split.py --use-llm  # 実LLMで監査


def _load_paragraphs(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    paragraphs = data.get("paragraphs", [])
    lines = []
    for item in paragraphs:
        if isinstance(item, dict):
            content = item.get("content", "")
        else:
            content = getattr(item, "content", "")
        if content:
            lines.append(content)
    return [line for line in lines if line.strip()]


def _fake_llm(messages):
    content = messages[-1]["content"]
    lines = []
    for line in content.splitlines():
        match = re.match(r"^\[(\d+)\]\s(.*)$", line)
        if match:
            lines.append((int(match.group(1)), match.group(2)))
    total_lines = len(lines)
    sig_line = _find_boundary_line(lines, "SIG_CAND")
    attach_line = _find_boundary_line(lines, "ATTACH_CAND")
    boundaries = []
    for _, boundary_id in _collect_boundary_lines(lines):
        section = "signature" if boundary_id.startswith("SIG_CAND") else "attachments"
        boundaries.append(
            {
                "id": boundary_id,
                "status": "accept",
                "section_after_boundary": section,
                "confidence": 0.7,
                "rationale": "rule_match",
            }
        )
    final_sections = []
    if sig_line:
        clause_end = max(sig_line - 1, 1)
        final_sections.append(
            {"name": "clause_last", "start_line": 1, "end_line": clause_end}
        )
        if attach_line and attach_line > sig_line:
            final_sections.append(
                {
                    "name": "signature",
                    "start_line": sig_line + 1,
                    "end_line": attach_line - 1,
                }
            )
            final_sections.append(
                {
                    "name": "attachments",
                    "start_line": attach_line + 1,
                    "end_line": total_lines,
                }
            )
        else:
            final_sections.append(
                {
                    "name": "signature",
                    "start_line": sig_line + 1,
                    "end_line": total_lines,
                }
            )
    elif attach_line:
        clause_end = max(attach_line - 1, 1)
        final_sections.append(
            {"name": "clause_last", "start_line": 1, "end_line": clause_end}
        )
        final_sections.append(
            {
                "name": "attachments",
                "start_line": attach_line + 1,
                "end_line": total_lines,
            }
        )
    else:
        final_sections.append(
            {"name": "clause_last", "start_line": 1, "end_line": total_lines}
        )
    payload = {
        "verdict": "accept",
        "boundaries": boundaries,
        "final_sections": final_sections,
        "warnings": [],
    }
    return json.dumps(payload, ensure_ascii=False)


def _find_boundary_line(lines, prefix):
    for line_number, text in lines:
        if text.startswith(f"---BOUNDARY:{prefix}"):
            return line_number
    return None


def _collect_boundary_lines(lines):
    results = []
    for line_number, text in lines:
        if text.startswith("---BOUNDARY:") and text.endswith("---"):
            boundary_id = text.replace("---BOUNDARY:", "").replace("---", "")
            results.append((line_number, boundary_id))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=os.path.join("tests", "ocr_result_test_加工済.json"),
        help="OCR JSON path",
    )
    parser.add_argument("--tail-lines", type=int, default=120)
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument(
        "--output",
        default=os.path.join("tmp", "functional_test_tail_split_result.json"),
        help="Output JSON path",
    )
    parser.add_argument("--print-full", action="store_true")
    args = parser.parse_args()

    paragraphs = _load_paragraphs(args.input)
    tail_lines = paragraphs[-args.tail_lines :] if args.tail_lines else paragraphs

    llm_call = None if args.use_llm else _fake_llm
    result = split_tail_sections(
        tail_lines, llm_config=LlmAuditConfig(max_retries=0), llm_call=llm_call
    )

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    output_payload = {
        "input_path": args.input,
        "tail_lines": args.tail_lines,
        "input_lines": len(tail_lines),
        "clause_last_lines": len(result["clause_last_text"].splitlines()),
        "signature_lines": len(result["signature_text"].splitlines()),
        "attachments_count": len(result["attachments"]),
        "clause_last_text": result["clause_last_text"],
        "signature_text": result["signature_text"],
        "attachments": result["attachments"],
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)
    print(
        "result="
        f"input_lines:{output_payload['input_lines']}, "
        f"clause_last_lines:{output_payload['clause_last_lines']}, "
        f"signature_lines:{output_payload['signature_lines']}, "
        f"attachments_count:{output_payload['attachments_count']}"
    )
    print(f"output_file={args.output}")
    if args.print_full:
        print("clause_last_text:")
        print(result["clause_last_text"])
        if result["signature_text"]:
            print("signature_text:")
            print(result["signature_text"])
        if result["attachments"]:
            print("attachments:")
            for attachment in result["attachments"]:
                print(attachment)


if __name__ == "__main__":
    main()
