from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Callable, Optional

from jsonschema import validate, ValidationError

from azure_.openai_service import AzureOpenAIService


BOUNDARY_TOKEN_PREFIX = "---BOUNDARY:"
BOUNDARY_TOKEN_SUFFIX = "---"


@dataclass
class BoundaryRule:
    id_prefix: str
    section_name: str
    strong_patterns: list[str]
    weak_patterns: list[str]
    max_candidates: int


@dataclass
class BoundaryCandidate:
    id: str
    line_index: int
    score: int
    section_name: str


@dataclass
class BoundaryPreprocessOptions:
    preserve_empty_lines: bool = True
    line_number_width: int = 3


@dataclass
class LlmAuditConfig:
    max_retries: int = 1


def default_tail_boundary_rules() -> list[BoundaryRule]:
    signature_strong = [
        r"署名",
        r"記名",
        r"押印",
        r"捺印",
        r"締結の証",
        r"署名押印欄",
        r"IN WITNESS WHEREOF",
        r"Signed\b",
        r"Signature\b",
        r"\d{4}[年/-]\d{1,2}[月/-]\d{1,2}日?",
        r"（甲）",
        r"（乙）",
        r"\bCompany\b",
        r"\bAddress\b",
        r"\bName\b",
        r"\bTitle\b",
    ]
    signature_weak = [
        r"印",
    ]
    attach_strong = [
        r"別紙",
        r"添付",
        r"別添",
        r"付録",
        r"Annex\b",
        r"Appendix\b",
        r"Attachment\b",
        r"Schedule\b",
        r"別紙\s*\d+",
        r"別紙\s*第\d+",
        r"Appendix\s+[A-Z]",
        r"Annex\s+\d+",
    ]
    return [
        BoundaryRule(
            id_prefix="SIG_CAND",
            section_name="signature",
            strong_patterns=signature_strong,
            weak_patterns=signature_weak,
            max_candidates=3,
        ),
        BoundaryRule(
            id_prefix="ATTACH_CAND",
            section_name="attachments",
            strong_patterns=attach_strong,
            weak_patterns=[],
            max_candidates=5,
        ),
    ]


