from azure_.cosmosdb import AzureCosmosDB
from azure_.openai_service import AzureOpenAIService


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
