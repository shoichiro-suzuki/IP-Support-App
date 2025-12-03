"""
knowledge_entry から数件を取得してサンプルJSONを生成するスクリプト
例:
    python scripts/export_knowledge_samples.py --limit 5
    python scripts/export_knowledge_samples.py --contract-type NDA --search-text 秘密保持
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.knowledge_api import KnowledgeAPI


FIELDS = [
    "id",
    "knowledge_number",
    "contract_type",
    "knowledge_title",
    "target_clause",
    "review_points",
    "action_plan",
    "clause_sample",
]


def sanitize_entry(entry: dict) -> dict:
    """必要フィールドのみに絞って返す"""
    return {k: entry.get(k) for k in FIELDS if k in entry}


def main():
    parser = argparse.ArgumentParser(
        description="knowledge_entry からサンプルデータを取得してJSON保存"
    )
    parser.add_argument(
        "--contract-type",
        help="契約種別でフィルタ",
    )
    parser.add_argument(
        "--search-text",
        help="テキスト検索でフィルタ",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="先頭から取得する件数（デフォルト5）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "review-ui-llm-support" / "knowledge_samples.json",
        help="出力先パス（デフォルト: docs/review-ui-llm-support/knowledge_samples.json）",
    )
    args = parser.parse_args()

    api = KnowledgeAPI()
    records = api.get_knowledge_list(
        contract_type=args.contract_type, search_text=args.search_text
    )
    samples = [sanitize_entry(r) for r in records[: args.limit]]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(samples, ensure_ascii=False, indent=2), "utf-8")
    print(f"Saved {len(samples)} records to {args.output}")


if __name__ == "__main__":
    main()
