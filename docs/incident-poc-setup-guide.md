# SharePoint → Power Automate → Azure Functions 疎通確認の設定・作業記録

作業日：2026年9月21日。会話、実行結果、共有された画面、実装ファイルをもとに記録。

## 1. 到達点

SharePoint「障害一覧」への新規登録をきっかけに、Power AutomateのHTTPアクションからPython製Azure FunctionへJSONを送信する構成を作成した。

```text
SharePoint「障害一覧」
  └ 項目を新規作成
      ↓
Power Automate「項目が作成されたとき」
      ↓ ID・タイトル・障害詳細をJSONにする
HTTP（POST、Function Keyで認証）
      ↓
Azure Functions /api/receive_incident
  └ 入力を検証 → UTF-8のJSONで応答
```

確認できたこと：

- Python 3.12で単体テスト44件成功。依存関係チェックも成功。
- ローカルHTTP POSTで200、`success: true`、日本語の応答を確認。
- ユーザーがAzureへデプロイし、Portalに関数が表示された。
- Power Automateの固定Bodyによる実行で、SharePointトリガー・HTTPとも緑の成功表示を確認。
- 固定値を動的なコンテンツへ置き換え、ユーザーから実データ取得成功の報告があった。最後の画面のBodyには以下が表示された。

| フィールド | 確認した値 |
|---|---|
| id | 8 |
| title | サイトが404 |
| description | 本番サイトにアクセスしたら404表示でした |

この最後の画面は送信Bodyの内容を示す。今回のFunctionの応答にはdescriptionを含めないため、レスポンス本文とは区別する。表形式の「8」だけではJSONの文字列・数値は判別できないが、実装ではidは文字列を要求する。

2026年9月22日にOpenAI APIによる一次分析をローカルコードへ追加した。
Structured Outputsを使い、要約、DB調査要否と質問、リポジトリ調査要否と質問、
確信度を型付きJSONとして返す。単体テストは51件成功。APIキーを使った実通信、
Azureへの再デプロイ、Power Automateでの新レスポンス確認はまだ行っていない。
DB、GitHub、Backlogとの連携、保存・SQL実行・チケット作成は未実装。

## 2. 環境と構成

| 項目 | 設定・確認結果 |
|---|---|
| ローカル | macOS 13、zsh、Homebrew |
| 作業フォルダ | `/Users/arais/Desktop/data/practice/azure-functions-sample` |
| アプリPython | 3.12（テスト環境3.12.4） |
| Azure Functions | Runtime v4 / Python Programming Model V2 |
| Core Tools | 4.14.0 |
| Azure CLI | 2.90.0 |
| Function App | `func-ashdevlab-incident-poc` |
| リソースグループ | `rg-incident-ai-poc` |
| Azure環境 | Linux / Flex従量課金 / Japan East |
| メモリ・最大インスタンス | 512MB / 1（ユーザー確認） |
| 関数 | `receive_incident` |
| ルート・メソッド | `/api/receive_incident` / POSTのみ |
| 認証 | Function |
| SharePointサイト | `https://ashdevlab.sharepoint.com/sites/portal` |
| リスト | 障害一覧（確認したURLのパスは `/Lists/kaizen/AllItems.aspx`） |

Azure CLI自身が使うPython 3.14と、アプリのPython 3.12は別。CLIのPython表示でアプリの実行バージョンが変わるわけではない。

## 3. アプリ実装

```text
function_app.py                 HTTP関数の登録
incident/
  __init__.py
  handler.py                    処理の流れ、ログ、例外処理
  parser.py                     Content-Type、JSON、必須項目の検証
  response.py                   UTF-8 JSONレスポンスの生成
host.json                       Functionsホスト設定
requirements.txt                本番依存 azure-functions==1.25.0
requirements-dev.txt            本番依存とpytest
local.settings.example.json     秘密情報を含まないローカル設定例
.gitignore                      ローカル設定・仮想環境などをGitから除外
.funcignore                     開発用ファイルなどをデプロイから除外
README.md                       基本操作
DEPLOYMENT.md                   デプロイ前後の確認
tests/test_receive_incident.py   単体テスト
```

必須の`id`、`title`、`description`は空白だけではない文字列。以下は400を返す。

- JSONとして解析できない、またはJSONオブジェクトではない。
- 必須項目がない、空文字・空白だけ、文字列以外。
- Content-Typeが未指定またはapplication/jsonではない。

