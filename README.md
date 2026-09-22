# func-ashdevlab-incident-poc

SharePoint「障害一覧」から Power Automate 経由で送信される障害情報を受信する Azure Functions（Python）アプリです。

初回構築から実データ連携までの手順と、発生した問題・解決方法は
[設定・作業記録](docs/incident-poc-setup-guide.md) にまとめています。

## 前提

- Python 3.12
- Azure Functions Runtime v4
- Python Programming Model V2
- Azure Functions Core Tools v4（ローカル起動・デプロイ用）
- デプロイ先: `func-ashdevlab-incident-poc`（Linux / Flex 従量課金）
- Azure 側の想定設定: メモリ 512MB、最大インスタンス数 1

メモリ・最大インスタンス数は Azure リソース側の設定です。このアプリや
`host.json` では変更しません。Azure リソースの作成・変更とデプロイは、
明示的な許可を得るまで実行しないでください。

## セットアップ

### 1. 仮想環境の作成

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 2. 依存パッケージのインストール

```bash
python -m pip install -r requirements-dev.txt
```

### 3. ローカル設定ファイルの作成

`local.settings.example.json` をコピーして `local.settings.json` を作成します。

```bash
cp local.settings.example.json local.settings.json
```

`local.settings.json` は Git 管理対象外です。API キーや接続文字列はこのファイルまたは Azure Portal / 環境変数で管理してください。

コピー先が既に存在する場合は上書きせず、必要な設定だけを反映してください。
`UseDevelopmentStorage=true` はローカルの Azurite を参照する設定で、実際の接続秘密情報ではありません。
本番の依存パッケージは `requirements.txt`、pytest は `requirements-dev.txt` に分離しています。

障害の一次分析にはOpenAI APIを使用します。`local.settings.json`の`Values`へ、
契約内で利用できるモデル名とAPIキーを設定してください。値はこのREADMEやGitへ記録しません。

```json
{
  "OPENAI_API_KEY": "実際のAPIキー",
  "OPENAI_MODEL": "利用可能なモデル名",
  "OPENAI_TIMEOUT_SECONDS": "30"
}
```

