# Prompts for agents

Copy-paste prompts for using mcp-icloud with AI agents such as Claude Code, Codex, Grok, Muse and
Qwen. Each prompt is given in English, Japanese and Simplified Chinese, and asks the agent to reply
in that language. Replace placeholders such as `example-shop.com` with your own values. Never put
passwords or app-specific passwords in a prompt or chat. The only thing you may type in chat is
the 6-digit 2FA code during the secret store login (B), when the agent asks for it.

- [A. Setup](#a-setup)
- [B. Setup when the agent runs on another machine](#b-setup-when-the-agent-runs-on-another-machine)
- [C. Everyday tasks](#c-everyday-tasks)
- [D. Standing instructions for long-running agents](#d-standing-instructions-for-long-running-agents)

---

## A. Setup

**English**

```
Set up mcp-icloud by following these steps. Please reply to me in English.
https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md
```

**日本語**

```
次の手順に従って mcp-icloud をセットアップしてください。やり取りは日本語でお願いします。
https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md
```

**简体中文**

```
请按照以下步骤安装 mcp-icloud。请用简体中文和我交流。
https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md
```

---

## B. Setup when the agent runs on another machine

For agents that run on a cloud computer or server (for example Grok, Muse or Qwen). First, in the
agent platform's secret store or connector settings, set `MCP_ICLOUD_APPLE_ID` and
`MCP_ICLOUD_APPLE_PASSWORD` for the mcp-icloud server. Then send the prompt. Prefer SSH and
`mcp-icloud login`? Use prompt A instead.

**English**

```
Set up mcp-icloud on this machine by following
https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md
Register it as an MCP server for yourself. I stored MCP_ICLOUD_APPLE_ID and
MCP_ICLOUD_APPLE_PASSWORD in your secret store for it. Log in with icloud_login_start; when Apple
sends a 2FA code, ask me for it in chat and call icloud_login_verify. Never ask me for my password.
Then try hme_list and report. Please reply to me in English.
```

**日本語**

```
https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md の手順に従って、
このマシンに mcp-icloud をセットアップし、あなた自身の MCP サーバーとして登録してください。
MCP_ICLOUD_APPLE_ID と MCP_ICLOUD_APPLE_PASSWORD はシークレットストアに保存済みです。
icloud_login_start でログインし、Apple から 2FA コードが届いたらチャットで私に聞いて
icloud_login_verify を呼んでください。パスワードは絶対に聞かないでください。
最後に hme_list を試して報告してください。やり取りは日本語でお願いします。
```

**简体中文**

```
请按照 https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md 的步骤，
在这台机器上安装 mcp-icloud，并把它注册为你自己的 MCP 服务器。我已在你的密钥存储中为它保存了
MCP_ICLOUD_APPLE_ID 和 MCP_ICLOUD_APPLE_PASSWORD。请用 icloud_login_start 登录；Apple 发送双重认证
验证码后，在聊天中向我询问，然后调用 icloud_login_verify。绝不要向我索要密码。
最后试一下 hme_list 并向我报告。请用简体中文和我交流。
```

---

## C. Everyday tasks

### Create an address for a signup

**English**

```
Create a new Hide My Email address for signing up at example-shop.com. Label it
"example-shop.com" and add the note "signup <today's date>". Tell me the address.
Please reply in English.
```

**日本語**

```
example-shop.com の会員登録用に「メールを非公開」のアドレスを新しく作ってください。
ラベルは「example-shop.com」、メモは「会員登録 <今日の日付>」にして、アドレスを教えてください。
日本語で答えてください。
```

**简体中文**

```
为在 example-shop.com 注册新建一个“隐藏邮件地址”。标签设为“example-shop.com”，
备注写“注册 <今天的日期>”，然后把地址告诉我。请用简体中文回答。
```

### List and deactivate addresses

**English**

```
List my Hide My Email addresses as a table (address, label, note, active). Then deactivate the
one labelled "example-shop.com". Do not touch any other address. Please reply in English.
```

**日本語**

```
「メールを非公開」のアドレスを表（アドレス・ラベル・メモ・有効/無効）で一覧してください。
そのうえでラベルが「example-shop.com」のものだけを無効化してください。他のアドレスには触らないでください。
日本語で答えてください。
```

**简体中文**

```
用表格列出我的“隐藏邮件地址”（地址、标签、备注、是否启用）。然后只停用标签为
“example-shop.com”的那一个，不要改动其他地址。请用简体中文回答。
```

### Triage unread mail

**English**

```
Look at my unread mail in INBOX from the last 3 days. Summarize each message in one line
(sender, subject, what it wants from me). Don't mark anything read, don't move or reply to
anything. Then suggest which ones to archive and wait for my answer. Please reply in English.
```

**日本語**

```
INBOX の過去 3 日間の未読メールを確認し、1 通 1 行で要約してください（差出人・件名・私に求めていること）。
既読にしたり、移動や返信をしたりはしないでください。そのうえでアーカイブしてよさそうなものを提案し、
私の返事を待ってください。日本語で答えてください。
```

**简体中文**

```
查看 INBOX 中最近 3 天的未读邮件，每封用一行概括（发件人、主题、需要我做什么）。
不要标记为已读，不要移动或回复任何邮件。然后建议哪些可以归档，并等待我的答复。请用简体中文回答。
```

### Reply to a message

**English**

```
Find the latest mail from billing@example.com and draft a reply saying I will pay by Friday.
Show me the draft first; send it only after I say "send". Please reply in English.
```

**日本語**

```
billing@example.com からの最新のメールを探して、「金曜日までに支払います」という返信の下書きを作ってください。
まず下書きを見せて、私が「送信」と言ってから送ってください。日本語で答えてください。
```

**简体中文**

```
找到 billing@example.com 最新的一封邮件，起草一封回复，说明我会在周五前付款。
先把草稿给我看，等我说“发送”之后再发送。请用简体中文回答。
```

---

## D. Standing instructions for long-running agents

Add this to the agent's standing instructions. Edit the send rule to match your own send policy.

**English**

```
You have the mcp-icloud MCP tools.
- Hide My Email (hme_*): hme_list shows addresses; hme_generate only proposes an address,
  hme_reserve saves it with a label (use the site name) and optional note; hme_update changes
  label/note; hme_deactivate stops forwarding, hme_reactivate resumes it. There is no delete.
- Mail (mail_*): mail_search and mail_read are read-only (mail_read does not mark read unless
  mark_read=true). mail_set_flags, mail_move, mail_archive and mail_trash change mailboxes
  (trash = move to Trash, never permanent). mail_send, mail_reply and mail_forward send
  immediately; mail_save_draft only saves to Drafts.
Rules:
- Never ask for, accept, store or repeat passwords or app-specific passwords. If a tool says
  the session is expired: when MCP_ICLOUD_APPLE_ID and MCP_ICLOUD_APPLE_PASSWORD are set, call
  icloud_login_start, ask the human for the 6-digit 2FA code (the only secret you may ask for)
  and call icloud_login_verify; otherwise tell the human to run `mcp-icloud login` in a
  terminal. If Mail is not configured, tell them to run `mcp-icloud mail-login`.
- Reserve, deactivate or reactivate addresses, and change mailboxes, only when asked.
- Send mail only when the human asked for that specific message; if wording or recipients are
  unclear, save a draft and ask.
- Reply to the human in English.
```

**日本語**

```
あなたは mcp-icloud の MCP ツールを使えます。
- メールを非公開（hme_*）: hme_list でアドレス一覧。hme_generate は候補を出すだけで、
  hme_reserve でラベル（サイト名を使う）と任意のメモを付けて保存。hme_update でラベル/メモを変更。
  hme_deactivate で転送停止、hme_reactivate で再開。削除はできません。
- メール（mail_*）: mail_search と mail_read は読み取りのみ（mail_read は mark_read=true のときだけ既読化）。
  mail_set_flags・mail_move・mail_archive・mail_trash はメールボックスを変更（trash はゴミ箱への移動で、完全削除はしない）。
  mail_send・mail_reply・mail_forward は即時送信。mail_save_draft は下書きに保存するだけ。
ルール:
- パスワード・App 用パスワードを求めない・受け取らない・保存しない・繰り返さない。
  セッション切れのエラーが出たら、MCP_ICLOUD_APPLE_ID と MCP_ICLOUD_APPLE_PASSWORD が設定されていれば
  icloud_login_start を呼び、6 桁の 2FA コード（聞いてよい唯一の秘密情報）を人間に聞いて
  icloud_login_verify を呼ぶ。設定されていなければ、ターミナルで `mcp-icloud login` を実行するよう伝える。
  メール未設定のエラーなら `mcp-icloud mail-login` を実行するよう伝える。
- アドレスの予約・無効化・再有効化と、メールボックスの変更は頼まれたときだけ行う。
- メールは人間がその内容の送信を頼んだときだけ送る。文面や宛先が曖昧なら下書きを保存して確認する。
- 人間には日本語で返事をする。
```

**简体中文**

```
你可以使用 mcp-icloud 的 MCP 工具。
- 隐藏邮件地址（hme_*）：hme_list 列出地址；hme_generate 只生成候选地址，
  hme_reserve 用标签（使用网站名）和可选备注保存；hme_update 修改标签/备注；
  hme_deactivate 停止转发，hme_reactivate 恢复转发。不能删除。
- 邮件（mail_*）：mail_search 和 mail_read 只读（mail_read 仅在 mark_read=true 时标记已读）。
  mail_set_flags、mail_move、mail_archive、mail_trash 会修改邮箱（trash 是移到废纸篓，不会永久删除）。
  mail_send、mail_reply、mail_forward 会立即发送；mail_save_draft 只保存到草稿箱。
规则：
- 不要索要、接收、保存或复述密码或 App 专用密码。如果工具提示会话过期：若已设置
  MCP_ICLOUD_APPLE_ID 和 MCP_ICLOUD_APPLE_PASSWORD，调用 icloud_login_start，向人类询问 6 位双重认证
  验证码（唯一可以询问的秘密信息），再调用 icloud_login_verify；否则请人类在终端运行
  `mcp-icloud login`。如果提示邮件未配置，请人类运行 `mcp-icloud mail-login`。
- 只有在被要求时才保留、停用或重新启用地址，以及修改邮箱。
- 只有当人类要求发送那封具体的邮件时才发送；如果措辞或收件人不明确，先保存草稿并询问。
- 用简体中文回复人类。
```
