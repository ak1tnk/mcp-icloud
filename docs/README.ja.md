<p align="center"><a href="../README.md">English</a> · <b>日本語</b> · <a href="README.zh-CN.md">简体中文</a></p>

<h1 align="center">mcp-icloud</h1>

<p align="center">
  <strong>AI エージェントに iCloud の「メールを非公開」と iCloud メールを扱わせる</strong>
</p>

<p align="center">
  <a href="../LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11+-green.svg?logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://github.com/ak1tnk/mcp-icloud/actions/workflows/ci.yml"><img src="https://github.com/ak1tnk/mcp-icloud/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

小さなローカル [MCP](https://modelcontextprotocol.io) サーバー（stdio）です。Linux と macOS でヘッドレスに
動き、Claude Code、Orca、Linux VM 上の自律エージェントなど、あらゆる MCP クライアントで使えます。

> 非公式です。Apple とは関係ありません。「メールを非公開」と既定のメールバックエンドは icloud.com と同じ
> 非公開の Web API を使うため、Apple の変更でいつでも動かなくなる可能性があります。

---

## なぜ作ったか

Apple には iCloud 用の公式 MCP サーバーも公開 API もないため、エージェントは iCloud に触れません。

- **メールを非公開**（iCloud+）は Apple のアプリと icloud.com にしかなく、これを管理できる MCP サーバーは
  見当たりません。エージェントがサービスの会員登録を代行しても、そのための転送用アドレスを作る・ラベルを付ける・
  あとで無効化する、ができません。
- **iCloud メール**にはエージェント向けの入口がありません。IMAP には別途 App 用パスワードが必要で、
  完全削除をしない・送信を制限するといった配慮も自分で組む必要があります。

mcp-icloud は、`mcp-icloud login` 1 回のログインでこの両方を MCP ツールとして提供します。Apple ID のパスワードは
エージェントに渡らず、何も完全削除しません。より安定した IMAP/SMTP のメールバックエンドも選べます。

## できること

| サービス | ツール | 必要なもの |
| --- | --- | --- |
| メールを非公開 | `hme_list`, `hme_generate`, `hme_reserve`, `hme_update`, `hme_deactivate`, `hme_reactivate` | iCloud+ と、`mcp-icloud login` のセッション（Apple ID・パスワード・2FA コードをあなたがターミナルで入力） |
| メール | `mail_list_mailboxes`, `mail_search`, `mail_read`, `mail_download_attachment`, `mail_set_flags`, `mail_move`, `mail_archive`, `mail_trash`, `mail_send`, `mail_reply`, `mail_forward`, `mail_save_draft` | 追加は不要：同じ `mcp-icloud login` のセッション（Web バックエンド、試験的）。任意：IMAP/SMTP バックエンド用の App 用パスワード |

- `hme_generate` は候補を出すだけで、保存は `hme_reserve`。削除ツールはありません。`hme_deactivate` で転送を止め、
  `hme_reactivate` で戻せます。
- `mail_trash` はゴミ箱への移動です。完全削除は一切しません。
- `mail_send`、`mail_reply`、`mail_forward` は即時に送信します（下の「送信ポリシー」を参照）。

## クイックスタート：エージェントにこれを送る

```
Set up mcp-icloud for me by following https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md
```

エージェントがインストール、MCP サーバーの登録、動作確認まで行います。あなたが自分でやることは 1 つだけで、
チャットではなくターミナルで行います。

- `mcp-icloud login` を実行し、Apple ID・パスワード・2FA コードを入力します。このログイン 1 回で
  「メールを非公開」とメールの両方が使えます。VM の場合は SSH して実行するか、セッションをコピーします
  （下の「Linux VM と自律エージェント」を参照）。
- 任意：より安定した IMAP/SMTP のメールバックエンドを使う場合は、<https://account.apple.com> で App 用パスワードを
  作り、`mcp-icloud mail-login` を実行します（環境変数やプラットフォームのシークレットストアでも可）。

パスワード、2FA コード、App 用パスワードをエージェントのチャットに貼らないでください。まともなエージェントなら
求めてきません。

ほかのコピペ用プロンプト（VM でのセットアップ、日常のタスク、システムプロンプト用の一節）：
[prompts.md](prompts.md)

## あなたの言葉 → エージェントの動き

| あなたが言う | エージェントがやること |
| --- | --- |
| 「example-shop.com 用に新しい非公開メールを作って」 | `hme_generate` → ラベル「example-shop.com」で `hme_reserve`、アドレスを伝える |
| 「example-shop で使ったアドレスはどれ？」 | `hme_list` でラベルやメモから探す |
| 「example-shop で使ったアドレスを無効にして」 | `hme_list` で探して `hme_deactivate` |
| 「billing@example.com からの未読を見せて」 | `sender` と `unread_only` を指定して `mail_search` |
| 「最新のを読んで、金曜に払うと返信して」 | `mail_read` → `mail_reply`（即時送信） |
| 「返信の下書きだけ作って、送らないで」 | `mail_save_draft` |
| 「newsletter@example.com からのメールを全部アーカイブして」 | `mail_search` → `mail_archive` |
| 「mcp-icloud の状態を確認して」 | `mcp-icloud status` を実行：セッションは有効か、どのメールバックエンドか |
| 「mcp-icloud をアンインストールして」 | 削除するものを一覧して確認を取り、下の「アンインストール」に従う |

## 手動セットアップ

必要なもの：Python 3.11〜3.13 と [uv](https://docs.astral.sh/uv/)。

```sh
uv tool install git+https://github.com/ak1tnk/mcp-icloud
mcp-icloud --help
```

### 1 回ログインする

```sh
mcp-icloud login        # Apple ID、パスワード（非表示）、2FA コード
mcp-icloud status       # セッションは有効か、どのメールバックエンドを使うか
mcp-icloud logout       # Apple 側でセッションをサインアウトし、ローカルのファイルを削除
```

パスワードは 1 回使うだけで保存しません。2FA にハードウェアのセキュリティキーが必須のアカウントにはまだ対応して
いません。保存されるのは Apple が返すセッションで、セッションディレクトリ（`0700`、ファイルは `0600`）に
`account.json`（Apple ID のみ）、`<apple-id>.session`、`<apple-id>.cookiejar` が置かれます。

### メール：2 つのバックエンド

12 個の `mail_*` ツールは、どちらのバックエンドでも名前と引数が同じです。

| | Web バックエンド（既定） | IMAP/SMTP バックエンド（任意） |
| --- | --- | --- |
| 必要なもの | `mcp-icloud login` のセッションのみ | App 用パスワード |
| 位置づけ | **試験的**：icloud.com の非公開 Web API に対する pyicloud のメール機能を使用 | 標準プロトコルで安定。パスワードはセッションと違って期限切れにならない |
| 使われる条件 | App 用パスワードが未設定のとき | App 用パスワードが設定済みのとき |

`MCP_ICLOUD_MAIL_BACKEND=web` または `imap` で固定できます（既定は `auto`）。どちらが有効かは
`mcp-icloud status` に表示されます。

Web バックエンドの制限（結果を黙って変えず、制限を明示したエラーを返します）：

- `mail_search`：テキスト条件（`sender`、`recipient`、`subject`、`text`）は 1 検索に 1 つ。`unread_only` と
  `flagged_only` は互いにも、テキスト条件とも併用できません。日付での絞り込みは最大 1000 通を走査します。
  `seen`/`flagged` は絞り込み条件から分かる場合以外 `null`、`total_matches` は概数です。
- `mail_move`：iCloud は迷惑メール・下書きなど一部の特殊フォルダへの移動を拒否します。
- 送信は下書きを作ってから送信します。Apple の応答が不明確な場合はツールがそう伝えるので、再試行の前に
  送信済みと下書きを確認してください。

IMAP バックエンドの設定：

1. <https://account.apple.com> にサインインし、**サインインとセキュリティ → App 用パスワード** で作成します
   （`xxxx-xxxx-xxxx-xxxx` の形式）。
2. `mcp-icloud mail-login` を実行します。iCloud メールのアドレスと App 用パスワード（非表示）を聞き、IMAP と
   SMTP に 1 回ずつログインして確認したうえで、セッションディレクトリの `mail.json`（`0600`）に保存します。
   `mcp-icloud mail-logout` で削除できます。
3. または、サーバーに `MCP_ICLOUD_MAIL_USER` と `MCP_ICLOUD_MAIL_APP_PASSWORD` を設定します。`mail.json`
   より優先されます。サーバーは `imap.mail.me.com:993`（TLS）と `smtp.mail.me.com:587`（STARTTLS）です。

## 設定

| 変数 | 既定値 | 意味 |
| --- | --- | --- |
| `MCP_ICLOUD_SESSION_DIR` | `$XDG_CONFIG_HOME/mcp-icloud`、なければ `~/.config/mcp-icloud` | セッションと `mail.json` の置き場所 |
| `MCP_ICLOUD_APPLE_ID` | `account.json` の値 | `login` で保存した Apple ID を上書き |
| `MCP_ICLOUD_MAIL_BACKEND` | `auto` | `auto`、`web`、`imap`（上の「メール：2 つのバックエンド」を参照） |
| `MCP_ICLOUD_MAIL_USER` | `mail.json` の値。Web では iCloud の主アドレス | iCloud メールのアドレス（`@icloud.com`、`@me.com`、独自ドメイン）。既定の差出人 |
| `MCP_ICLOUD_MAIL_APP_PASSWORD` | `mail.json` の値 | IMAP バックエンドの App 用パスワード。設定すると `mail.json` より環境変数が使われる |
| `MCP_ICLOUD_MAIL_FROM_ALIASES` | — | 差出人として許可する追加アドレス（カンマ区切り） |
| `MCP_ICLOUD_SEND_ALLOWLIST` | 未設定＝制限なし | 宛先として許可するアドレスと `@domain`（カンマ区切り） |
| `MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB` | `20` | 送信・ダウンロードする添付のサイズ上限 |

## サーバーの登録

コマンドは `mcp-icloud serve` です。クライアントがシェルの `PATH` を引き継がない場合は、
`command -v mcp-icloud` で表示される絶対パスを使ってください。

**Claude Code**

```sh
claude mcp add icloud -- mcp-icloud serve
```

**Orca**

```sh
orca bot tools add "mcp-icloud serve" --bot <bot-name>
```

**任意の MCP クライアント（JSON 設定）**

```json
{
  "mcpServers": {
    "icloud": {
      "command": "mcp-icloud",
      "args": ["serve"]
    }
  }
}
```

`mail-login` を使えば、これらの設定に秘密情報は入りません。メールの認証情報を環境変数で渡す場合
（`claude mcp add -e …` や JSON の `env`）、クライアントの設定ファイルに平文で保存されます。`mail-login` か
プラットフォームのシークレットストアを使うことを勧めます。

## Linux VM と自律エージェント

すべて素の Python とファイルなので、Ubuntu などどの Linux でも同じように動きます。

「メールを非公開」と既定のメールバックエンドにはセッションが必要です。2FA のログインにはターミナルの前に人が
必要なので、無人の VM だけではセッションを作れません。方法は 2 つです。

1. **VM に SSH して自分でログインする**：`ssh vm` のあと `mcp-icloud login`。最も簡単で、1 台 1 セッションを保てます。
2. **自分のマシンでログインし、セッションディレクトリを VM にコピーする**：例 `scp -r ~/.config/mcp-icloud vm:~/.config/`。
   `0700`/`0600` を保ち、パスが違う場合は `MCP_ICLOUD_SESSION_DIR` を設定します。セッションはただのファイルで、
   特定のマシンに結び付いていません（`mail.json` を作っていれば一緒にコピーされます）。

VM にセッションを置きたくない場合は、その VM では IMAP のメールバックエンドだけを使います。サーバーに
`MCP_ICLOUD_MAIL_USER` と `MCP_ICLOUD_MAIL_APP_PASSWORD` をシークレットストアから渡すか、SSH して
`mcp-icloud mail-login` を実行します。この場合「メールを非公開」のツールはセッションがないと報告します。

**何を渡すのかを理解してください。** セッションディレクトリには、あなたの Apple ID でサインイン済みの icloud.com の
Web セッションが入っています。このサーバーは「メールを非公開」と Web メールバックエンドにしか使いませんが、
このファイルを読める人は、取り消すか期限が切れるまで icloud.com でできること全般（メール、Drive、写真、連絡先、
探す…）に使えてしまいます。信頼できるマシンとサービスにだけ置き、1 台 1 セッションにしてください。コピー同士は
それぞれ別に更新されるため、互いをサインアウトさせる可能性があります。メールの App 用パスワードはもっと範囲が
狭く、IMAP/SMTP にしか使えず、Apple ID へのサインインやアカウント設定の変更はできず、単独で取り消せます。

Web の Cookie が切れると、サーバーは保存されたセッションと 2FA の信頼トークンでパスワードなしに更新します。
Apple がその信頼を受け付けなくなると（期間は非公開。類似ツールの報告では数週間〜数か月）、「メールを非公開」の
各ツールは `mcp-icloud login` をやり直すよう伝えるエラーを返します（方法 2 の場合はコピーし直し）。Web メール
バックエンドも同様で、IMAP バックエンドはそのまま動きます。

## セキュリティ

- **秘密情報をチャットに書かない。** パスワード、2FA コード、App 用パスワードをエージェントとの会話に入力しない
  でください。`mcp-icloud login` と `mcp-icloud mail-login` はあなた自身のターミナルで読み取ります。App 用
  パスワードはログにも出力にも出さず、エラーメッセージからも伏せ字にします。
- **秘密情報は、コマンドが作るファイル・環境変数・シークレットストアで渡す。** プロンプト、コマンドライン、
  コミットするファイルには書かないでください。
- **アクセスの取り消し**：
  - セッション：`mcp-icloud logout` で Apple 側のセッションをサインアウトし、ローカルのファイルを削除します。
    できない場合は Apple ID のパスワードを変更するか、<https://account.apple.com> でサインイン中のデバイスを
    確認してください。コピーしたセッションディレクトリも同じセッションです。
  - IMAP メール：`mcp-icloud mail-logout` で保存したパスワードを削除し、App 用パスワード自体は
    <https://account.apple.com>（App 用パスワード）で削除します。

### 送信ポリシー

- **既定では制限がありません。このサーバーを使うエージェントは、あなたのアカウントとして誰にでも即時に送信
  できます。** それを任せられるエージェントにだけ渡してください。
- `MCP_ICLOUD_SEND_ALLOWLIST` を設定すると、`mail_send`、`mail_reply`、`mail_forward` はリストにない宛先
  （To、Cc、Bcc）を含むメールを拒否します。送信も下書き保存もしません。`mail_save_draft` は制限されません。
- 差出人はメールアドレス本体か `MCP_ICLOUD_MAIL_FROM_ALIASES` のいずれかに限ります（Web バックエンドでは
  加えて iCloud メールの設定で有効な送信元アドレスである必要があります）。
- ファイルパスを受け取るツール（`attachments`、`mail_download_attachment`）は、サーバーを動かしているユーザーの
  権限でファイルを読み書きします。ダウンロードは既存のファイルを上書きしません。

## アンインストール

```sh
mcp-icloud logout          # Apple 側でサインアウトし、ローカルのセッションファイルを削除
mcp-icloud mail-logout     # 保存したメールのパスワードを削除
claude mcp remove icloud   # またはクライアントの MCP 設定 / Orca の bot のツールから外す
uv tool uninstall mcp-icloud
rm -rf ~/.config/mcp-icloud
```

App 用パスワードを作っていれば <https://account.apple.com> で削除し、ほかのマシンにコピーしたセッション
ディレクトリも削除してください。

## 開発

```sh
git clone https://github.com/ak1tnk/mcp-icloud && cd mcp-icloud
uv sync
uv run pytest            # オフライン：pyicloud・IMAP・SMTP はモック、テスト中はネットワークを遮断
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

構成：iCloud の各サービスは `src/mcp_icloud/services/`（`hidemyemail.py`、`mail/`）にあり、それぞれ
`register(...)` を公開します。`server.py` がそれらをまとめ、`session.py` が保存済みセッションを読み込み、
`login.py` にターミナル用コマンドがあります。

## 謝辞

- [pyicloud](https://github.com/timlaing/pyicloud)：本プロジェクトの土台となる iCloud Web API クライアント。
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)。

## ライセンス

MIT。[LICENSE](../LICENSE) を参照してください。
