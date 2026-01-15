# pip install python-docx

from typing import Callable, Optional

from services.boundary_audit import LlmAuditConfig, split_tail_sections


def split_document_paragraphs(
    paragraphs: list[str],
    *,
    enable_tail_audit: bool = True,
    llm_config: Optional[LlmAuditConfig] = None,
    llm_call: Optional[Callable[[list[dict]], str]] = None,
    audit_clause_boundaries: bool = True,
    clause_llm_call: Optional[Callable[[list[dict]], str]] = None,
) -> dict:
    lines = [line.rstrip("\n") for line in paragraphs]
    chunked = _chunk_by_clauses(lines, enable_tail_audit, llm_config, llm_call)
    if audit_clause_boundaries and "error" not in chunked:
        merged = _merge_clauses_with_llm(chunked["clauses"], clause_llm_call)
        if merged is None:
            return {
                "error": "条文境界のLLM監査に失敗しました。手動修正してください。",
                "raw_text": "\n".join(lines),
            }
        chunked["clauses"] = merged
    return chunked


def _chunk_by_clauses(
    lines: list[str],
    enable_tail_audit: bool,
    llm_config: Optional[LlmAuditConfig],
    llm_call: Optional[Callable[[list[dict]], str]],
) -> dict:
    import re

    clause_pattern = re.compile(
        r"^(第[0-9一二三四五六七八九十百千]+条|Article\s+\d+)",
        flags=re.IGNORECASE,
    )

    def z2h_num(s: str) -> str:
        return s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))

    clause_starts = []
    for idx, line in enumerate(lines):
        normalized = z2h_num(line.lstrip())
        match = clause_pattern.match(normalized)
        if match:
            clause_starts.append((idx, match.group(1)))
    title = ""
    introduction = ""
    clauses = []
    signature_section = ""
    attachments = []
    if clause_starts:
        intro_lines = lines[: clause_starts[0][0]]
        if intro_lines:
            title = intro_lines[0].strip()
            introduction = "\n".join(intro_lines[1:]).strip()
        for idx, (start, marker) in enumerate(clause_starts):
            end = clause_starts[idx + 1][0] if idx + 1 < len(clause_starts) else len(lines)
            clause_lines = lines[start:end]
            clause_title = clause_lines[0].strip()
            if marker.startswith("第"):
                clause_number = marker.replace("第", "").replace("条", "")
            elif marker.lower().startswith("article"):
                clause_number = marker.split()[1] if len(marker.split()) > 1 else ""
            else:
                clause_number = marker
            clause_text_body = "\n".join(clause_lines[1:]).strip()
            clause_text = (
                f"{clause_title}\n{clause_text_body}"
                if clause_text_body
                else clause_title
            )
            if enable_tail_audit and idx == len(clause_starts) - 1:
                tail_result = split_tail_sections(
                    clause_lines, llm_config=llm_config, llm_call=llm_call
                )
                clause_text = tail_result["clause_last_text"].strip()
                signature_section = tail_result["signature_text"].strip()
                attachments = tail_result["attachments"]
            clauses.append(
                {
                    "id": len(clauses) + 1,
                    "clause_number": clause_number,
                    "text": clause_text,
                }
            )
    else:
        if lines:
            title = lines[0].strip()
            introduction = "\n".join(lines[1:]).strip()
        else:
            title = ""
            introduction = ""
    if attachments and signature_section:
        for att in attachments:
            if att and att in signature_section:
                signature_section = signature_section.replace(att, "").strip()
    return {
        "title": title,
        "introduction": introduction,
        "clauses": clauses,
        "signature_section": signature_section,
        "attachments": attachments,
    }


