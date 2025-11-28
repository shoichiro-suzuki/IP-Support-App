from azure_.cosmosdb import AzureCosmosDB
from azure_.openai_service import AzureOpenAIService
from typing import List, Dict, Optional
import uuid
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

        now_jst = datetime.now(JST)

        # 既存データがあればcreated_atを引き継ぐ
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

    def add_vectors_to_knowledge(
        self, knowledge_data: Dict, force: bool = False
    ) -> Dict | None:
        """
        ナレッジ1件にベクトルフィールドを付与して保存する。

        Args:
            knowledge_data: ナレッジレコード
            force: 既存ベクトルがあっても上書きする場合 True
        Returns:
            更新後のレコード。入力が空でベクトル生成できない場合は None
        """

        def _embed_if_needed(field: str, text: str | None):
            if not text or not str(text).strip():
                return None
            if not force and knowledge_data.get(field):
                return None
            return self.openai_service.get_emb_3_small(text)

        updates = {}
        clause_vec = _embed_if_needed(
            "clause_sample_vector", knowledge_data.get("clause_sample")
        )
        risk_vec = _embed_if_needed(
            "risk_description_vector", knowledge_data.get("review_points")
        )
        action_vec = _embed_if_needed(
            "action_plan_vector", knowledge_data.get("action_plan")
        )
        if clause_vec is not None:
            updates["clause_sample_vector"] = clause_vec
        if risk_vec is not None:
            updates["risk_description_vector"] = risk_vec
        if action_vec is not None:
            updates["action_plan_vector"] = action_vec

        if not updates:
            return None

        knowledge_data.update(updates)
        return self.save_knowledge(knowledge_data)

    def backfill_vectors(self, force: bool = False, limit: int | None = None):
        """
        既存knowledge_entryにベクトルフィールドを付与して保存する。
        """
        records = self.get_knowledge_list()
        if limit:
            records = records[:limit]
        updated = 0
        skipped = 0
        for rec in records:
            res = self.add_vectors_to_knowledge(rec, force=force)
            if res:
                updated += 1
            else:
                skipped += 1
        return {"updated": updated, "skipped": skipped, "total": len(records)}

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
    
