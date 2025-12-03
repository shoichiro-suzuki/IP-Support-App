"""
pdf_sample.pdf を OCR + フラット化し、プロジェクトルートにテキストを書き出す簡易スクリプト。
依存: services.document_input.extract_text_from_document (Document Intelligence OCR)
出力: ./pdf_sample_flattened.txt
"""

from pathlib import Path
from typing import Any, Dict, List

import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.document_input import extract_text_from_document


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


def main():
    pdf_path = Path("pdf_sample.pdf")
    if not pdf_path.exists():
        raise FileNotFoundError(f"{pdf_path} が見つかりません。")

    result = extract_text_from_document(str(pdf_path))
    flattened = flatten_document_result(result)
    out_path = Path("pdf_sample_flattened.txt")
    out_path.write_text(flattened, encoding="utf-8")
    print(f"書き出し完了: {out_path} ({len(flattened)} chars)")


if __name__ == "__main__":
    main()
