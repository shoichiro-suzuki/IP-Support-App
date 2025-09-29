from azure_.cosmosdb import AzureCosmosDB
from azure_.openai_service import AzureOpenAIService
import csv
import io
import re
from datetime import datetime


class ContractAPI:
    def __init__(self):
        self.cosmosdb_client = AzureCosmosDB().client
        self.openai_service = AzureOpenAIService()

    def search_similar_clauses(self, search_clause: str, top_k: int = 5):
        """
        条項のテキストから類似する条項をベクトル検索する

        Args:
            search_clause (str): 検索対象の条項テキスト
            top_k (int): 取得する類似条項の数

        Returns:
            list: 類似度の高い上位条項（id, clause, clause_vector, review_points, action_plan, SimilarityScore）
        """
        db = self.cosmosdb_client.get_database_client("CONTRACT")
        container = db.get_container_client("clause_entry")

        # 検索テキストをベクトル化
        query_embedding = self.openai_service.get_emb_3_small(search_clause)

        # コサイン類似度による検索クエリ
        query = f"""
            SELECT TOP @top_k 
                c.id,
                c.clause,
                c.review_points,
                c.action_plan,
                VectorDistance(c.clause_vector, @embedding) AS SimilarityScore
            FROM c
            WHERE c.clause_vector != null
            ORDER BY VectorDistance(c.clause_vector, @embedding)
        """
        parameters = [
            {"name": "@top_k", "value": top_k},
            {"name": "@embedding", "value": query_embedding},
        ]
        try:
            items = container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        except Exception as e:
            print(f"Error occurred: {e}")

        return list(items)

    def get_knowledge_entries(self, contract_type: str):
        """
        contract_typeが一致または"汎用"のナレッジエントリーを取得する

        Args:
            contract_type (str): 契約種別

        Returns:
            list: ナレッジエントリーのリスト
        """
        db = self.cosmosdb_client.get_database_client("CONTRACT")
        container = db.get_container_client("knowledge_entry")

        query = """
            SELECT
                c.id,
                c.knowledge_number,
                c.version,
                c.contract_type,
                c.target_clause,
                c.knowledge_title,
                c.review_points,
                c.action_plan,
                c.clause_sample
            FROM c
            WHERE c.contract_type = @contract_type OR c.contract_type = '汎用'
        """
        parameters = [{"name": "@contract_type", "value": contract_type}]

        try:
            items = container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        except Exception as e:
            print(f"Error occurred: {e}")
            return []

        return list(items)

    def get_contract_type_value_by_id(self, contract_type_id):
        """
        contract_typeのidを指定して、contract_typeの値（例：秘密保持）を取得する
        """
        db = self.cosmosdb_client.get_database_client("CONTRACT")
        container = db.get_container_client("contract_type")
        query = f"SELECT c.contract_type FROM c WHERE c.id = '{contract_type_id}'"
        results = list(
            container.query_items(query=query, enable_cross_partition_query=True)
        )
        if results:
            return results[0].get("contract_type")
        return None

    def get_approved_contracts(self):
        """
        承認済みの契約一覧を取得する
        """
        db = self.cosmosdb_client.get_database_client("CONTRACT")
        container = db.get_container_client("contract_master")
        query = "SELECT * FROM c WHERE c.approval_status = 'approved' AND c.record_status = 'latest'"
        return list(
            container.query_items(query=query, enable_cross_partition_query=True)
        )

    def get_contract_types(self):
        db = self.cosmosdb_client.get_database_client("CONTRACT")
        container = db.get_container_client("contract_type")
        return list(container.read_all_items())

    def get_draft_contracts(self):
        db = self.cosmosdb_client.get_database_client("CONTRACT")
        container = db.get_container_client("contract_master")
        query = "SELECT * FROM c WHERE c.approval_status = 'draft' OR c.approval_status = 'submitted'"
        return list(
            container.query_items(query=query, enable_cross_partition_query=True)
        )

    def get_contract_by_id(self, contract_id):
        db = self.cosmosdb_client.get_database_client("CONTRACT")
        container = db.get_container_client("contract_master")
        query = f"SELECT * FROM c WHERE c.id = '{contract_id}'"
        results = list(
            container.query_items(query=query, enable_cross_partition_query=True)
        )
        return results[0] if results else None

    def upsert_contract(self, data):
        db = self.cosmosdb_client.get_database_client("CONTRACT")
        container = db.get_container_client("contract_master")
        return container.upsert_item(body=data)

    def upsert_clause_entry(self, data):
        db = self.cosmosdb_client.get_database_client("CONTRACT")
        container = db.get_container_client("clause_entry")
        return container.upsert_item(body=data)

    def export_examination_result_to_csv(
        self,
        analyzed_clauses: list,
        original_clauses: list,
        contract_info: dict,
        clause_review_status: dict,
        examination_datetime: str = None,
        llm_model: str = None
    ) -> str:
        """
        審査結果を2テーブル構造のCSV形式で出力

        Args:
            analyzed_clauses: 審査結果データ
            original_clauses: 元の条項データ
            contract_info: 契約基本情報
            clause_review_status: 条項審査状態
            examination_datetime: 審査日時（未指定時は現在時刻）
            llm_model: 使用LLMモデル

        Returns:
            str: CSV形式の文字列データ
        """
        if examination_datetime is None:
            examination_datetime = datetime.now().strftime("%Y%m%d%H%M%S")

        if llm_model is None:
            llm_model = "gpt-4.1"

        # 契約IDを生成
        contract_id = f"EXAM_{examination_datetime}"

        # 状態マッピング
        status_map = {
            "unreviewed": "未審査",
            "reviewed_safe": "審査済み",
            "reviewed_concern": "審査済み"
        }

        concern_map = {
            "unreviewed": "未実施",
            "reviewed_safe": "なし",
            "reviewed_concern": "あり"
        }

        # StringIOを使用してCSV文字列を作成
        output = io.StringIO()

        # BOM付きで日本語対応
        output.write('\ufeff')

        # 契約基本情報テーブル
        output.write("# 契約基本情報\n")
        contract_headers = [
            "契約ID", "審査日時", "契約タイトル", "契約種別",
            "当事者", "背景情報", "審査実行者", "LLMモデル"
        ]

        writer = csv.writer(output)
        writer.writerow(contract_headers)

        # 審査日時をフォーマット
        formatted_datetime = datetime.strptime(examination_datetime, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")

        contract_row = [
            contract_id,
            formatted_datetime,
            contract_info.get("title", ""),
            contract_info.get("contract_type", ""),
            contract_info.get("partys", ""),
            contract_info.get("background", ""),
            "システム",
            llm_model
        ]
        writer.writerow(contract_row)

        # 空行とセクション区切り
        output.write("\n# 条項審査結果\n")

        # 条項審査結果テーブル
        clause_headers = [
            "契約ID", "条項番号", "条項内容", "審査状態", "懸念事項有無",
            "懸念事項", "修正条文", "関連ナレッジID", "関連ナレッジ数"
        ]
        writer.writerow(clause_headers)

        # analyzed_clausesを辞書に変換（高速検索用）
        analyzed_dict = {}
        if analyzed_clauses:
            for analyzed in analyzed_clauses:
                clause_number = analyzed.get("clause_number", "")
                analyzed_dict[clause_number] = analyzed

        # 条項データを処理
        for clause in original_clauses:
            clause_number = clause.get("clause_number", "")
            clause_content = clause.get("clause", "")

            # 改行文字をスペースに変換し、連続スペースを単一スペースに統一
            clause_content = clause_content.replace("\n", " ").replace("\r", " ")
            clause_content = re.sub(r'\s+', ' ', clause_content).strip()

            # 審査状態を取得
            review_status = clause_review_status.get(clause_number, "unreviewed")
            audit_status = status_map.get(review_status, "未審査")
            concern_status = concern_map.get(review_status, "未実施")

            # 審査結果を取得
            analyzed = analyzed_dict.get(clause_number, {})
            concern = analyzed.get("concern", "")
            amendment_clause = analyzed.get("amendment_clause", "")
            knowledge_ids = analyzed.get("knowledge_ids", [])

            # concernとamendment_clauseがリストの場合は文字列に変換
            if isinstance(concern, list):
                concern = " ".join(str(x).strip() for x in concern if x)
            elif concern:
                concern = str(concern)
            else:
                concern = ""

            if isinstance(amendment_clause, list):
                amendment_clause = " ".join(str(x).strip() for x in amendment_clause if x)
            elif amendment_clause:
                amendment_clause = str(amendment_clause)
            else:
                amendment_clause = ""

            # 改行文字をスペースに変換し、連続スペースを単一スペースに統一
            concern = re.sub(r'\s+', ' ', concern.replace("\n", " ").replace("\r", " ")).strip()
            amendment_clause = re.sub(r'\s+', ' ', amendment_clause.replace("\n", " ").replace("\r", " ")).strip()

            # ナレッジIDをカンマ区切り文字列に変換
            knowledge_ids_str = ""
            knowledge_count = 0
            if knowledge_ids:
                if isinstance(knowledge_ids, list):
                    knowledge_ids_str = ",".join(str(kid) for kid in knowledge_ids)
                    knowledge_count = len(knowledge_ids)
                else:
                    knowledge_ids_str = str(knowledge_ids)
                    knowledge_count = 1

            clause_row = [
                contract_id,
                clause_number,
                clause_content,
                audit_status,
                concern_status,
                concern,
                amendment_clause,
                knowledge_ids_str,
                knowledge_count
            ]
            writer.writerow(clause_row)

        # CSV文字列を取得
        csv_content = output.getvalue()
        output.close()

        return csv_content
