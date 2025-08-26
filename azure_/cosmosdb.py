# pip install azure-cosmos

from os import environ
import logging
from datetime import datetime
from typing import Dict, List, Optional
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import (
    CosmosHttpResponseError,
    CosmosResourceNotFoundError,
    CosmosResourceExistsError,
)
import os
import uuid
from dotenv import load_dotenv
import streamlit as st


@st.cache_resource
def get_cosmosdb_client():
    """CosmosDBクライアントをキャッシュして返す"""
    load_dotenv()
    endpoint = os.getenv("COSMOSDB_CORE_ENDPOINT")
    key = os.getenv("COSMOSDB_CORE_API_KEY")
    return CosmosClient(url=endpoint, credential=key)


class AzureCosmosDB:
    def __init__(self):
        """CosmosDBクライアントの初期化（@st.cache_resource経由のみ）"""
        self.client = get_cosmosdb_client()

    # 既存のユーティリティメソッド -------------------

    def get_container_client(self, database_name: str, container_name: str):
        """コンテナクライアントを取得"""
        database = self.client.get_database_client(database_name)
        container = database.get_container_client(container_name)
        return container

    def upsert_to_container(
        self, container_name: str, data: dict, database_name: str = None
    ):
        """データをCosmos DBに登録する"""
        database = database_name
        container = self.get_container_client(database, container_name)

        # データにIDが含まれていない場合は追加
        if "id" not in data:
            data["id"] = str(uuid.uuid4())

        upsert_item = container.upsert_item(body=data)
        return upsert_item

    def delete_data_from_container_by_column(
        self,
        container_name: str,
        column_name: str,
        column_value: str,
        partition_key_column_name: str,
        database_name: str = None,
    ):
        """列と値を指定してデータを削除する"""
        database = database_name
        container = self.get_container_client(database, container_name)

        # クエリを使って指定したカラムに一致するアイテムを検索
        query = f"SELECT * FROM c WHERE c.{column_name} = @value"
        parameters = [{"name": "@value", "value": column_value}]

        # クエリを実行して一致するアイテムを取得
        items_to_delete = container.query_items(
            query=query, parameters=parameters, enable_cross_partition_query=True
        )

        # アイテムが見つかったら削除
        for item in items_to_delete:
            try:
                container.delete_item(
                    item=item, partition_key=item[partition_key_column_name]
                )
                print(f"アイテム {item['id']} を削除しました。")
            except CosmosResourceNotFoundError:
                print(f"アイテム {item['id']} は既に削除されています。")
            except Exception as e:
                print(f"アイテム {item['id']} の削除中にエラーが発生しました: {e}")

    def query_data_from_container(
        self,
        container_name: str,
        column_name: str = None,
        column_value: str = None,
        mode: int = 1,
        select_columns: list = None,
        database_name: str = None,
    ):
        """列と値を指定してデータを取得する"""
        database = database_name
        container = self.get_container_client(database, container_name)

        # モードに応じてクエリを変更
        if mode == 1:
            # 完全一致検索
            if column_name:
                query = f"SELECT {', '.join([f'c.{col}' for col in select_columns]) if select_columns else '*'} FROM c WHERE c.{column_name} = @value"
                parameters = [{"name": "@value", "value": column_value}]
            else:
                query = f"SELECT {', '.join([f'c.{col}' for col in select_columns]) if select_columns else '*'} FROM c"
                parameters = []
        elif mode == 2:
            # 部分一致検索
            query = f"SELECT {', '.join([f'c.{col}' for col in select_columns]) if select_columns else '*'} FROM c WHERE CONTAINS(c.{column_name}, @value)"
            parameters = [{"name": "@value", "value": column_value}]
        else:
            raise ValueError(
                "Invalid mode. Use 1 for exact match or 2 for partial match."
            )

        # クエリを実行して一致するアイテムを取得
        results = container.query_items(
            query=query, parameters=parameters, enable_cross_partition_query=True
        )
        return list(results)

    def search_container_by_query(
        self,
        container_name: str,
        query: str,
        parameters: list,
        database_name: str = None,
    ):
        """カスタムクエリを実行する"""
        database = database_name
        container = self.get_container_client(database, container_name)

        results = container.query_items(
            query=query, parameters=parameters, enable_cross_partition_query=True
        )
        return list(results)

    def search_similar_vectors(
        self,
        container_name: str,
        search_column_name: str,  # 検索対象のベクトル値を指定するカラム名（例: "embedding"）
        target_column_names: list,  # 検索結果として取得するカラム名のリスト
        search_word: str,  # 検索ワード
        get_emb_func,  # 検索ワードからベクトルを取得する関数（例: OpenAI埋め込みAPIなど）
        top_k: int = 1,
        database_name: str = None,
    ):
        """
        指定したワードに最も近いベクトルデータをコサイン類似度で検索し、類似度スコア付きで返す。

        Args:
            container_name (str): Cosmos DBのコンテナ名。
            search_column_name (str): 検索対象となるベクトルが格納されたカラム名。
            target_column_names (list): 検索結果として取得するカラム名のリスト。
            search_word (str): 類似度検索に使用する検索ワード。
            get_emb_func (callable): 検索ワードからベクトルを取得する関数。
            top_k (int, optional): 類似度が高い上位何件を取得するか。デフォルトは1件。
            database_name (str, optional): データベース名。未指定時はデフォルト。

        Returns:
            list: 類似度の高い上位 `top_k` 件の結果（各指定カラム値・id・SimilarityScoreを含む辞書のリスト）
        """
        database = database_name or self.default_database
        container = self.get_container_client(database, container_name)

        # 検索ワードからベクトルを取得
        query_embedding = get_emb_func(search_word)

        # クエリを組み立て
        select_cols = ", ".join([f"c.{col}" for col in target_column_names])
        query = f"""
            SELECT TOP @top_k c.id, {select_cols}, VectorDistance(c.{search_column_name}, @embedding) AS SimilarityScore
            FROM c
            ORDER BY VectorDistance(c.{search_column_name}, @embedding)
        """
        parameters = [
            {"name": "@top_k", "value": top_k},
            {"name": "@embedding", "value": query_embedding},
        ]

        items = container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )

        results = []
        for item in items:
            result_item = {"id": item["id"]}
            for col in target_column_names:
                result_item[col] = item.get(col)
            result_item["SimilarityScore"] = item.get(
                "SimilarityScore", item.get("similarity_score", None)
            )
            results.append(result_item)
        return results
