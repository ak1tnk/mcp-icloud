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

## 概要

mcp-icloud は、iCloud の「メールを非公開」と iCloud メールを扱う [MCP](https://modelcontextprotocol.io)
サーバーです。Claude Code、Codex、Grok、Muse、Qwen などの AI エージェントから使えます。macOS と Linux で動きます。

**→ [AI エージェントでインストールする](#agent-install)**

## できること

- Web サイトの会員登録用に「メールを非公開」のアドレスを新しく作る
- アドレスの一覧表示、ラベルやメモの設定、無効化と再有効化
- メールの検索と閲覧
- 添付ファイルをフォルダに保存
- メールの整理：既読にする、フラグを付ける、移動、アーカイブ、ゴミ箱に入れる
- 送信、返信、転送
- 送らずに下書きとして保存

「メールを非公開」には iCloud+ が必要です。

<a id="agent-install"></a>

## AI エージェントでインストールする

これをコピーして、エージェントに送ってください。

```
次の手順に従って mcp-icloud をセットアップしてください。やり取りは日本語でお願いします。
https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md
```

インストール、登録、動作確認はエージェントが行います。あなたがやることは次のとおりです。

- エージェントに言われたら、ターミナルで `mcp-icloud login` を実行し、Apple ID・パスワード・2FA コードを
  そこで入力します。このログイン 1 回で「メールを非公開」とメールの両方が使えます。
- パスワードやコードをチャットに貼らないでください。まともなエージェントなら求めてきません。
- 任意：メールの接続をより安定させたい場合は、<https://account.apple.com> で App 用パスワードを作り、
  `mcp-icloud mail-login` を実行します。

ほかのプロンプト（日常のタスク、常設の指示）：[prompts.md](prompts.md)

## 手動でインストールする

Python 3.11〜3.13 と [uv](https://docs.astral.sh/uv/) が必要です。

```sh
uv tool install git+https://github.com/ak1tnk/mcp-icloud
mcp-icloud login     # Apple ID・パスワード・2FA コード
mcp-icloud status    # ログインを確認
```

サーバーを登録します。クライアントが `mcp-icloud` を見つけられない場合は、`command -v mcp-icloud` で
表示されるフルパスを使ってください。

- **Claude Code**：`claude mcp add icloud -- mcp-icloud serve`
- **Orca**：`orca bot tools add "mcp-icloud serve" --bot <bot-name>`
- **ほかの MCP クライアント**（JSON 設定）：

  ```json
  { "mcpServers": { "icloud": { "command": "mcp-icloud", "args": ["serve"] } } }
  ```

## 設定

すべて任意です。MCP サーバーの環境変数として設定します。

| 変数 | 既定値 | 意味 |
| --- | --- | --- |
| `MCP_ICLOUD_SESSION_DIR` | `$XDG_CONFIG_HOME/mcp-icloud`、なければ `~/.config/mcp-icloud` | ログイン情報の保存場所 |
| `MCP_ICLOUD_APPLE_ID` | `mcp-icloud login` で保存したもの | 保存済みの Apple ID を上書き |
| `MCP_ICLOUD_MAIL_BACKEND` | `auto` | `web`、`imap`、`auto`（App 用パスワードがあれば IMAP、なければ web） |
| `MCP_ICLOUD_MAIL_USER` | `mail-login` で保存したもの。web ではメインの iCloud アドレス | iCloud メールのアドレス。既定の差出人 |
| `MCP_ICLOUD_MAIL_APP_PASSWORD` | `mail-login` で保存したもの | IMAP/SMTP 用の App 用パスワード |
| `MCP_ICLOUD_MAIL_FROM_ALIASES` | — | 差出人に使える追加アドレス（カンマ区切り） |
| `MCP_ICLOUD_SEND_ALLOWLIST` | 制限なし | 送信を許す宛先：アドレスと `@domain`（カンマ区切り） |
| `MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB` | `20` | 添付ファイルのサイズ上限 |

## Grok・Muse・Qwen などのエージェントで使う

エージェントが別のマシン（クラウド上のコンピューターやサーバー）で動いている場合は、そのマシンにも
ログインが必要です。方法は 2 つあります。

1. **そのマシンで自分でログインする**（おすすめ）：SSH で接続して `mcp-icloud login` を実行します。
2. **自分のコンピューターからログインフォルダをコピーする**：自分のコンピューターで `mcp-icloud login` を実行し、
   `~/.config/mcp-icloud` をエージェントのマシンの同じ場所にコピーします。他人が読めないようにしてください
   （`chmod 700`）。

注意：ログインフォルダがあれば、このサーバーの機能に限らず iCloud アカウント全体（メール、Drive、写真など）を
使えてしまいます。信頼できるマシンにだけ置いてください。

ログインフォルダを置かずにメールだけ使う場合は、そのマシンで App 用パスワードを使います
（`mcp-icloud mail-login`、または `MCP_ICLOUD_MAIL_USER` と `MCP_ICLOUD_MAIL_APP_PASSWORD`）。

## 注意事項

- **完全削除はしません。**「ゴミ箱」はゴミ箱フォルダへの移動です。
- **「メールを非公開」のアドレスはここでは削除できません。** 無効化（と再有効化）だけです。
- **送信はすぐに行われます。** 既定では、エージェントはあなたとして誰にでも送れます。宛先を制限するには
  `MCP_ICLOUD_SEND_ALLOWLIST` を設定してください。
- **既定のメール接続は試験的です。** iCloud.com の非公開 Web API を使うため、Apple の変更で動かなくなることが
  あります。IMAP 接続（App 用パスワード）のほうが安定しています。既定の接続では、1 回の検索で使える文字列の
  条件（差出人・宛先・件名・本文）は 1 つだけです。
- **ログインは一定期間（数週間〜数か月）で切れます。** そのときは `mcp-icloud login` をもう一度実行してください。
  ハードウェアセキュリティキーを使うアカウントにはまだ対応していません。
- **非公式です。** Apple とは関係ありません。
- **アクセスの取り消し**：`mcp-icloud logout` で Apple 側からサインアウトし、ログイン情報を削除します。
  `mcp-icloud mail-logout` は保存した App 用パスワードを削除します。<https://account.apple.com> でも削除してください。
- **アンインストール**：上の 2 つのログアウトを実行し、クライアントからサーバーを外して
  （`claude mcp remove icloud`）、`uv tool uninstall mcp-icloud` を実行します。

[pyicloud](https://github.com/timlaing/pyicloud) と
[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) を使っています。ライセンス：[MIT](../LICENSE)

<details>
<summary>ツール一覧</summary>

- メールを非公開：`hme_list`、`hme_generate`（アドレスの候補を出す）、`hme_reserve`（ラベルとメモを付けて保存）、
  `hme_update`、`hme_deactivate`、`hme_reactivate`
- メール：`mail_list_mailboxes`、`mail_search`、`mail_read`、`mail_download_attachment`、`mail_set_flags`、
  `mail_move`、`mail_archive`、`mail_trash`、`mail_send`、`mail_reply`、`mail_forward`、`mail_save_draft`

</details>
