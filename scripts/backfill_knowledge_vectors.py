import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.knowledge_api import KnowledgeAPI


def main():
    parser = argparse.ArgumentParser(
        description="knowledge_entry にベクトルフィールドを一括付与するスクリプト"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="既存ベクトルがあっても上書きする",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="処理件数を制限する（先頭から）",
    )
    args = parser.parse_args()

    api = KnowledgeAPI()
    result = api.backfill_vectors(force=args.force, limit=args.limit)
    print(result)


if __name__ == "__main__":
    # カレントがプロジェクトルートでない場合を考慮しパス調整
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.append(str(root))
    main()
