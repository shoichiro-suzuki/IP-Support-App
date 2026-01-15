# pip install python-docx


def extract_text_from_document(file_path: str) -> dict:
    import os
    import mimetypes
    from docx import Document
    from azure_.documentintelligence import get_document_intelligence_ocr
    from azure_.openai_service import AzureOpenAIService
    import re
    import json

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
    if ext == ".docx":
        text = extract_text_including_sdt(file_path)
    elif ext in [".pdf"]:
        ocr = get_document_intelligence_ocr()
        result = ocr.analyze_document(file_path)
        text = getattr(result, "content", "")
        # OCR後、機械的なチャンキング前に <!-- ... --> 形式のコメントをすべて削除
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        text = re.sub(r"[#*`>\-]", "", text)
    else:
        raise ValueError("対応していないファイル形式です")

    # --- 機械的なチャンキング ---
    def chunk_by_clauses(text):
        import re

        # 区切りパターンをリストで管理
        CLAUSE_PATTERNS = [
            r"第[0-9一二三四五六七八九十百千]+条",  # 日本語条文
            r"Article\s+\d+",  # 英文条文
            # 追加パターンがあればここに追記
        ]
        clause_pattern = r"(" + "|".join(CLAUSE_PATTERNS) + r")"

        # 全角数字を半角数字に正規化
        def z2h_num(s):
            return s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))

        text_norm = z2h_num(text)
        parts = re.split(clause_pattern, text_norm)
        title = ""
        introduction = ""
        clauses = []
        signature_section = ""
        attachments = []
        if len(parts) > 1:
            intro = parts[0].strip()
            lines = intro.splitlines()
            if lines:
                title = lines[0].strip()
                introduction = "\n".join(lines[1:]).strip()
            else:
                title = intro
                introduction = ""
            for i in range(1, len(parts) - 1, 2):
                clause_marker = parts[i]
                # 条文番号抽出: 日本語・英語両対応
                if clause_marker.startswith("第"):
                    clause_number = clause_marker.replace("第", "").replace("条", "")
                elif clause_marker.lower().startswith("article"):
                    clause_number = (
                        clause_marker.split()[1]
                        if len(clause_marker.split()) > 1
                        else ""
                    )
                else:
                    clause_number = clause_marker
                clause_title = clause_marker
                clause_text_body = parts[i + 1].strip()
                clause_text = (
                    f"{clause_title}\n{clause_text_body}"
                    if clause_text_body
                    else clause_title
                )
                if i + 2 >= len(parts):
                    clause_lines = clause_text.splitlines()
                    sig_keywords = [
                        "署名",
                        "記名",
                        "押印",
                        "印",
                        "以上",
                        "IN WITNESS WHEREOF",
                    ]
                    sig_idx = -1
                    for idx, l in enumerate(clause_lines):
                        if any(k in l for k in sig_keywords):
                            sig_idx = idx
                            break
                    if sig_idx != -1:
                        clause_text_main = "\n".join(clause_lines[:sig_idx]).strip()
                        signature_section = "\n".join(clause_lines[sig_idx:]).strip()
                        clause_text = clause_text_main
                        # 署名セクションの後に別紙があればattachmentsとして保存
                        # 残りの行を取得
                        attachment_lines = clause_lines[sig_idx + 1 :]
                        if attachment_lines:
                            # 別紙キーワード
                            att_keywords = [
                                "別紙",
                                "添付",
                                "Annex",
                                "Appendix",
                                "Attachment",
                            ]
                            current_attachment = []
                            for line in attachment_lines:
                                if any(k in line for k in att_keywords):
                                    if current_attachment:
                                        attachments.append(
                                            "\n".join(current_attachment).strip()
                                        )
                                        current_attachment = []
                                    current_attachment.append(line)
                                else:
                                    if current_attachment:
                                        current_attachment.append(line)
                            if current_attachment:
                                attachments.append(
                                    "\n".join(current_attachment).strip()
                                )
                clauses.append(
                    {
                        "id": len(clauses) + 1,
                        "clause_number": clause_number,
                        "text": clause_text,
                    }
                )

        else:
            lines = text_norm.splitlines()
            if lines:
                title = lines[0].strip()
                introduction = "\n".join(lines[1:]).strip()
            else:
                title = text_norm
                introduction = ""
            attachments = []
        # attachmentsが存在する場合、signature_sectionからattachmentsの内容を除外
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

    chunked = chunk_by_clauses(text)

    # LLMで結合すべきidのみを返すように指示
    openai = AzureOpenAIService()
    system_prompt = f"""
あなたは優秀な契約書解析AIです。
契約書の条文を「第X条」で機械的に分割したJSONデータ（id, clause_number, textを持つ）を提供します。
ただし、条文中に「第X条に従い」などの引用があると、不適当に分割されている可能性がある。
あなたの役割は、契約書の文脈を考慮して、隣り合うclause_numberの文章を結合すべき方が適当と思われるidのリストのみを出力してください。
例えば、id=2,3,4が結合すべき場合は[2,3,4]のように出力します。複数グループある場合は[[2,3],[5,6]]のように出力します。
結合しなくてよい場合は空リスト[]を返してください。
出力は必ずJSON形式でお願いします。

### 出力形式:
```json
[[2,3,4],[5,6]]
```
"""
    prompt = "### 条文リスト:\n" + json.dumps(
        chunked["clauses"], ensure_ascii=False, indent=2
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    try:
        result = openai.get_openai_response_gpt41(messages)
        if isinstance(result, str):
            result = (
                result.replace("```json", "")
                .replace("```", "")
                .replace("\n", "")
                .replace("\\", "")
                .strip()
            )
    except Exception:
        result = ""

    def is_json(s: str) -> bool:
        try:
            json.loads(s)
            return True
        except Exception:
            return False

    result_text = result if isinstance(result, str) else ""
    if not is_json(result_text):
        return {
            "error": "LLM補正に失敗しました。手動修正してください。",
            "raw_text": text,
        }

    # LLM補正のid結合指示を反映して条文を結合
    import copy

    clauses = copy.deepcopy(chunked["clauses"])
    merge_groups = json.loads(result_text)
    merged = []
    used_ids = set()
    for group in merge_groups:
        if not group:
            continue
        # group: [2,3,4] または 2 の場合もあるので、intならリスト化
        if isinstance(group, int):
            group = [group]
        group_clauses = [c for c in clauses if c["id"] in group]
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
    # 結合されなかったものを追加
    for c in clauses:
        if c["id"] not in used_ids:
            merged.append(c)
    # id順にソート
    merged = sorted(merged, key=lambda x: x["id"])
    final_output = {
        "title": chunked["title"],
        "introduction": chunked["introduction"],
        "clauses": merged,
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