`application/json; charset=utf-8`も受理する。categoryとcreatedAtは任意。category省略時は応答のcategoryがnullになる。createdAtは現時点では処理・応答に使用しない。

正常応答例：

```json
{
  "success": true,
  "message": "障害情報を受信しました",
  "incident": {
    "id": "8",
    "title": "サイトが404",
    "category": null
  }
}
```

全応答のContent-Typeは`application/json; charset=utf-8`。想定外の例外は500と固定メッセージを返し、内部詳細を応答に含めない。

ログには受信、検証済みID・タイトル、正常／異常終了を記録する。description、リクエスト全体、例外メッセージやスタックトレースは出さない。例外メッセージにも本文が混入し得るため、途中の実装の`logger.exception`を固定のエラーログに修正した。

将来の処理は`incident/`に小さなモジュールを追加し、handlerから呼び出せる。

## 4. 開発ツールの準備

```bash
brew tap azure/functions
brew install azure-functions-core-tools@4
brew install azure-cli
```

インストール後：

```bash
func --version
az --version
```

今回Azure CLIは依存ライブラリをソースからビルドし、時間がかかった。Homebrewにバージョンが表示されても、インストール中はまだazコマンドが存在しない場合があった。最終的にaz --versionの成功とインストールプロセスの終了を確認した。

仮想環境と依存：

```bash
cd /Users/arais/Desktop/data/practice/azure-functions-sample
# .venvがない初回のみ
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pip check
```

再開時には既存ファイルと仮想環境を使用した。最初の確認時、このフォルダはGitリポジトリではなかった。.gitignoreの作成はGit初期化やリモートへの保存を意味しない。

## 5. ローカル起動と疎通

### ターミナルA：Azurite

Node.js/npmが利用可能な状態で実行。

```bash
npm install -g azurite
azurite --location /tmp/incident-poc-azurite
```

Blob 10000、Queue 10001、Table 10002がlisteningになれば起動成功。このターミナルは開いたままにする。Pythonの.venvが有効でもnpmのインストールは問題ない。

### ターミナルB：Function

```bash
cd /Users/arais/Desktop/data/practice/azure-functions-sample
source .venv/bin/activate
cp -n local.settings.example.json local.settings.json
func start
```

`cp -n`は既存の設定を上書きしない。設定例の`UseDevelopmentStorage=true`はローカルAzuriteを参照する。

Core ToolsとRuntimeのバージョン表示だけでは起動完了ではない。関数URLの表示と待ち受けを確認する。

```text
receive_incident: [POST] http://localhost:7071/api/receive_incident
```

通常のローカル起動ではFunction Keyは不要。Azure上では必要。

### ターミナルC：POST

```bash
curl -i http://localhost:7071/api/receive_incident \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "id": "1",
    "title": "ログイン画面でエラーが発生する",
    "description": "ログインボタンを押すと500エラーになります",
    "category": "障害",
    "createdAt": "2026-09-21T15:00:00+09:00"
  }'
```

HTTP 200とsuccess:trueを確認。コードブロック内をコピーし、Markdownリンクの角括弧などはコマンドに含めない。改行継続のバックスラッシュは行末に置く。応答末尾の`%`はzshの表示で、APIエラーではなかった。

## 6. Azureログインとデプロイ

```bash
az login
```

ブラウザのログイン成功後、ターミナルにサブスクリプション選択が出た。デフォルトでよければ何も入力せずEnter。通常の`%`プロンプトへ戻ってから次のコマンドを入力する。

```bash
az account show --query '{subscription:name,id:id}' -o table
az functionapp list --query "[?name=='func-ashdevlab-incident-poc'].{name:name,resourceGroup:resourceGroup,state:state}" -o table
```

対象アプリが`rg-incident-ai-poc`内でRunningと表示された。Runtime・Python・Linux・Flex・512MB・最大1はPortalで別途確認した。Runningだけで全設定が確認できるわけではない。

今回ユーザーが実行したデプロイコマンド：

```bash
func azure functionapp publish func-ashdevlab-incident-poc
```

以後の再デプロイも既存アプリのコードを更新する操作として扱う。エージェントが再実行する場合は明示的な許可後。秘密情報入りのlocal.settings.jsonやmacOSの.venvはアップロードしない。

