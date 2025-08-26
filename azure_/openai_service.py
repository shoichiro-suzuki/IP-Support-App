# pip install openai
# pip install python-dotenv

from dotenv import load_dotenv
from openai import AzureOpenAI
import os
import streamlit as st


@st.cache_resource
def get_openai_client():
    """OpenAIクライアントをキャッシュして返す"""
    load_dotenv()
    return AzureOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        api_version=os.getenv("OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("OPENAI_API_BASE"),
    )


class AzureOpenAIService:
    """
    Azure OpenAI サービスへの接続・応答取得を管理するクラス。
    通常用とSwedenCentral用の2種類のクライアントを内部で保持。
    """

    def __init__(self):
        self.client = get_openai_client()

    def get_emb_3_small(self, doc):
        response = (
            self.client.embeddings.create(input=doc, model="text-embedding-3-small")
            .data[0]
            .embedding
        )
        return response

    def get_openai_response_o1(self, messages):
        response = self.client.chat.completions.create(
            model="o1",
            messages=messages,
        )
        answer = response.choices[0].message.content
        return answer

    def get_openai_response_o1_mini(self, messages):
        response = self.client.chat.completions.create(
            model="o1-mini",
            messages=messages,
        )
        answer = response.choices[0].message.content
        return answer

    def get_openai_response_o3_mini(self, messages):
        response = self.client.chat.completions.create(
            model="o3-mini",
            messages=messages,
        )
        answer = response.choices[0].message.content
        return answer

    def get_openai_response_o3(self, messages):
        response = self.client.chat.completions.create(
            model="o3",
            messages=messages,
        )
        answer = response.choices[0].message.content
        return answer

    def get_openai_response_o4_mini(self, messages):
        response = self.client.chat.completions.create(
            messages=messages,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model="o4-mini",
        )
        answer = response.choices[0].message.content
        return answer

    def get_openai_response_gpt41(self, messages):
        response = self.client.chat.completions.create(
            messages=messages,
            temperature=0.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model="gpt-4.1",
        )
        answer = response.choices[0].message.content
        return answer

    def get_openai_response_gpt41mini(self, messages):
        response = self.client.chat.completions.create(
            messages=messages,
            temperature=0.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model="gpt-4.1-mini",
        )
        answer = response.choices[0].message.content
        return answer

    def get_openai_response_gpt41nano(self, messages):
        response = self.client.chat.completions.create(
            messages=messages,
            temperature=0.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model="gpt-4.1-nano",
        )
        answer = response.choices[0].message.content
        return answer

    def get_openai_response_gpt5(self, messages):
        response = self.client.chat.completions.create(
            messages=messages,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model="gpt-5",
            reasoning_effort="minimal",  # 応答にどれだけ「深く考えるか」を制御: ["minimal", "low", "medium", "high"]
            verbosity="low",  # 応答の長さを制御: ["low", "medium", "high"]
        )
        answer = response.choices[0].message.content
        return answer

    def get_openai_response_gpt5_mini(self, messages):
        response = self.client.chat.completions.create(
            messages=messages,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model="gpt-5-mini",
            reasoning_effort="minimal",  # 応答にどれだけ「深く考えるか」を制御: ["minimal", "low", "medium", "high"]
            verbosity="low",  # 応答の長さを制御: ["low", "medium", "high"]
        )
        answer = response.choices[0].message.content
        return answer

    def get_openai_response_gpt5_nano(self, messages):
        response = self.client.chat.completions.create(
            messages=messages,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model="gpt-5-nano",
            reasoning_effort="minimal",  # 応答にどれだけ「深く考えるか」を制御: ["minimal", "low", "medium", "high"]
            verbosity="low",  # 応答の長さを制御: ["low", "medium", "high"]
        )
        answer = response.choices[0].message.content
        return answer

    def get_openai_response_gpt5_chat(self, messages):
        response = self.client.chat.completions.create(
            model="gpt-5-chat",
            messages=messages,
            temperature=0.0,
        )
        answer = response.choices[0].message.content
        return answer


def test():
    """
    テスト用関数。クラスの各関数の接続テストを行う。
    """
    service = AzureOpenAIService()
    messages = [
        {"role": "user", "content": "こんにちは、今日の天気はどうですか？"},
    ]
    max_tokens = 1000
    try:
        answer, input_tokens, output_tokens = service.get_openai_response_o3_mini(
            messages, max_tokens
        )
        print("Response:", answer)
        print("Input Tokens:", input_tokens)
        print("Output Tokens:", output_tokens)
    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    test()
