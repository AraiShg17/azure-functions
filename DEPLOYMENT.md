# デプロイ手順（実行は明示的な許可後）

対象: `func-ashdevlab-incident-poc`

## 準備済み

- Python 3.12 / Programming Model V2 の HTTP 関数。
- `receive_incident`: POST、`/api/receive_incident`、Function 認証。
- 本番依存は検証済みの `azure-functions==1.25.0` に固定。
- `.funcignore` で仮想環境、ローカル設定、テスト、開発用依存、ドキュメントなどを除外。
- Function Key・実接続文字列は同梱しない。

## デプロイ前の確認

プロジェクトルートで実行します。

```bash
source .venv/bin/activate
python --version
python -m pip check
python -m pytest -q
func --version
az --version
```

ローカル HTTP 疎通は README の Azurite・`func start`・curl 手順で確認します。
単体テストは Azure ホスト上の認証や実 HTTP 動作を検証するものではありません。

Azure CLI のインストール完了後、ログインして対象を確認します。

```bash
az login
az account show --query '{subscription:name,id:id}' --output table
az functionapp list --query "[?name=='func-ashdevlab-incident-poc'].{name:name,resourceGroup:resourceGroup,state:state,host:defaultHostName}" --output table
```

意図したサブスクリプション内の既存アプリであることを確認してください。
アプリが見つからなくても、この手順ではリソースを新規作成しません。
Azure Portal で Runtime v4、Python 3.12、Linux、Flex 従量課金、
インスタンスメモリ 512MB、最大インスタンス数 1 を確認します。
これらは `host.json` では指定しません。設定の変更も別途許可後に実施します。

## 許可後のデプロイ

以下は既存アプリのコードを更新します。ここまでの確認結果を共有し、
ユーザーがデプロイを明示的に許可してから実行してください。

```bash
func azure functionapp publish func-ashdevlab-incident-poc
```

DB調査を実行する段階では、Function Appの環境変数へ`DB_HOST`、`DB_PORT`、
`DB_NAME`、`DB_USER`、`DB_PASSWORD`、`DB_TIMEOUT_SECONDS`、`DB_SSL`を追加します。
`DB_PASSWORD`はKey Vault参照を使用します。SQL計画だけを確認する間はDB設定不要です。

Python の依存はリモートビルドで Linux 用に構築します。
macOS の `.venv` やローカル設定をアップロードする必要はありません。
`--publish-local-settings` は付けません。

## デプロイ後の疎通

1. Portal で `receive_incident` が登録されていることを確認します。
2. 実際の既定ホスト名を使った HTTPS URL の `/api/receive_incident` に送信します。
3. Power Automate の HTTP アクションを POST、`Content-Type: application/json` とし、
   Function Key を `x-functions-key` ヘッダーに設定します。
4. README のサンプル JSON を送り、200、`success: true`、日本語の応答を確認します。
5. 不正入力で400になり、ログに description が含まれないことを確認します。

キーはソース・Git・この文書へ貼り付けず、Power Automate の該当アクションでは
セキュリティで保護された入力・出力を有効にします。

## 初回作業の結果（2026年9月21日）

- Azure CLI のインストールとユーザーによるログインが完了。
- 対象アプリの存在を確認し、環境設定はユーザーが確認。
- ローカル HTTP POST で200とUTF-8 JSON応答を確認。
- ユーザーが初回デプロイを実施し、Power Automateの固定Bodyによる実行成功を確認。
- 動的なコンテンツへ置き換え、SharePointのID・タイトル・障害詳細の取得成功が報告された。
- Azure上での異常系の網羅的な試験と実行履歴の保護設定は未確認。

詳細は [設定・作業記録](docs/incident-poc-setup-guide.md) を参照。
この記録は今後の再デプロイ・リソース変更を許可するものではありません。