def _merge_clauses_with_llm(
    clauses: list[dict], llm_call: Optional[Callable[[list[dict]], str]]
) -> Optional[list[dict]]:
    import json
    from azure_.openai_service import AzureOpenAIService

    system_prompt = """
あなたは優秀な契約書解析AIです。
契約書の条文を「第X条」で機械的に分割したJSONデータ（id, clause_number, text）を提供します。
条文中に「第X条に従い」などの引用があると、不適切に分割されている可能性があります。
隣り合うclause_numberの文章を結合すべきidのリストのみを出力してください。
例: [2,3,4] / 複数グループは [[2,3],[5,6]]。結合不要なら []。
出力はJSONのみ。
"""
    prompt = "### 条文リスト:\n" + json.dumps(
        clauses, ensure_ascii=False, indent=2
    )
    messages = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": prompt},
    ]
    call = llm_call
    if call is None:
        service = AzureOpenAIService()
        call = service.get_openai_response_gpt41
    try:
        result = call(messages)
        if isinstance(result, str):
            result = (
                result.replace("```json", "")
                .replace("```", "")
                .replace("\n", "")
                .replace("\\", "")
                .strip()
            )
        payload = json.loads(result)
    except Exception:
        return None
    if not isinstance(payload, list):
        return None
    merged = []
    used_ids = set()
    for group in payload:
        if not group:
            continue
        if isinstance(group, int):
            group = [group]
        if not isinstance(group, list):
            return None
        group_clauses = [c for c in clauses if c.get("id") in group]
        if not group_clauses:
            continue
        min_id = min(c["id"] for c in group_clauses)
        min_clause_number = [
            c["clause_number"] for c in group_clauses if c["id"] == min_id
        ][0]
        merged_text = "".join(c["text"].strip() for c in group_clauses)
        merged.append(
            {"id": min_id, "clause_number": min_clause_number, "text": merged_text}
        )
        used_ids.update(group)
    for clause in clauses:
        if clause.get("id") not in used_ids:
            merged.append(clause)
    merged = sorted(merged, key=lambda x: x.get("id", 0))
    return merged


def extract_text_from_document(
    file_path: str, *, audit_clause_boundaries: bool = True
) -> dict:
    import os
    from azure_.documentintelligence import get_document_intelligence_ocr

    def extract_text_including_sdt(file_path: str) -> str:
        """
        .docx 内の“可視テキスト”をできるだけ取りこぼしなく抽出する。
        - SDT(コンテンツコントロール)配下のテキストも含む
        - 本文に加え、ヘッダー/フッター、脚注/文末脚注、コメントも対象
        - 段落(w:p)ごとに w:t を結合し、行として積む
        - 変更履歴の削除(w:del)配下の文字は除外
        """
        import zipfile
        import lxml.etree as etree

        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

        def _read_xml(z: zipfile.ZipFile, name: str):
            try:
                return etree.fromstring(z.read(name))
            except KeyError:
                return None

        with zipfile.ZipFile(file_path) as z:
            # 見に行くパーツ（存在するものだけ処理）
            parts = ['word/document.xml']
            parts += [n for n in z.namelist() if n.startswith('word/header')]
            parts += [n for n in z.namelist() if n.startswith('word/footer')]
            for extra in ('word/footnotes.xml', 'word/endnotes.xml', 'word/comments.xml'):
                if extra in z.namelist():
                    parts.append(extra)

            lines = []
            for name in parts:
                root = _read_xml(z, name)
                if root is None:
                    continue

                # パーツ内の“段落ごと”に、削除履歴を除いた w:t を順序通り収集
                for p in root.xpath('.//w:p', namespaces=ns):
                    # 段落内のテキストノード（w:t）を、w:del の配下は除外して集める
                    ts = p.xpath('.//w:t[not(ancestor::w:del)]/text()', namespaces=ns)
                    line = ''.join(ts).strip()
                    if line:
                        lines.append(line)

            return '\n'.join(lines)


    # ファイル種別判定
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    paragraphs = []
    if ext == ".docx":
        text = extract_text_including_sdt(file_path)
        paragraphs = text.splitlines()
    elif ext in [".pdf"]:
        ocr = get_document_intelligence_ocr()
        result = ocr.analyze_document(file_path)
        ocr_paragraphs = getattr(result, "paragraphs", None)
        if ocr_paragraphs:
            lines = []
            for p in ocr_paragraphs:
                content = p.get("content") if isinstance(p, dict) else getattr(p, "content", "")
                if content:
                    lines.append(content)
            paragraphs = lines
            text = "\n".join(lines)
        else:
            return {
                "error": "PDF抽出で result.paragraphs.content が取得できませんでした。",
                "raw_text": "",
            }
    else:
        raise ValueError("対応していないファイル形式です")

    chunked = split_document_paragraphs(
        paragraphs, enable_tail_audit=True, audit_clause_boundaries=audit_clause_boundaries
    )
    if "error" in chunked:
        return chunked
    final_output = {
        "title": chunked["title"],
        "introduction": chunked["introduction"],
        "clauses": chunked["clauses"],
        "signature_section": chunked["signature_section"],
        "attachments": chunked["attachments"],
    }
    return final_output


if __name__ == "__main__":
    import tkinter as tk
    import os
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()  # メインウィンドウを非表示
    file_path = filedialog.askopenfilename(
        title="ドキュメントファイルを選択してください",
        filetypes=[
            ("Wordファイル", "*.docx"),
            ("PDFファイル", "*.pdf"),
            ("画像ファイル", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff"),
        ],
    )
    if not file_path:
        print("ファイルが選択されませんでした。処理を終了します。")
        exit(1)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist.")

    result = extract_text_from_document(file_path)