OpenAI Python SDKは環境変数の`OPENAI_API_KEY`を利用します。AIの応答には
Structured Outputsを使用し、アプリ側の型に一致するJSONだけを受け付けます。
[OpenAI公式Quickstart](https://developers.openai.com/api/docs/quickstart)

AzureではKey Vaultのシークレット名を`OPENAI-API-KEY`とし、Function Appの
環境変数`OPENAI_API_KEY`へ次のKey Vault参照を設定します。Key Vaultの名前と
環境変数名は別管理のため、Pythonコードは`OPENAI_API_KEY`のまま使用します。

```text
@Microsoft.KeyVault(SecretUri=https://kv-incident-poc-sarai.vault.azure.net/secrets/OPENAI-API-KEY)
```

## テスト

```bash
python -m pytest
```

詳細表示:

```bash
python -m pytest -v
```

## DB調査Function（想定実装）

`POST /api/investigate_database` は一次分析でDB調査が必要と判断された場合に使用します。
Power AutomateのTrue分岐から、次の形式で送信します。

```json
{
  "incident": {
    "id": "12",
    "title": "年齢が表示されない",
    "description": "特定ユーザーだけ年齢が空欄です"
  },
  "analysis": {
    "databaseQuestions": [
      "対象ユーザーの生年月日が登録されているか"
    ]
  },
  "execute": false
}
```

`execute: false`（既定）はシミュレーションモードです。RAG検索、SQL計画生成、安全性
検査を行い、実DBには接続せず、明示的なサンプル行を取得結果として使用します。
`execute: true`の場合だけ、設定済みの読み取り専用MySQLアカウントでSQLを実行します。
どちらのモードでも取得結果を元の障害情報、DB調査質問、関連DB仕様とともに再度AIへ渡し、
原因、根拠、問題特定の成否、リポジトリ調査要否、推奨対応を構造化JSONで返します。

```json
{
  "databaseInvestigation": {
    "summary": "対象顧客の生年月日が登録されていません",
    "likelyCause": "birth_dateがNULLのため年齢を算出できません",
    "evidence": ["customers.birth_dateがNULL"],
    "problemIdentified": true,
    "needsRepositoryInvestigation": false,
    "recommendedActions": ["生年月日の登録経路を確認する"],
    "confidence": 0.92
  }
}
```

`execute: false`のレスポンスは`mode: simulated`、`dataSource: sampleData`となり、各結果にも
`simulated: true`が付きます。考察のsummaryにも仮データによるシミュレーションであることを
明記させます。本番データの調査結果として扱わないでください。

サンプルRAGデータは`rag_data/database_schema.json`です。テーブル定義、列の意味、
業務ルール、検索キーワード、参照許可テーブルをチャンク単位で記録しています。
検索処理は`database_investigation/rag.py`に分離しているため、後からベクトル検索へ
差し替えられます。

DB実行時は次の環境変数を設定します。`DB_USER`にはSELECT権限だけを付与した専用
ユーザーを指定し、パスワードは本番環境ではKey Vault参照にします。

```text
DB_HOST
DB_PORT=3306
DB_NAME=incident_poc
DB_USER=incident_reader
DB_PASSWORD=<Key Vault参照>
DB_TIMEOUT_SECONDS=10
DB_MAX_ROWS=20
DB_SSL=true
```

AI生成SQLに対し、単一のSELECT、テーブル許可リスト、禁止キーワード、WHERE句、
名前付きパラメータ、`SELECT *`の禁止、最大20行のLIMITを検査します。SQL計画には
取得列と、その列だけが必要な理由も含まれます。DB実行時にも読み取り専用トランザクションを
開始します。最終的な防御として、DB側で`incident_reader`へSELECT以外の権限を付与
しないでください。

## Backlog起票Function

`POST /api/create_backlog_issue` は、元の課題、一次分析、DB調査レスポンスからBacklogの
件名と説明を生成します。説明には起票内容、AIが想定した状況、SQL、取得データ、疑われる
原因と根拠を含めます。DB調査がシミュレーションの場合は、仮データであることを明記します。

最初は必ず`dryRun: true`で呼び出してください。この場合はBacklogへ登録せず、完成した
`backlogIssue.summary`と`backlogIssue.description`だけを返します。内容を確認したあと
`dryRun: false`へ変更すると実際に課題を作成します。

```json
{
  "incident": {
    "id": "12",
    "title": "年齢が表示されない",
    "description": "特定ユーザーだけ年齢が空欄です"
  },
  "analysis": {
    "summary": "特定ユーザーの年齢だけ表示されない",
    "databaseQuestions": ["生年月日が登録されているか"],
    "repositoryQuestions": ["年齢算出処理を確認する"]
  },
  "databaseInvestigation": "investigate_databaseのbody全体を指定",
  "dryRun": true
}
```

Azure Function Appには次を設定します。APIキーはKey Vaultへ保存し、環境変数
`BACKLOG_API_KEY`から参照してください。

```text
BACKLOG_BASE_URL=https://<スペース名>.backlog.com
BACKLOG_API_KEY=<Key Vault参照>
BACKLOG_PROJECT_ID=<数値ID>
BACKLOG_ISSUE_TYPE_ID=<数値ID>
BACKLOG_PRIORITY_ID=<数値ID>
BACKLOG_TIMEOUT_SECONDS=15
```

Power AutomateではDB調査のTrue分岐にあるHTTPアクションの直後へ、もう一つHTTP
アクションを追加してこのFunctionを呼びます。Function Keyは従来どおり
`x-functions-key`ヘッダーへ設定します。

## ローカル起動

[Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) と
[Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) をインストールしてください。
設定例は Azurite を使うため、別ターミナルで先に起動します（Node.js / npm が必要）。

```bash
npm install -g azurite
azurite --location /tmp/incident-poc-azurite
```

仮想環境を有効にしたプロジェクトルートで次を実行します。

```bash
func start
```

起動後、関数は次の URL で待ち受けます。

- ルート: `http://localhost:7071/api/receive_incident`
- HTTP メソッド: POST
- 認証: Azure 上は Function Key が必要。通常のローカル起動では認証チェックが無効になり、キーは不要です。

## curl による POST テスト例

ローカル起動した関数へ送信します。

```bash
curl -i -X POST "http://localhost:7071/api/receive_incident" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "1",
    "title": "ログイン画面でエラーが発生する",
    "description": "ログインボタンを押すと500エラーになります",
    "category": "障害",
    "createdAt": "2026-09-21T15:00:00+09:00"
  }'
```

正常時のレスポンス例:

```json
{
  "success": true,
  "message": "障害情報を受信しました",
  "incident": {
    "id": "1",
    "title": "ログイン画面でエラーが発生する",
    "category": "障害"
  },
  "analysis": {
    "summary": "ログイン操作で500エラーが発生している",
    "needsDatabaseInvestigation": true,
    "databaseQuestions": [
      "対象ユーザーの状態が有効か"
    ],
    "needsRepositoryInvestigation": true,
    "repositoryQuestions": [
      "ログイン処理の直近変更を確認する"
    ],
    "confidence": 0.4
  }
}
```

## デプロイ

実行前の確認と許可後の手順は [DEPLOYMENT.md](DEPLOYMENT.md) を参照してください。

以下は許可後に実施する手順です。Azure CLI にログインし、対象サブスクリプションと
既存 Function App の Python 3.12 / Runtime v4 / Linux / Flex / 512MB / 最大インスタンス数 1
の設定を確認してからデプロイします。このコマンドを今回の作業で実行することはありません。

```bash
func azure functionapp publish func-ashdevlab-incident-poc
```

## Function Key の取り扱い

- Function Key をソースコードや Git リポジトリへ保存しないでください
- ローカルの秘密情報は `local.settings.json` を使用します（`.gitignore` および `.funcignore` 対象）
- Function Key は Azure Portal の対象関数の「関数キー」で管理してください（通常の Application Settings とは別です）
- Power Automate から呼び出す際は、URL クエリ `?code=` または `x-functions-key` ヘッダーでキーを渡します
- Power Automate の HTTP アクションには、デプロイ後に確認した HTTPS URL の `/api/receive_incident`、POST、`Content-Type: application/json` と JSON 本文を指定します。キーを含むアクションはセキュリティで保護された入力・出力を有効にしてください。

## 入出力と拡張

`id`・`title`・`description` は空白だけではない文字列が必須です。JSON の解析失敗、
オブジェクト以外、必須項目の不足・空文字・型違い、不正または未指定の Content-Type は 400 を返します。
`application/json; charset=utf-8` も受理します。`category` と `createdAt` は任意で、
`category` 省略時はレスポンスの値が `null` になります。
全レスポンスは UTF-8 の JSON で、想定外の例外は詳細を含まない 500 を返します。

受信、検証済みの ID・タイトル、正常終了または異常終了を記録します。
検証に失敗した入力の値、リクエスト全体、description、例外の詳細やスタックトレースはログへ出しません。
OpenAI APIによる一次分析を実装済みです。DB・GitHub・Backlog連携は未実装です。
APIの設定不足は500、AIサービスの呼び出し失敗や構造化結果を取得できない場合は502を返します。

## プロジェクト構成

```text
function_app.py              # Azure Functions エントリポイント
incident/
  handler.py                 # HTTP ハンドラー
  parser.py                  # リクエスト解析・バリデーション
  response.py                # レスポンス生成
  analyzer.py                # OpenAI APIによる一次分析
  models.py                  # 構造化された分析結果の型
  prompts.py                 # 一次分析プロンプト
host.json
requirements.txt
requirements-dev.txt         # テスト用依存
.funcignore                  # デプロイ除外
local.settings.example.json
tests/
  test_receive_incident.py
```

将来 OpenAI 連携などを追加する場合は、`incident/` 配下に処理モジュールを追加し、`handler.py` から呼び出す構成を想定しています。
