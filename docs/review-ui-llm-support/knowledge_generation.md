# ナレッジ選択/生成

## 機能
1. 審査経緯／結果から新たなナレッジを審査担当から抽出（創出）する `pages\22_knowledge_llm.py`
2. 抽出した新ナレッジのスキーマをデータベース状態に揃えてJSONファイルで出力
3. 新ナレッジJSONをアップロードしつつ新規作成する機能を `pages\22_knowledge_llm.py` に追加

### 機能１：新ナレッジ創出チャット（pages/22_knowledge_llm.py）
- Input：ユーザーテキスト、契約書ファイル（経過や結論）
- LLMプロンプトでナレッジ抽出し、`knowledge_title` などCosmosDBスキーマで返す
    - ナレッジ抽出観点をシステムプロンプトで指定、JSONのみ出力を要求
- 機能２に引き渡せるように清書し、JSONダウンロードを提供

### 機能２：ナレッジスキーマ生成
- CosmosDBのコンテナスキーマを用意
- 機能１のアウトプットをスキーマに合わせて再整形
- JSONファイルとしてダウンロード可能とする
    - 技術的にはCosmosDBに直更新できるが、ナレッジ更新の承認のためあえて外に出す
    - 更新するときは `pages\22_knowledge_llm.py` でインポートする機能を追加してJSONファイルをアップロードする：機能３
    - `knowledge_title`, `target_clause`, `review_points`, `action_plan`, `clause_sample`, `contract_type`

### 機能３：新ナレッジをJSONから追加
- JSONファイルをアップロード
- `id`, `knowledge_number` を自動付与
- ベクトルフィールドを追加してDB追加