## 7. Power Automate：固定値での疎通

### SharePointトリガー

自動化したクラウドフローを作成し、SharePoint「項目が作成されたとき」を選択。

- サイトのアドレス：ポータル（/sites/portal）
- リスト名：障害一覧

### HTTPアクションを追加

トリガーの下の＋ → アクションの追加 → HTTPを検索。

「HTTP」グループの緑のアイコンで、名前が単に「HTTP」のアクションを選んだ。HTTP Webhook、HTTP + Swagger、SharePoint専用HTTP、HTTP With Microsoft Entra IDとは別。

| 欄 | 値 |
|---|---|
| URI | 実際の関数URLの`?code=`より前 |
| Method | POST |
| Headers 1行目 | Content-Type / application/json |
| Headers 2行目 | x-functions-key / Function Keyの値 |
| Queries | 空欄 |
| Cookie | 空欄 |
| Body | 下記のJSON |

BodyはHTTPカードをクリック → パラメーター内の、Queriesの下・Cookieの上にある。

```json
{
  "id": "1",
  "title": "Power Automateからのテスト",
  "description": "疎通確認用の障害情報です",
  "category": "障害"
}
```

### Function Keyの取得

Azure Portal → Function Appの概要 → 関数一覧のreceive_incident → 関数のURLの取得。

```text
https://実際のホスト名/api/receive_incident?code=キーの値
```

URIは`?code=`より前。x-functions-keyには`?code=`を含めず値だけを入れる。末尾の`=`なども省略せず、空白・改行を入れない。キーはこの資料に保存しない。

補足：URLのキーに`%2B`などのURLエンコードが見える場合、ヘッダーへは関数キー画面で取得した元のキー値を使う。URL用の表現をそのままヘッダーへ移すことと、元のキーを渡すことは同じではない。

### テスト

保存 → テスト → 手動 → テストを開始。その後、SharePointに新しい項目を作成・保存する。既存項目の編集ではこのトリガーは起動しない。

実行履歴でSharePointとHTTPの成功を確認。HTTPの出力で200とsuccess:trueを確認する。今回、初回はUnauthorized、キー設定を見直した後は両アクションが緑になった。

## 8. 固定BodyからSharePoint実データへ置き換え

### 列の追加

SharePoint一覧の「＋列の追加」から以下を作った。

- 列名：障害詳細
- 型：複数行テキスト

新しいアイテムの「書式設定」はフォームの表示を変更する画面。列追加は一覧の列見出しから行う。

### Bodyの編集

Power Automate → フロー編集 → HTTP → Bodyに以下の枠を入れる。

```json
{
  "id": "",
  "title": "",
  "description": ""
}
```

各引用符の間へ「動的なコンテンツ」からトークンを挿入する。

| JSON | SharePointトリガーの動的なコンテンツ |
|---|---|
| id | ID |
| title | タイトル |
| description | 障害詳細 |

IDも引用符で囲み、文字列として送る。表示名を文字として手入力するのではなく、動的なコンテンツを挿入する。新しい列が候補に出ない場合は保存して編集画面を再読み込みする。

保存後、タイトル・障害詳細を入力した新規項目で試験し、ID 8・「サイトが404」・「本番サイトにアクセスしたら404表示でした」がBodyに入ったことを確認した。categoryとcreatedAtは今回の実データBodyでは省略した。

## 9. 詰まった点と解決方法の一覧

