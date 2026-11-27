# mcp-icloud

A small local [MCP](https://modelcontextprotocol.io) server (stdio) that lets an AI agent manage
iCloud+ **Hide My Email** addresses (via [pyicloud](https://github.com/timlaing/pyicloud)) and
read and send **iCloud Mail** (via IMAP/SMTP).

- Runs on Linux and macOS, headless (no TTY, no browser, no Keychain).
- The server never sees your Apple ID password: for Hide My Email you log in once with a
  separate command and the server reuses the stored session; Mail uses an app-specific password.
- Deleting Hide My Email addresses is intentionally not supported, and Mail "delete" only moves
  messages to Trash.

> Unofficial. Not affiliated with Apple. It uses the same private web APIs as icloud.com, which
> Apple can change at any time.

## Tools

### Hide My Email

| Tool | What it does |
| --- | --- |
| `hme_list` | List all addresses: email, label, note, active, forward-to, anonymous id |
| `hme_generate` | Get a new candidate address. **Not saved** until `hme_reserve` |
| `hme_reserve` | Save a generated address with a label (and optional note) |
| `hme_update` | Change the label and/or note of an address |
| `hme_deactivate` | Stop forwarding for an address (it stays in your list) |
| `hme_reactivate` | Resume forwarding for a deactivated address |

Addresses are identified by `anonymous_id`, as returned by `hme_list` / `hme_reserve`.

### Mail

| Tool | What it does |
| --- | --- |
| `mail_list_mailboxes` | List mailboxes (folders) and their special use (Drafts, Sent, Trash, …) |
| `mail_search` | Search a mailbox by sender, recipient, subject, text, date range, unread, flagged |
| `mail_read` | Read one message: headers, text body (HTML converted to text), attachment list |
| `mail_download_attachment` | Save one attachment to a new file (size-limited) |
| `mail_set_flags` | Mark messages read/unread and flagged/unflagged |
| `mail_move` / `mail_archive` | Move messages to another mailbox / to Archive |
| `mail_trash` | Move messages to Trash (never deletes permanently) |
| `mail_send` | Send a new message (optional attachments) |
| `mail_reply` / `mail_forward` | Reply (or reply all) / forward an existing message |
| `mail_save_draft` | Save a message to Drafts without sending |

Messages are identified by mailbox name + `uid`, as returned by `mail_search`.

## Requirements

- Python 3.11–3.13
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Hide My Email: an Apple ID with iCloud+ and two-factor authentication by code (trusted device
  or SMS). Accounts that require a hardware security key are not supported yet.
- Mail: an iCloud Mail address and an app-specific password.

## Install

```sh
git clone https://github.com/ak1tnk/mcp-icloud.git
cd mcp-icloud
uv tool install .          # puts `mcp-icloud` on your PATH (usually ~/.local/bin)
```

Or with pip: `pip install .` inside a virtualenv.

## Log in (once, in a terminal)

```sh
mcp-icloud login                       # prompts for Apple ID, password, then the 2FA code
mcp-icloud login --apple-id you@example.com
mcp-icloud status                      # checks that the stored session works
mcp-icloud logout                      # signs the session out at Apple, then deletes local files
```

The password is read with a hidden prompt, used once to sign in, and never stored. What is stored
is the session pyicloud gets back from Apple, in the session directory:

| Setting | Default |
| --- | --- |
| `MCP_ICLOUD_SESSION_DIR` | `$XDG_CONFIG_HOME/mcp-icloud`, else `~/.config/mcp-icloud` |
| `MCP_ICLOUD_APPLE_ID` | optional; overrides the Apple ID saved by `login` |

The directory is kept at mode `0700` and its files at `0600`. It contains `account.json` (your
Apple ID only), `<apple-id>.session` and `<apple-id>.cookiejar`.

### Headless machines and VMs

2FA needs a person at a terminal, so an unattended VM cannot log in by itself. Either:

1. **Log in on the VM over SSH**: `ssh vm`, then `mcp-icloud login` there. Simplest.
2. **Copy a session**: log in on any machine with a terminal, then copy the whole session
   directory to the VM (for example `scp -r ~/.config/mcp-icloud vm:~/.config/`), keep it
   `0700`/`0600`, and set `MCP_ICLOUD_SESSION_DIR` if the path differs. The session is plain files
   and is not tied to the machine.

Prefer one session per machine. Each running copy refreshes the session cookies on its own, so
two machines sharing one copy may invalidate each other (not verified).

How it works: `login` stores Apple's session token, a 2FA *trust token* and cookies. When the
short-lived web cookies expire, the server silently renews them with the session and trust
tokens, without a password. Once Apple stops honouring the trust token, renewal fails and every
tool returns an error telling you to run `mcp-icloud login` again (and re-copy the directory, if
you use option 2). Apple does not document how long that trust lasts; reports for similar tools
range from weeks to a few months.

## Set up Mail

Mail does not use the pyicloud session, so it works on headless machines without any 2FA step
and does not expire with it.

1. Create an app-specific password: sign in at <https://account.apple.com>, open
   **Sign-In and Security → App-Specific Passwords**, and generate one (it looks like
   `xxxx-xxxx-xxxx-xxxx`).
2. Give the server these environment variables:

| Variable | Meaning |
| --- | --- |
| `MCP_ICLOUD_MAIL_USER` | Your iCloud Mail address (`…@icloud.com`, `@me.com`, or a custom domain). Also the default From |
| `MCP_ICLOUD_MAIL_APP_PASSWORD` | The app-specific password |
| `MCP_ICLOUD_MAIL_FROM_ALIASES` | Optional, comma-separated: other addresses allowed as From (iCloud aliases, custom-domain addresses) |
| `MCP_ICLOUD_SEND_ALLOWLIST` | Optional, comma-separated addresses and `@domain` entries. Unset = no restriction |
| `MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB` | Optional size limit for attachments sent or downloaded (default 20) |

Servers: `imap.mail.me.com:993` (TLS) and `smtp.mail.me.com:587` (STARTTLS).

### Send policy

- **By default there is no restriction: any agent using this server can send mail as your
  account, to anyone, immediately.** Only give the server to agents you trust with that.
- If `MCP_ICLOUD_SEND_ALLOWLIST` is set, `mail_send`, `mail_reply` and `mail_forward` refuse any
  message with a recipient (To, Cc or Bcc) that is not listed; nothing is sent and no draft is
  saved. `mail_save_draft` is not restricted.
- From must be `MCP_ICLOUD_MAIL_USER` or one of `MCP_ICLOUD_MAIL_FROM_ALIASES`; anything else is
  rejected.

## Register the server

The server command is `mcp-icloud serve` (or just `mcp-icloud`). Use the absolute path if the
client does not inherit your shell's `PATH` (`command -v mcp-icloud` prints it).

Claude Code:

```sh
claude mcp add icloud -- mcp-icloud serve
# with a non-default session directory:
claude mcp add icloud -e MCP_ICLOUD_SESSION_DIR=/path/to/session -- mcp-icloud serve
# with Mail:
claude mcp add icloud -e MCP_ICLOUD_MAIL_USER=you@example.com \
  -e MCP_ICLOUD_MAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx -- mcp-icloud serve
```

Note that `-e` values are stored in plain text in the client's config file; protect it like the
session directory.

Orca bots:

```sh
orca bot tools add "mcp-icloud serve" --name icloud
```

Any other MCP client: run `mcp-icloud serve` over stdio.

## Security notes

- **What the stored session can do.** It is an icloud.com web session for your Apple ID. This
  server only calls Hide My Email, but anyone who can read the session files can use them for
  anything icloud.com allows (Mail, Drive, Photos, Contacts, Find My, …) until the session
  expires. Treat the session directory like a password.
- **Never commit or share it.** It lives outside the repository by default, and `.gitignore`
  excludes `*.session`, `*.cookiejar` and `account.json` in case you point it inside.
- **Revoke it.** `mcp-icloud logout` asks Apple to sign this session out, then deletes the local
  files. If Apple cannot be reached or does not confirm, change your Apple ID password or review
  signed-in devices at <https://account.apple.com>. A copied session directory on another machine
  is the same session.
- The agent can create and deactivate addresses but not delete them. Deactivating stops
  forwarding; `hme_reactivate` undoes it.
- **The app-specific password** gives full IMAP/SMTP access to your iCloud Mail: reading, moving
  and sending as you. It is read from the environment only, never logged, and scrubbed from
  error messages. Revoke it any time at <https://account.apple.com> (App-Specific Passwords); it
  cannot be used to sign in to your Apple ID or change account settings.
- Mail tools that take file paths (`attachments`, `mail_download_attachment`) read and write
  files as the user running the server. Downloads never overwrite an existing file.

## Development

```sh
uv sync
uv run pytest            # offline: pyicloud is mocked and network access is blocked in tests
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

Layout: each iCloud service lives under `src/mcp_icloud/services/` (`hidemyemail.py`,
`mail/`) and exposes a `register(...)` function; `server.py` wires them up; `session.py` loads the
stored pyicloud session; `login.py` holds the interactive commands.

## 日本語メモ

iCloud+ の「メールを非公開」アドレスを AI エージェントから一覧・生成・予約・ラベル編集・停止/再開し、
iCloud メールを IMAP/SMTP（App 用パスワード）で検索・閲覧・整理・送信するローカル MCP サーバーです。
送信は既定で無制限です（`MCP_ICLOUD_SEND_ALLOWLIST` で宛先を制限可能）。パスワードと 2FA はターミナルで `mcp-icloud login` を一度実行して入力し、
サーバーは保存されたセッションだけを使います。Linux VM で使う場合は VM に SSH して login するか、
セッションディレクトリをコピーしてください。セッションファイルはパスワード同等に扱ってください。

## License

MIT. See [LICENSE](LICENSE).
