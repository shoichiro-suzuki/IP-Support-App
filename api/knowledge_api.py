from azure_.cosmosdb import AzureCosmosDB
from azure_.openai_service import AzureOpenAIService
from typing import List, Dict, Optional
import uuid
from datetime import datetime, timedelta, timezone


from datetime import datetime, timedelta, timezone
from api.contract_api import ContractAPI


JST = timezone(timedelta(hours=9))


class KnowledgeAPI:
    def __init__(self):
        self.cosmosdb = AzureCosmosDB()
        self.openai_service = AzureOpenAIService()
        self.contract_api = ContractAPI()

    def get_max_knowledge_number(self) -> int:
        """
        knowledge_entryコレクションから最大knowledge_numberを取得する
        """
        query = "SELECT VALUE MAX(c.knowledge_number) FROM c"
        results = self.cosmosdb.search_container_by_query(
            container_name="knowledge_entry",
            query=query,
            parameters=[],
            database_name="CONTRACT",
        )
        if results and results[0] is not None:
            return int(results[0])
        return 0

    def get_contract_types(self):
        """
        契約種別一覧を取得する
        """
        return self.contract_api.get_contract_types()

    def get_knowledge_list(
        self, contract_type: Optional[str] = None, search_text: Optional[str] = None
    ) -> List[Dict]:
        """
        ナレッジの一覧を取得する。フィルター条件を指定可能。
        Args:
            contract_type (str, optional): 契約種別でフィルター
            search_text (str, optional): テキスト検索でフィルター
        Returns:
            List[Dict]: ナレッジ一覧
        """
        query = "SELECT * FROM c WHERE 1=1"
        parameters = []

        if contract_type:
            query += " AND c.contract_type = @contract_type"
            parameters.append({"name": "@contract_type", "value": contract_type})

        if search_text:
            query += """ AND (
                CONTAINS(c.knowledge_title, @search_text) OR 
                CONTAINS(c.review_points, @search_text) OR 
                CONTAINS(c.action_plan, @search_text) OR
                CONTAINS(c.target_clause, @search_text) OR
                CONTAINS(c.clause_sample, @search_text)
            )"""
            parameters.append({"name": "@search_text", "value": search_text})

        results = self.cosmosdb.search_container_by_query(
            container_name="knowledge_entry",
            query=query,
            parameters=parameters,
            database_name="CONTRACT",
        )

        return results

    def get_knowledge_by_id(self, knowledge_id: str) -> Optional[Dict]:
        """
        指定されたIDのナレッジを取得する
        """
        results = self.cosmosdb.query_data_from_container(
            container_name="knowledge_entry",
            column_name="id",
            column_value=knowledge_id,
            database_name="CONTRACT",
        )
        return results[0] if results else None

    def save_knowledge(self, knowledge_data: Dict) -> Dict:
        """
        ナレッジを保存する
        """
        if "id" not in knowledge_data:
            knowledge_data["id"] = str(uuid.uuid4())

        JST = timezone(timedelta(hours=9))
        now_jst = datetime.now(JST)

        # 既存データがあればcreated_atを引き継ぐ
        existing = None
        if "id" in knowledge_data:
            existing = self.get_knowledge_by_id(knowledge_data["id"])
        if existing and "created_at" in existing:
            knowledge_data["created_at"] = existing["created_at"]
        else:
            knowledge_data["created_at"] = now_jst.isoformat()
        knowledge_data["updated_at"] = now_jst.isoformat()

        return self.cosmosdb.upsert_to_container(
            container_name="knowledge_entry",
            data=knowledge_data,
            database_name="CONTRACT",
        )

    def delete_knowledge(self, knowledge_data: Dict) -> Dict:
        """
        ナレッジを削除する
        """
        if "id" not in knowledge_data:
            raise ValueError("ID is required to delete knowledge.")

        return self.cosmosdb.delete_data_from_container_by_column(
            container_name="knowledge_entry",
            column_name="knowledge_number",
            column_value=knowledge_data["knowledge_number"],
            partition_key_column_name="knowledge_number",
            database_name="CONTRACT",
        )

    # def save_knowledge_draft(self, knowledge_data: Dict) -> Dict:
    #     """
    #     ナレッジをドラフトとして保存する
    #     """
    #     if "id" not in knowledge_data:
    #         knowledge_data["id"] = str(uuid.uuid4())

    #     JST = timezone(timedelta(hours=9))
    #     now_jst = datetime.now(JST)

    #     # 既存データがあればcreated_atを引き継ぐ
    #     existing = None
    #     if "id" in knowledge_data:
    #         existing = self.get_knowledge_by_id(knowledge_data["id"])
    #     if existing and "created_at" in existing:
    #         knowledge_data["created_at"] = existing["created_at"]
    #     else:
    #         knowledge_data["created_at"] = now_jst.isoformat()
    #     knowledge_data["updated_at"] = now_jst.isoformat()

    #     # record_status, approval_status のデフォルト
    #     if "record_status" not in knowledge_data:
    #         knowledge_data["record_status"] = "latest"
    #     if "approval_status" not in knowledge_data:
    #         knowledge_data["approval_status"] = "draft"

    #     # 旧statusフィールドは廃止
    #     if "status" in knowledge_data:
    #         del knowledge_data["status"]

    #     return self.cosmosdb.upsert_to_container(
    #         container_name="knowledge_entry",
    #         data=knowledge_data,
    #         database_name="CONTRACT",
    #     )

    # def save_knowledge_with_vectors(self, knowledge_data: Dict) -> Dict:
    #     """
    #     ナレッジをベクトル変換して保存する
    #     """
    #     # タイトル、審査観点、対応策、条項サンプルをベクトル化
    #     title_vector = self.openai_service.get_emb_3_small(
    #         knowledge_data.get("knowledge_title", "")
    #     )
    #     review_points_vector = self.openai_service.get_emb_3_small(
    #         knowledge_data.get("review_points", "")
    #     )
    #     action_vector = self.openai_service.get_emb_3_small(
    #         knowledge_data.get("action_plan", "")
    #     )
    #     clause_vector = self.openai_service.get_emb_3_small(
    #         knowledge_data.get("clause_sample", "")
    #     )

    #     JST = timezone(timedelta(hours=9))
    #     now_jst = datetime.now(JST)

    #     knowledge_data["review_points_vector"] = review_points_vector
    #     knowledge_data["action_vector"] = action_vector
    #     knowledge_data["clause_vector"] = clause_vector
    #     # 既存データがあればcreated_atを引き継ぐ
    #     existing = None
    #     if "id" in knowledge_data:
    #         existing = self.get_knowledge_by_id(knowledge_data["id"])

    #     if existing and "created_at" in existing:
    #         knowledge_data["created_at"] = existing["created_at"]
    #     else:
    #         knowledge_data["created_at"] = now_jst.isoformat()
    #     knowledge_data["updated_at"] = now_jst.isoformat()

    #     # record_status, approval_status のデフォルト
    #     if "record_status" not in knowledge_data:
    #         knowledge_data["record_status"] = "latest"
    #     if "approval_status" not in knowledge_data:
    #         knowledge_data["approval_status"] = "draft"

    #     return self.save_knowledge_draft(knowledge_data)

    # def update_approval_status(self, knowledge_id: str, new_status: str) -> Dict:
    #     """
    #     approval_statusを変更する（draft, submitted, approved, revoked）
    #     """
    #     JST = timezone(timedelta(hours=9))
    #     now_jst = datetime.now(JST)
    #     knowledge = self.get_knowledge_by_id(knowledge_id)
    #     if knowledge:
    #         knowledge["approval_status"] = new_status
    #         knowledge["updated_at"] = now_jst.isoformat()
    #         if new_status == "approved":
    #             knowledge["approved_at"] = now_jst.isoformat()
    #         return self.cosmosdb.upsert_to_container(
    #             container_name="knowledge_entry",
    #             data=knowledge,
    #             database_name="CONTRACT",
    #         )
    #     return None