| 詰まった点 | 確認・原因 | 解決／今後の見方 |
|---|---|---|
| 作業が途中で止まったように見えた | アプリのファイルは既に存在し、実際の懸念はHomebrewのインストールだった | 既存実装を維持して補修。ツールの稼働を別途確認 |
| brew install azure-cliが長い | macOS 13で依存をソースビルド中。rustcが稼働 | プロセス・CPU時間・ログ更新を比較 |
| 本当に進んでいるか不明 | 約28秒でログ427,704→435,514バイト、CPU時間22.51→42.49秒。後にcryptographyへ進行 | 出力が静かなだけでは停止と判断しない |
| 再インストールでロックエラー | 元のbrew installがまだ稼働していた | 二重起動しない。こちらの再インストール判断は早計だった |
| スリープで止まった疑い | スリープ中の停止はあり得るが、その発生自体は未確認 | `caffeinate -i -w <実際のbrewのPID>`で自動アイドルスリープを抑止。蓋は開けておく |
| caffeinateが無表示 | 待機中の正常な動作 | 対象プロセスの終了まで待つ。今回の70902は当時のPIDで再利用しない |
| インストール残り時間 | 正確には測れず、10〜30分は当時の概算 | 推定時間を保証にしない。az --versionで完了確認 |
| .venv内でnpmを実行した | Python仮想環境とnpmのグローバルインストールは別 | そのまま実行可能 |
| Azuriteが待ち続ける | Blob/Queue/Tableのサービスとして稼働中 | 閉じずに別ターミナルでfunc start |
| func startがバージョン表示だけ | その時点では待ち受け前だった | 関数URLとポートの待ち受けを待つ。初回起動が遅かった具体的原因は未確定 |
| curl接続拒否 | その時点で7071へ接続できなかった | 起動後に再実行し200確認 |
| curlのURLや改行が分かりにくい | 会話表示にはMarkdownリンクの表現も混在 | コードブロックをコピー。URL・オプション・行末バックスラッシュを確認 |
| JSON末尾の% | ターミナルの表示 | エラーではない |
| Azureブラウザログイン後のInvalid selection | サブスクリプション選択待ちへazコマンドを入力していた | Enterまたは選択番号で確定後、通常プロンプトでコマンド入力 |
| Azure CLIのSyntaxWarning | CLI内部ライブラリの警告。アプリ一覧取得は成功 | 今回は処理結果を確認して継続 |
| HTTP候補が多い | 複数製品のHTTPアクションが検索された | HTTPグループ内の単独のHTTPを選択 |
| URLとキーの境界が不明 | 関数アプリ概要にはキー付きURLがまだ出ていなかった | receive_incidentを開き関数のURLを取得。URIとキーを分離 |
| Bodyがどこか分からない | ライセンスパネルや別画面を開いていた | HTTP → パラメーター → Queriesの下・Cookieの上 |
| Premiumライセンス警告 | HTTPがPremium機能 | 90日試用をユーザーが有効化。事前説明が不足していた |
| 解約・自動更新設定が見つからない | Microsoft 365契約、Power Automateライセンス、利用レポートが混同された | 次節の確認済み事実と未確認事項を区別 |
| 「ライセンス表示」が見つからない | すべての設定の中ではなく、右の設定パネルに直リンクがあった | 中央ダイアログを閉じ「自分のライセンスを表示」 |
| 管理センターでPower Appsが出る | 選択している製品が異なった | 左でPower Automateを選ぶ。ただし利用レポートは契約更新画面ではない |
| ライセンス画面でデータなし | 利用状況レポートの表示だった | 解約済み・課金なしの証拠にはしない |
| 手動テストがずっとローディング | 画面上はトリガー待ちだったが、後に実行履歴で起動とHTTP失敗が判明 | 待機画面だけで原因を断定せず実行履歴を見る |
| 項目を作ったのに動かないように見える | 登録先のサイト・リストを照合。項目作成は確認できた | トリガー設定と履歴で切り分け |
| 実行履歴の代わりに分析画面を開いた | Actions/Usage/Errorsの集計画面だった | フロー詳細の実行履歴から個別実行を開く |
| HTTPがUnauthorized | SharePointは成功し、HTTP認証段階で失敗 | キーの設定を見直して成功。欠落や誤入力のどの形だったかまでは未特定 |
| 列追加のつもりで書式設定を開いた | 新規アイテムの表示カスタマイズ画面だった | キャンセルし一覧の＋列の追加へ |
| 固定テストと実データの違い | 固定BodyではSharePoint項目内容が自動では送られない | 動的なコンテンツで3項目を対応させ、実データを確認 |

## 10. 試用・料金の確認記録

### 画面で確認した事実

- Microsoft 365 Business Standard：2026年10月20日に試用期限が切れるとキャンセルされる旨の表示を確認。
- Power Automate：「Power Automate Plan 2 Trial」、有効期限2026年12月20日を確認。
- プレミアムコネクタが利用可能な表示を確認。
- ユーザー報告：Microsoft 365の製品一覧にPower Automateは出なかった。カードは最初の登録時に入力し、Power Automate試用時には追加入力していない。追加メールも来ていない。

### この作業では断定できなかったこと