class BoundaryAuditService:
    def __init__(
        self,
        llm_call: Optional[Callable[[list[dict]], str]] = None,
        prompt_path: Optional[str] = None,
        schema_path: Optional[str] = None,
    ):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self._llm_call = llm_call or self._default_llm_call
        self._prompt_path = prompt_path or os.path.join(
            base_dir, "prompts", "document_input_boundary_audit.md"
        )
        self._schema_path = schema_path or os.path.join(
            base_dir, "configs", "document_input", "boundary_audit.schema.json"
        )
        self._system_prompt = self._load_text(self._prompt_path)
        self._schema = self._load_schema(self._schema_path)

    def build_audit_context(
        self,
        paragraphs: list[str],
        boundary_rules: list[BoundaryRule],
        preprocess: BoundaryPreprocessOptions,
    ) -> dict:
        lines = [line.rstrip("\n") for line in paragraphs]
        if not preprocess.preserve_empty_lines:
            lines = [line for line in lines if line.strip()]
        candidates = self._collect_candidates(lines, boundary_rules)
        lines_with_tokens = self._insert_boundary_tokens(lines, candidates)
        numbered_lines = self._add_line_numbers(
            lines_with_tokens, preprocess.line_number_width
        )
        return {
            "lines": lines_with_tokens,
            "numbered_text": "\n".join(numbered_lines),
            "candidates": candidates,
        }

    def audit(
        self,
        paragraphs: list[str],
        boundary_rules: list[BoundaryRule],
        preprocess: BoundaryPreprocessOptions,
        llm_config: Optional[LlmAuditConfig] = None,
    ) -> dict:
        config = llm_config or LlmAuditConfig()
        context = self.build_audit_context(paragraphs, boundary_rules, preprocess)
        messages = [
            {"role": "system", "content": self._system_prompt},
            {
                "role": "user",
                "content": "以下の行番号付きテキストを監査してください。\n"
                + context["numbered_text"],
            },
        ]
        last_error = None
        for _ in range(config.max_retries + 1):
            response = self._llm_call(messages)
            parsed = self._parse_and_validate(response)
            if parsed is not None:
                parsed["lines"] = context["lines"]
                parsed["raw_response"] = response
                normalized = self._normalize_final_sections(parsed, len(context["lines"]))
                return normalized
            last_error = response
        return self._fallback_result(context["lines"], last_error)

    @staticmethod
    def extract_sections(lines: list[str], final_sections: list[dict]) -> dict:
        clause_last = ""
        signature = ""
        attachments = []
        for section in final_sections:
            name = section.get("name")
            start = section.get("start_line", 0)
            end = section.get("end_line", 0)
            if start < 1 or end < start or end > len(lines):
                continue
            chunk = [
                line
                for line in lines[start - 1 : end]
                if not _is_boundary_line(line)
            ]
            text = "\n".join(chunk).strip()
            if not text:
                continue
            if name == "clause_last":
                clause_last = text
            elif name == "signature":
                signature = text if not signature else signature + "\n" + text
            elif name == "attachments":
                attachments.append(text)
        return {
            "clause_last_text": clause_last,
            "signature_text": signature,
            "attachments": attachments,
        }

    def _default_llm_call(self, messages: list[dict]) -> str:
        service = AzureOpenAIService()
        response = service.get_openai_response_gpt41(messages)
        return response or ""

    def _parse_and_validate(self, response: str) -> Optional[dict]:
        try:
            payload = self._extract_json(response)
            if payload is None:
                return None
            validate(instance=payload, schema=self._schema)
        except (json.JSONDecodeError, ValidationError, TypeError):
            return None
        return payload

    def _normalize_final_sections(self, result: dict, max_lines: int) -> dict:
        final_sections = result.get("final_sections", [])
        if result.get("verdict") == "reject":
            return self._fallback_result(result.get("lines", []), result.get("raw_response"))
        if not final_sections:
            return self._fallback_result(result.get("lines", []), result.get("raw_response"))
        sorted_sections = sorted(final_sections, key=lambda x: x.get("start_line", 0))
        lines = result.get("lines", [])
        if not lines:
            return self._fallback_result(result.get("lines", []), result.get("raw_response"))
        first_start = sorted_sections[0].get("start_line", 0)
        if first_start < 1 or first_start > max_lines:
            return self._fallback_result(result.get("lines", []), result.get("raw_response"))
        if not self._gap_is_boundary_only(lines, 1, first_start - 1):
            return self._fallback_result(result.get("lines", []), result.get("raw_response"))
        last_end = 0
        for section in sorted_sections:
            start = section.get("start_line", 0)
            end = section.get("end_line", 0)
            if start < 1 or end < start or end > max_lines:
                return self._fallback_result(result.get("lines", []), result.get("raw_response"))
            if last_end and not self._gap_is_boundary_only(lines, last_end + 1, start - 1):
                return self._fallback_result(result.get("lines", []), result.get("raw_response"))
            last_end = end
        if not self._gap_is_boundary_only(lines, last_end + 1, max_lines):
            return self._fallback_result(result.get("lines", []), result.get("raw_response"))
        result["final_sections"] = sorted_sections
        return result

    def _fallback_result(self, lines: list[str], raw_response: Optional[str]) -> dict:
        return {
            "verdict": "reject",
            "boundaries": [],
            "final_sections": [
                {"name": "clause_last", "start_line": 1, "end_line": len(lines)}
            ],
            "warnings": [
                {"code": "NEEDS_HUMAN_REVIEW", "message": "LLM監査に失敗"}
            ],
            "lines": lines,
            "raw_response": raw_response or "",
        }

    def _collect_candidates(
        self, lines: list[str], boundary_rules: list[BoundaryRule]
    ) -> list[BoundaryCandidate]:
        candidates = []
        date_lines = self._find_date_lines(lines)
        for rule in boundary_rules:
            raw_candidates = []
            for idx, line in enumerate(lines):
                if not line.strip():
                    continue
                strong = self._matches_any(line, rule.strong_patterns)
                if strong:
                    raw_candidates.append((idx, 2))
                    continue
                if rule.weak_patterns and self._matches_any(line, rule.weak_patterns):
                    if rule.id_prefix == "SIG_CAND" and self._is_signature_weak_hit(
                        line, idx, date_lines
                    ):
                        raw_candidates.append((idx, 1))
            merged = self._merge_close_candidates(raw_candidates)
            merged = sorted(merged, key=lambda x: x[0])[: rule.max_candidates]
            for count, (line_index, score) in enumerate(merged, 1):
                candidates.append(
                    BoundaryCandidate(
                        id=f"{rule.id_prefix}_{count}",
                        line_index=line_index,
                        score=score,
                        section_name=rule.section_name,
                    )
                )
        return candidates

    def _merge_close_candidates(self, candidates: list[tuple[int, int]]) -> list[tuple[int, int]]:
        if not candidates:
            return []
        merged = []
        for line_index, score in sorted(candidates, key=lambda x: x[0]):
            if not merged:
                merged.append((line_index, score))
                continue
            last_index, last_score = merged[-1]
            if abs(line_index - last_index) <= 2:
                if score > last_score:
                    merged[-1] = (line_index, score)
                continue
            merged.append((line_index, score))
        return merged

    def _is_signature_weak_hit(
        self, line: str, idx: int, date_lines: set[int]
    ) -> bool:
        role_markers = ["代表", "役職", "Name", "Title", "Company", "（甲）", "（乙）"]
        if any(marker in line for marker in role_markers):
            return True
        for date_idx in date_lines:
            if abs(date_idx - idx) <= 5:
                return True
        return False

    def _find_date_lines(self, lines: list[str]) -> set[int]:
        date_pattern = re.compile(r"\d{4}[年/-]\d{1,2}[月/-]\d{1,2}日?")
        return {idx for idx, line in enumerate(lines) if date_pattern.search(line)}

    def _insert_boundary_tokens(
        self, lines: list[str], candidates: list[BoundaryCandidate]
    ) -> list[str]:
        insert_map = {}
        for candidate in candidates:
            insert_map.setdefault(candidate.line_index, []).append(candidate)
        result = []
        for idx, line in enumerate(lines):
            if idx in insert_map:
                for candidate in insert_map[idx]:
                    result.append(_format_boundary_token(candidate.id))
            result.append(line)
        return result

    def _add_line_numbers(self, lines: list[str], width: int) -> list[str]:
        return [f"[{i:0{width}d}] {line}" for i, line in enumerate(lines, 1)]

    def _matches_any(self, line: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            if re.search(pattern, line, flags=re.IGNORECASE):
                return True
        return False

    def _gap_is_boundary_only(self, lines: list[str], start: int, end: int) -> bool:
        if start > end:
            return True
        start_index = max(start - 1, 0)
        end_index = min(end, len(lines))
        for line in lines[start_index:end_index]:
            if not _is_boundary_line(line):
                return False
        return True

    def _extract_json(self, text: str) -> Optional[dict]:
        if not text:
            return None
        cleaned = (
            text.replace("```json", "")
            .replace("```", "")
            .replace("\n", "")
            .strip()
        )
        if cleaned.startswith("{") and cleaned.endswith("}"):
            return json.loads(cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return json.loads(cleaned[start : end + 1])

    def _load_text(self, path: str) -> str:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Prompt file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def _load_schema(self, path: str) -> dict:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Schema file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def split_tail_sections(
    paragraphs: list[str],
    llm_config: Optional[LlmAuditConfig] = None,
    llm_call: Optional[Callable[[list[dict]], str]] = None,
) -> dict:
    service = BoundaryAuditService(llm_call=llm_call)
    rules = default_tail_boundary_rules()
    preprocess = BoundaryPreprocessOptions(preserve_empty_lines=True, line_number_width=3)
    audit_result = service.audit(paragraphs, rules, preprocess, llm_config)
    sections = service.extract_sections(
        audit_result["lines"], audit_result["final_sections"]
    )
    if not sections["clause_last_text"]:
        sections["clause_last_text"] = "\n".join(paragraphs).strip()
    return sections


def _format_boundary_token(boundary_id: str) -> str:
    return f"{BOUNDARY_TOKEN_PREFIX}{boundary_id}{BOUNDARY_TOKEN_SUFFIX}"


def _is_boundary_line(line: str) -> bool:
    return line.startswith(BOUNDARY_TOKEN_PREFIX) and line.endswith(BOUNDARY_TOKEN_SUFFIX)
