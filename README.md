<p align="center"><b>English</b> · <a href="docs/README.ja.md">日本語</a> · <a href="docs/README.zh-CN.md">简体中文</a></p>

<h1 align="center">mcp-icloud</h1>

<p align="center">
  <strong>Let your AI agent manage iCloud Hide My Email and iCloud Mail</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11+-green.svg?logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://github.com/ak1tnk/mcp-icloud/actions/workflows/ci.yml"><img src="https://github.com/ak1tnk/mcp-icloud/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

A small local [MCP](https://modelcontextprotocol.io) server (stdio). It runs on Linux and macOS,
headless, and works with Claude Code, Orca, autonomous agents in Linux VMs, and any other MCP
client.

> Unofficial. Not affiliated with Apple. Hide My Email and the default Mail backend use the same
> private web API as icloud.com, which Apple can change at any time.

---

## Why

Apple has no official MCP server or public API for iCloud, so agents can't touch it:

- **Hide My Email** (iCloud+) exists only in Apple's apps and on icloud.com, and we know of no MCP
  server that manages it. An agent signing you up for a service can't create a fresh relay
  address for it, label it, or turn it off later.
- **iCloud Mail** has no agent-friendly interface: IMAP needs a separate app-specific password and
  careful wiring (no permanent deletes, send restrictions).

mcp-icloud adds both as MCP tools behind a single `mcp-icloud login`, keeps your Apple ID password
away from the agent, and never deletes anything permanently. An IMAP/SMTP mail backend is
available as a steadier option.

## What it can do

| Service | Tools | Needs |
| --- | --- | --- |
| Hide My Email | `hme_list`, `hme_generate`, `hme_reserve`, `hme_update`, `hme_deactivate`, `hme_reactivate` | iCloud+ and a session from `mcp-icloud login` (Apple ID, password and 2FA code, typed by you in a terminal) |
| Mail | `mail_list_mailboxes`, `mail_search`, `mail_read`, `mail_download_attachment`, `mail_set_flags`, `mail_move`, `mail_archive`, `mail_trash`, `mail_send`, `mail_reply`, `mail_forward`, `mail_save_draft` | Nothing extra: the same `mcp-icloud login` session (web backend, experimental). Optional: an app-specific password for the IMAP/SMTP backend |

- `hme_generate` only proposes an address; `hme_reserve` saves it. There is no delete tool:
  `hme_deactivate` stops forwarding and `hme_reactivate` undoes it.
- `mail_trash` moves messages to Trash. Nothing is ever deleted permanently.
- `mail_send`, `mail_reply` and `mail_forward` send immediately (see [Send policy](#send-policy)).

## Quick start: send this to your agent

```
Set up mcp-icloud for me by following https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md
```

The agent installs it, registers the MCP server and checks it. You will be asked to do one thing
yourself, in a terminal, never in the chat:

- Run `mcp-icloud login` and enter your Apple ID, password and 2FA code there. That one login
  covers Hide My Email and Mail. On a VM, do it over SSH or copy a session (see
  [Linux VMs](#running-on-linux-vms-and-autonomous-agents)).
- Optional, for the steadier IMAP/SMTP mail backend: create an app-specific password at
  <https://account.apple.com> and run `mcp-icloud mail-login` (or use environment variables or
  your platform's secret store).

Never paste a password, 2FA code or app-specific password into an agent chat. A well-behaved
agent will not ask for one.

More copy-paste prompts (setup on a VM, everyday tasks, a system-prompt snippet):
[docs/prompts.md](docs/prompts.md).

## What you say → what the agent does

| You say | The agent |
| --- | --- |
| "Make me a new Hide My Email for example-shop.com" | `hme_generate`, then `hme_reserve` labelled "example-shop.com", and tells you the address |
| "Which address did I use for example-shop?" | `hme_list`, matching the label or note |
| "Deactivate the address I used for example-shop" | finds it with `hme_list`, then `hme_deactivate` |
| "Show unread mail from billing@example.com" | `mail_search` with `sender` and `unread_only` |
| "Read the latest one and reply that I'll pay on Friday" | `mail_read`, then `mail_reply` (sends immediately) |
| "Draft a reply but don't send it" | `mail_save_draft` |
| "Archive everything from newsletter@example.com" | `mail_search`, then `mail_archive` |
| "Check mcp-icloud status" | runs `mcp-icloud status`: is the session valid, is Mail configured |
| "Uninstall mcp-icloud" | lists what will be removed, asks you, then follows [Uninstall](#uninstall) |

## Manual setup

Requirements: Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/ak1tnk/mcp-icloud
mcp-icloud --help
```

### Log in once

```sh
mcp-icloud login        # Apple ID, password (hidden), then the 2FA code
mcp-icloud status       # is the session valid? which mail backend is in use?
mcp-icloud logout       # signs the session out at Apple, then deletes the local files
```

The password is used once and never stored. Accounts that require a hardware security key for
2FA are not supported yet. What is stored is the session Apple returns: `account.json` (your
Apple ID only), `<apple-id>.session` and `<apple-id>.cookiejar`, in the session directory (mode
`0700`, files `0600`).

### Mail: two backends

The twelve `mail_*` tools have the same names and arguments on both backends.

| | Web backend (default) | IMAP/SMTP backend (optional) |
| --- | --- | --- |
| Needs | the `mcp-icloud login` session, nothing else | an app-specific password |
| Status | **experimental**: uses pyicloud's Mail support for icloud.com's private web API | standard protocols, stable; the password does not expire with the session |
| Used when | no app-specific password is configured | an app-specific password is configured |

Force one with `MCP_ICLOUD_MAIL_BACKEND=web` or `imap` (default `auto`). `mcp-icloud status` shows
which one is active.

Web backend limits (the tool returns an error that names the limit instead of a different result):

- `mail_search`: one text criterion (`sender`, `recipient`, `subject` or `text`) per search;
  `unread_only` and `flagged_only` can't be combined with each other or with a text criterion;
  date filters scan at most 1000 messages; `seen`/`flagged` are `null` unless implied by the
  filter; `total_matches` is approximate.
- `mail_move`: iCloud refuses moves into Junk, Drafts and some special folders.
- Sending creates a draft and submits it. If Apple's answer is unclear, the tool says so; check
  Sent and Drafts before retrying.

To set up the IMAP backend:

1. Sign in at <https://account.apple.com>, open **Sign-In and Security → App-Specific
   Passwords**, and create one (it looks like `xxxx-xxxx-xxxx-xxxx`).
2. Run `mcp-icloud mail-login`: it asks for your iCloud Mail address and the app-specific password
   (hidden), checks them with one IMAP and SMTP login, and stores them in `mail.json` in the
   session directory (`0600`). `mcp-icloud mail-logout` deletes it.
3. Or set `MCP_ICLOUD_MAIL_USER` and `MCP_ICLOUD_MAIL_APP_PASSWORD` for the server; they take
   precedence over `mail.json`. Servers: `imap.mail.me.com:993` (TLS), `smtp.mail.me.com:587`
   (STARTTLS).

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `MCP_ICLOUD_SESSION_DIR` | `$XDG_CONFIG_HOME/mcp-icloud`, else `~/.config/mcp-icloud` | Where the session and `mail.json` live |
| `MCP_ICLOUD_APPLE_ID` | from `account.json` | Overrides the Apple ID saved by `login` |
| `MCP_ICLOUD_MAIL_BACKEND` | `auto` | `auto`, `web` or `imap` (see [Mail: two backends](#mail-two-backends)) |
| `MCP_ICLOUD_MAIL_USER` | from `mail.json`; on web, your primary iCloud address | Your iCloud Mail address (`@icloud.com`, `@me.com` or a custom domain); the default From |
| `MCP_ICLOUD_MAIL_APP_PASSWORD` | from `mail.json` | IMAP backend: the app-specific password. When set, the environment is used instead of `mail.json` |
| `MCP_ICLOUD_MAIL_FROM_ALIASES` | — | Comma-separated extra addresses allowed as From |
| `MCP_ICLOUD_SEND_ALLOWLIST` | unset = no restriction | Comma-separated addresses and `@domain` entries allowed as recipients |
| `MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB` | `20` | Size limit for attachments sent or downloaded |

## Register the server

The command is `mcp-icloud serve`. If your client does not inherit your shell's `PATH`, use the
absolute path from `command -v mcp-icloud`.

**Claude Code**

```sh
claude mcp add icloud -- mcp-icloud serve
```

**Orca**

```sh
orca bot tools add "mcp-icloud serve" --bot <bot-name>
```

**Any MCP client (JSON config)**

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

With `mail-login` there is nothing secret in these configs. If you pass Mail credentials as
environment variables instead (`claude mcp add -e …`, a JSON `env` block), they are stored in plain
text in the client's config file; prefer `mail-login` or your platform's secret store.

## Running on Linux VMs and autonomous agents

Everything is plain Python and files, so it runs the same on Ubuntu or any other Linux.

Hide My Email and the default Mail backend need a session, and the 2FA login needs a person at a
terminal, so an unattended VM cannot create one by itself. Two ways:

1. **SSH into the VM and log in there yourself**: `ssh vm`, then `mcp-icloud login`. Simplest, and
   keeps one session per machine.
2. **Log in on your own machine and copy the session directory** to the VM, for example
   `scp -r ~/.config/mcp-icloud vm:~/.config/`. Keep it `0700`/`0600` and set
   `MCP_ICLOUD_SESSION_DIR` if the path differs. The session is plain files and is not tied to a
   machine. (This copies `mail.json` too, if you created one.)

If you would rather not place the session on the VM at all, use only the IMAP mail backend there:
give the server `MCP_ICLOUD_MAIL_USER` and `MCP_ICLOUD_MAIL_APP_PASSWORD` from your platform's
secret store (or run `mcp-icloud mail-login` over SSH). Hide My Email tools will then report that
the session is missing.

**Know what you are handing over.** The session directory holds a signed-in icloud.com web
session for your Apple ID. This server only calls Hide My Email, but anyone who can read those
files can use them for anything icloud.com allows (Mail, Drive, Photos, Contacts, Find My, …)
until the session is revoked or expires. This server uses it for Hide My Email and the web mail
backend. Only place it on machines and services you trust, and
prefer one session per machine: copies refresh independently and may sign each other out. The
Mail app-specific password is narrower: IMAP/SMTP only, it cannot sign in to your Apple ID or
change account settings, and you can revoke it on its own.

When the web cookies expire, the server renews them with the stored session and 2FA trust
tokens, without a password. Once Apple stops honouring the trust (Apple does not say how long;
reports for similar tools range from weeks to a few months), every Hide My Email tool returns an
error telling you to run `mcp-icloud login` again (and re-copy the directory if you used option 2).
The same goes for the web mail backend; the IMAP backend keeps working.

## Security

- **No secrets in chat.** Never type passwords, 2FA codes or app-specific passwords into an agent
  conversation. `mcp-icloud login` and `mcp-icloud mail-login` read them in your own terminal.
  The app-specific password is never logged, never printed, and is scrubbed from error messages.
- **Pass secrets through files the commands create, environment variables or a secret store**,
  never in a prompt, a command line or a committed file.
- **Revoke access**:
  - Hide My Email: `mcp-icloud logout` signs the session out at Apple and deletes the local files.
    If that is not possible, change your Apple ID password or review signed-in devices at
    <https://account.apple.com>. A copied session directory is the same session.
  - Mail: `mcp-icloud mail-logout` deletes the stored password; delete the app-specific password
    itself at <https://account.apple.com> (App-Specific Passwords).

### Send policy

- **By default there is no restriction: any agent using this server can send mail as your
  account, to anyone, immediately.** Only give it to agents you trust with that.
- If `MCP_ICLOUD_SEND_ALLOWLIST` is set, `mail_send`, `mail_reply` and `mail_forward` refuse a
  message with any recipient (To, Cc or Bcc) not on the list; nothing is sent and no draft is
  saved. `mail_save_draft` is not restricted.
- From must be your Mail address or one of `MCP_ICLOUD_MAIL_FROM_ALIASES` (on the web backend
  it must also be a sender address enabled in your iCloud Mail settings).
- Tools that take file paths (`attachments`, `mail_download_attachment`) read and write files as
  the user running the server. Downloads never overwrite an existing file.

## Uninstall

```sh
mcp-icloud logout          # sign out at Apple and delete the local session files
mcp-icloud mail-logout     # delete the stored Mail password
claude mcp remove icloud   # or remove it from your client's MCP config / the Orca bot's tools
uv tool uninstall mcp-icloud
rm -rf ~/.config/mcp-icloud
```

Then delete the app-specific password at <https://account.apple.com> if you created one, and
remove any session directory you copied to other machines.

## Development

```sh
git clone https://github.com/ak1tnk/mcp-icloud && cd mcp-icloud
uv sync
uv run pytest            # offline: pyicloud, IMAP and SMTP are mocked; network is blocked in tests
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

Layout: each iCloud service lives under `src/mcp_icloud/services/` (`hidemyemail.py`, `mail/`)
and exposes a `register(...)` function; `server.py` wires them up; `session.py` loads the stored
session; `login.py` holds the terminal commands.

## Acknowledgements

- [pyicloud](https://github.com/timlaing/pyicloud), the iCloud web API client this builds on.
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).

## License

MIT. See [LICENSE](LICENSE).
