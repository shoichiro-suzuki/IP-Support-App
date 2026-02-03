{
  "meta": {
    "audience": "developer",
    "mode": "manual",
    "system_name": "契約審査サポートアプリ",
    "purpose": "勉強会での技術共有",
    "generated_at": "2026-02-03",
    "source_scope": ["repo", "docs"],
    "confidence_overall": "medium"
  },
  "common": {
    "one_liner": {
      "purpose": "契約書をアップロードし、条文抽出とナレッジ照合を経てLLM審査結果を出力する",
      "who": "契約審査担当者",
      "outcome": "審査結果の可視化とCSV出力"
    },
    "out_of_scope": [
      "法的な最終判断や承認の自動化",
      "契約書本文の恒久保存"
    ],
    "glossary": [],
    "open_questions": [
      "リポジトリURL（社内共有用）はどこか",
      "本番運用の監視・運用フローはどこで管理しているか",
      "主要な非機能要件（SLA/性能/コスト制約）があるか"
    ]
  },
  "audience_specific": {
    "tech_summary": {
      "one_liner": "Streamlit UI + Azureサービス連携で、契約審査の条文抽出とLLM審査を実行するアプリ",
      "problem_solved": "契約書の条文抽出とナレッジ照合を自動化し、審査結果の整理を支援",
      "target_audience": "新人開発者（Python/Streamlit初学者レベル）"
    },
    "architecture": {
      "overview": "StreamlitのUI層（Home/pages）から、文書抽出（services）、API層（api）、Azure接続（azure_）を介して審査処理を行う構成。",
      "diagram_hint": "UI → 文書抽出 → ナレッジ照合/審査 → CSV出力、横にAzure OpenAI/Cosmos DB/Document Intelligenceを配置したコンポーネント図が適切。",
      "components": [
        {
          "name": "UI",
          "responsibility": "契約審査画面とナレッジ管理画面の提供",
          "technology": "Streamlit（Home.py / pages）",
          "why": "docsに明記なし"
        },
        {
          "name": "Document Input",
          "responsibility": "PDF/DOCXの抽出、条文境界監査",
          "technology": "services/document_input + Azure Document Intelligence",
          "why": "docsに明記なし"
        },
        {
          "name": "LLM & Matching",
          "responsibility": "条項とナレッジのマッチング、審査/要約",
          "technology": "api/async_llm_service + Azure OpenAI",
          "why": "docsに明記なし"
        },
        {
          "name": "Data Store",
          "responsibility": "ナレッジ/条文/契約データのCRUDと検索",
          "technology": "Azure Cosmos DB",
          "why": "docsに明記なし"
        }
      ],
      "data_flow": "入力: .docx/.pdf → 抽出: title/introduction/clauses → LLMで条項とナレッジをマッチング → 審査/要約 → 出力: 審査結果CSV。"
    },
    "tech_choices": [
      {
        "category": "UI",
        "choice": "Streamlit",
        "why": "docsに明記なし",
        "alternatives": [],
        "tradeoffs": "docsに明記なし"
      },
      {
        "category": "LLM",
        "choice": "Azure OpenAI",
        "why": "docsに明記なし",
        "alternatives": [],
        "tradeoffs": "docsに明記なし"
      },
      {
        "category": "OCR",
        "choice": "Azure Document Intelligence",
        "why": "docsに明記なし",
        "alternatives": [],
        "tradeoffs": "docsに明記なし"
      },
      {
        "category": "DB",
        "choice": "Azure Cosmos DB",
        "why": "docsに明記なし",
        "alternatives": [],
        "tradeoffs": "docsに明記なし"
      }
    ],
    "key_implementations": [
      {
        "topic": "プロンプトフローの状態管理",
        "description": "JSON schemaによるターン検証と修復リトライ、添付テキスト結合を定義。",
        "code_pointer": "docs/PROMPT_FLOW_STATE_SPEC.md",
        "highlight": "response_format=json_schema と最大2回の修復リトライ"
      },
      {
        "topic": "ナレッジ抽出インタビュアープロンプト",
        "description": "4フィールド固定のJSON出力を強制し、対話でナレッジを構造化する。",
        "code_pointer": "prompts/system_prompt_A.md",
        "highlight": "knowledge_json は null 必須、追加フィールド禁止"
      },
      {
        "topic": "条文境界監査（計画）",
        "description": "ルールベース候補をLLMで監査して境界を確定する方針。",
        "code_pointer": "docs/document_input.md",
        "highlight": "境界候補挿入 → LLM監査 → final_sections"
      }
    ],
    "challenges_and_solutions": [
      {
        "challenge": "条文分割の誤判定（引用句など）",
        "context": "『第X条に基づき』などで誤分割が頻発",
        "solution": "境界候補の挿入とLLM監査による補正（計画）",
        "lesson": "ルールとLLMを分担し、LLMを監査に限定する方針"
      },
      {
        "challenge": "LLM再結合の不安定さ",
        "context": "再結合すべき箇所の見落としが発生",
        "solution": "境界監査クラスの共通化で再監査を可能にする（計画）",
        "lesson": "再現性確保のため入出力スキーマを明確化する"
      }
    ],
    "learnings": [
      {
        "category": "設計",
        "learning": "LLMの役割を『監査』に限定すると説明可能性を担保しやすい",
        "recommendation": "境界判定など曖昧性の高い工程は、ルール+LLM監査で分担する"
      }
    ],
    "future_improvements": [
      {
        "area": "条文分割の精度向上",
        "current_state": "誤分割があり、計画中",
        "improvement": "境界監査クラスの導入と末尾分割の精緻化",
        "priority": "未定"
      }
    ],
    "resources": {
      "repo": "",
      "docs": [
        "README.md",
        "docs/overview.md",
        "docs/ui.md",
        "docs/api.md",
        "docs/document_input.md",
        "docs/PROMPT_FLOW_STATE_SPEC.md",
        "prompts/system_prompt_A.md"
      ],
      "related_reading": []
    },
    "qa_anticipated": [
      {
        "question": "条文抽出の失敗時はどうなる？",
        "answer": "UIでエラー表示し処理を停止する。"
      },
      {
        "question": "ナレッジ管理は誰が編集できる？",
        "answer": "管理者パスワードで編集権限を制御する。"
      },
      {
        "question": "LLMの出力形式はどう担保する？",
        "answer": "json_schema での強制と修復リトライを採用している。"
      }
    ]
  },
  "evidence_summary": [
    {
      "claim": "Streamlit製の契約審査アプリで、契約書アップロード→条文抽出→ナレッジ紐付け→LLM審査→CSV出力の流れを持つ",
      "ref": "README.md:3-16",
      "confidence": "explicit"
    },
    {
      "claim": "外部サービスとしてAzure OpenAI/Cosmos DB/Document Intelligenceを利用する",
      "ref": "docs/overview.md:1-7",
      "confidence": "explicit"
    },
    {
      "claim": "契約審査画面は document_input で抽出し、LLMでマッチングと審査/要約を行う",
      "ref": "docs/ui.md:4-12",
      "confidence": "explicit"
    },
    {
      "claim": "LLM呼び出しはjson_schemaでの制約と修復リトライを用いる",
      "ref": "docs/PROMPT_FLOW_STATE_SPEC.md:10-17",
      "confidence": "explicit"
    },
    {
      "claim": "条文境界の監査はルールベース候補＋LLM監査で補正する計画",
      "ref": "docs/document_input.md:17-28",
      "confidence": "explicit"
    },
    {
      "claim": "ナレッジ抽出プロンプトは4フィールド固定のJSON出力を強制する",
      "ref": "prompts/system_prompt_A.md:1-21",
      "confidence": "explicit"
    }
  ],
  "infographic_hints": {
    "recommended_layout": "コンポーネント図",
    "primary_message": "文書抽出とLLM審査を分離し、検証可能なプロンプトフローで品質を担保する",
    "visual_elements": [
      "UIからAPI/Servicesへの矢印",
      "Azure OpenAI/Cosmos DB/Document Intelligenceの外部依存",
      "条文境界監査のルール→LLM監査フロー"
    ],
    "color_scheme_hint": "UI層=青、LLM/AI層=オレンジ、データ層=緑"
  }
}