Power Automateの継続請求設定そのものは確認できていない。期限付き試用の表示と、継続請求オフの確認は別。Microsoft 365側のキャンセル設定だけでPower AutomateやAzureの料金まで止まるとは扱わない。

Microsoft公式ではPower Automateの90日試用は期限切れになると説明されている。一方、試用の登録経路・契約条件によって支払い条件が異なり得るため、この記録だけで個別契約の課金を保証しない。

ユーザーは十分に設定を探したうえで、追加探索を止めて検証を続ける判断をした。この資料でも追加の契約操作を実施済みとは記載しない。

### 金額の整理

Azureの少量実行費用とPower Automateのライセンス料金は別。確認時の日本向け公式表示はPower Automate Premiumが1ユーザー月額相当2,248円、年払い・税別。これは試用に今請求が発生したという意味ではない。また「月額相当」は実際の請求単位が月払いであることを意味せず、年払いなら請求額が1万円を超える場合がある。契約・税・他サービス込みの請求を1万円以下と保証するものではない。

Functions Flexにはオンデマンドの無料枠があるが、ストレージ・ログ・Always Ready等の条件次第で別料金が生じる。512MB・最大1インスタンスは支出上限の設定ではない。「月100円未満」は確認できていない。

## 11. 秘密情報とログの扱い

- Function Key、接続文字列、APIキーはソース・Git・資料に保存しない。
- local.settings.jsonはGit・デプロイ対象外。
- スクリーンショット共有時はキーを隠す。
- Functionのdescription非出力と、Power Automateの実行履歴に入力が残ることは別。今回の画像でもBodyにdescriptionが表示された。
- HTTPアクションの設定にある「セキュリティで保護された入力・出力」の有効化は案内したが、実際に有効にした証跡は未確認。実データ運用前に適用する。SharePointトリガー側の実行履歴にも本文が残り得るため、必要に応じてそちらの出力保護も確認する。

## 12. 案内の訂正と再現時の注意

- ローカル起動にキーが必要という初期READMEの説明は誤りで、修正済み。
- Azure CLIの実体がないだけで「壊れた」と判断したのは早計。既存ビルドの確認を先に行うべきだった。
- Power Automate Premiumの必要性をHTTP追加前に説明できていなかった。
- ライセンスの導線を誤案内し、利用レポートまで遠回りさせた。「自分のライセンスを表示」で確認できたのはライセンス名と期限。
- 「請求後に解約すれば大丈夫」「少額で済む」とは保証できない。発生済み料金や年払いの扱いを含め契約条件による。
- トリガー待ちの表示だけでフロー未実行と断定しない。最終的には実行履歴が判断材料になった。

## 13. 次の拡張候補（未実施）

- category・createdAtもSharePointの動的な値に対応させる。
- descriptionが空の登録を防ぐため、SharePointの障害詳細列を必須にするか検討する。
- Azure上の不正入力400、キーなし401、実運用ログの非出力を追加確認する。
- 業務処理を追加する際は、HTTPの再試行・再送を考慮した重複処理防止を設計する。
- OpenAI等の外部連携は別モジュールとして追加する。

## 14. 参照先

- [プロジェクトREADME](../README.md)
- [デプロイ手順](../DEPLOYMENT.md)
- [Azure Functions Python開発ガイド](https://learn.microsoft.com/azure/azure-functions/functions-reference-python)
- [Core Toolsとローカル開発](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
- [HTTPトリガーとキー認証](https://learn.microsoft.com/azure/azure-functions/functions-bindings-http-webhook-trigger)
- [Power Automateライセンス購入・試用](https://learn.microsoft.com/power-platform/admin/power-automate-licensing/buy-licenses)
- [Microsoftの試用・サブスクリプションのキャンセル](https://learn.microsoft.com/microsoft-365/commerce/subscriptions/cancel-your-subscription?view=o365-worldwide)
- [セルフサービス購入・試用の管理](https://learn.microsoft.com/microsoft-365/commerce/subscriptions/manage-self-service-purchases-admins?view=o365-worldwide)
- [Power Automate料金](https://www.microsoft.com/ja-jp/power-platform/products/power-automate/pricing)
- [Azure Functions料金](https://azure.microsoft.com/ja-jp/pricing/details/functions/)

料金・画面表示は作業時点の記録。再現時は現行の表示と契約条件を確認する。
