# ナレッジ選択/生成（LLMモック）
- 目的: 既存ナレッジを選択し、プロンプトを確認しながら下書きをモック生成。
- 想定モデル: Azure OpenAI chat（温度0.2目安）。実装はLLM未接続。

## ナレッジ選択タブ（正式UI）
- データ取得: `KnowledgeAPI.get_knowledge_list()`。失敗時は空リストで継続。
- 選択方法: ラジオで「テキスト検索」/「ベクトル検索（モック・フィルタ方式）」を切替。どちらもテキスト入力でキーワードフィルタ。
- 選択: `knowledge_number`をラベルにマルチセレクト。フィルタ変更時も既選択を維持。結果IDは`session_state["knowledge_llm_selected"]`に保持。
- プレビュー: 選択済みナレッジをエクスパンダで表示（対象条項/審査観点/対応策/条項サンプル）。

## ナレッジ生成タブ（LLMモック）
- レイアウト: メインはチャット欄、サイドバーに選択済みナレッジと生成結果（再生成ボタン含む）。
- チャット欄: `st.chat_input(accept_file=True)`でテキスト/添付を送信し、`st.chat_message`で履歴表示。入力内容と添付は生成ツールに渡すだけでLLMはモック応答。別アップローダ不要。
- サイドバー: 選択済みナレッジをexpander表示し、下記フィールドのみをJSON化してUserプロンプトに埋め込み。  
  `contract_type, target_clause, knowledge_title, review_points, action_plan, clause_sample`
- プロンプト表示: UI上は非表示（内部でSystem/Userテンプレを生成）。
- モック出力: サイドバーのボタンで下記フォーマットに沿ったJSONを生成表示。LLM呼び出しなし。

## システム/ユーザープロンプト
- System: あなたは契約ナレッジ編集者。入力コンテキストのみを根拠に既存フォーマットでドラフトを返す。推測/補完禁止。足りない項目は空文字。日本語で簡潔に。前置き/結論は不要。
- User:
```
以下コンテキストを踏まえ、ナレッジ下書きをJSONで返して。説明文やコードブロックは不要。
[アップロード資料]
{file_context_json}
[参考ナレッジ（任意）]
{knowledge_refs_json}
```

## 出力フォーマット（JSON 1オブジェクト）
- 必須: `knowledge_title`, `target_clause`, `review_points`, `action_plan`, `clause_sample`, `contract_type`
- 生成禁止/アプリ側付与: `id`, `knowledge_number`, `created_at`, `updated_at`
```
{
  "knowledge_title": "...",
  "target_clause": "...",
  "review_points": "...",
  "action_plan": "...",
  "clause_sample": "...",
  "contract_type": "..."
}
```
- 空項目はUIで追加入力を促す。改行はそのまま保存し、CSV/Excel出力時のみ整形。

## ナレッジ修正シナリオ
- 既存ナレッジ指定+修正方針: 対象を選択し指示を渡す→LLMで再生成→ユーザーが調整。
- 既存ナレッジ+参考コンテキスト: 契約抜粋や新知見を渡し差分抽出→修正案提示→微調整。
- 参考コンテキストのみ: 関連ナレッジ検索→候補提示→差分抽出→修正案提示→確定。
- 品質チェック依頼: 必須項目充足/重複・冗長削減をLLMに依頼し採否決定。

## スキーマ/機能整理
- 編集スキーマ: `knowledge_title`, `target_clause`, `review_points`, `action_plan`, `clause_sample`, `contract_type`
- 固定/生成禁止: `id`, `knowledge_number`, `created_at`, `updated_at`
- ベクトル検索用: `clause_sample_vector`, `risk_description_vector`, `action_plan_vector`（1536次元）
- 入力コンテキスト: 既存ナレッジ、参考コンテキスト（テキスト/Word/PDF/OCR）、ユーザー指示、関連ナレッジ候補（検索結果トップN）
- 出力/適用: 修正結果はJSON出力で持ち出し、承認後に `pages/20_knowledge.py` へインポートして反映。
