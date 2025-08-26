# pip install python-dotenv
# pip install azure-ai-documentintelligence==1.0.2

import os
import json
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv


import streamlit as st


@st.cache_resource
def get_document_intelligence_ocr():
    load_dotenv()
    endpoint = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("DOCUMENT_INTELLIGENCE_API_KEY")
    client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))

    class _DocumentIntelligenceOCR:
        def __init__(self, client):
            self.client = client

        def analyze_document(self, file_path):
            with open(file_path, "rb") as f:
                poller = self.client.begin_analyze_document(
                    "prebuilt-layout",
                    body=f,
                    output_content_format="markdown",
                )
                result = poller.result()
            return result

    return _DocumentIntelligenceOCR(client)
