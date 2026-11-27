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

## Overview

mcp-icloud is an [MCP](https://modelcontextprotocol.io) server for iCloud Hide My Email and iCloud
Mail. It works with AI agents such as Claude Code, Codex, Grok, Muse and Qwen. It runs on macOS
and Linux.

**→ [Install with your AI agent](#agent-install)**

## What you can do

- Create a new Hide My Email address when you sign up for a website
- List your addresses, add labels and notes, and turn addresses off and on again
- Search and read your mail
- Save attachments as files
- Organize mail: mark as read, flag, move, archive, move to Trash
- Send, reply and forward
- Save a draft without sending it

You need iCloud+ for Hide My Email.

<a id="agent-install"></a>

## Install with your AI agent

Copy this and send it to your agent:

```
Set up mcp-icloud by following these steps. Please reply to me in English.
https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md
```

The agent installs it, registers it and checks it. You do this yourself:

- When the agent asks, open a terminal and run `mcp-icloud login`. Enter your Apple ID, password
  and 2FA code there. One login covers Hide My Email and Mail.
- Never paste a password or code into the chat. A good agent will not ask for one.
- Optional: for a more stable mail connection, create an app-specific password at
  <https://account.apple.com> and run `mcp-icloud mail-login`.

More prompts (everyday tasks, standing instructions): [docs/prompts.md](docs/prompts.md)

## Manual install

You need Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/).

```sh
uv tool install git+https://github.com/ak1tnk/mcp-icloud
mcp-icloud login     # Apple ID, password, 2FA code
mcp-icloud status    # check the login
```

Register the server. If your client can't find `mcp-icloud`, use the full path from
`command -v mcp-icloud`.

- **Claude Code**: `claude mcp add icloud -- mcp-icloud serve`
- **Orca**: `orca bot tools add "mcp-icloud serve" --bot <bot-name>`
- **Other MCP clients** (JSON config):

  ```json
  { "mcpServers": { "icloud": { "command": "mcp-icloud", "args": ["serve"] } } }
  ```

## Configuration

All optional. Set them in the MCP server's environment.

| Variable | Default | Meaning |
| --- | --- | --- |
| `MCP_ICLOUD_SESSION_DIR` | `$XDG_CONFIG_HOME/mcp-icloud`, else `~/.config/mcp-icloud` | Where the login is stored |
| `MCP_ICLOUD_APPLE_ID` | from `mcp-icloud login` | Overrides the saved Apple ID |
| `MCP_ICLOUD_MAIL_BACKEND` | `auto` | `web`, `imap`, or `auto` (IMAP if an app-specific password is set, else web) |
| `MCP_ICLOUD_MAIL_USER` | from `mail-login`; on web, your main iCloud address | Your iCloud Mail address; the default From |
| `MCP_ICLOUD_MAIL_APP_PASSWORD` | from `mail-login` | App-specific password for IMAP/SMTP |
| `MCP_ICLOUD_MAIL_FROM_ALIASES` | — | Extra From addresses, comma-separated |
| `MCP_ICLOUD_SEND_ALLOWLIST` | no limit | Allowed recipients: addresses and `@domain`, comma-separated |
| `MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB` | `20` | Attachment size limit |

## Using it with Grok, Muse, Qwen and other agents

If your agent runs on another machine (a cloud computer or server), the login must be on that
machine too. Two ways:

1. **Log in there yourself** (recommended): connect with SSH and run `mcp-icloud login`.
2. **Copy the login folder** from your computer: run `mcp-icloud login` on your computer, then copy
   `~/.config/mcp-icloud` to the same place on the agent's machine. Keep it private
   (`chmod 700`).

Risk: the login folder gives full access to your iCloud account (Mail, Drive, Photos, …), not
only what this server does. Only put it on machines you trust.

To use Mail only, without the login folder: use an app-specific password there
(`mcp-icloud mail-login`, or `MCP_ICLOUD_MAIL_USER` and `MCP_ICLOUD_MAIL_APP_PASSWORD`).

## Notes

- **Nothing is deleted permanently.** "Trash" moves mail to the Trash folder.
- **Hide My Email addresses can't be deleted here**, only turned off (and on again).
- **Sending is immediate**, and by default an agent can send to anyone as you. To limit
  recipients, set `MCP_ICLOUD_SEND_ALLOWLIST`.
- **The default mail connection is experimental.** It uses iCloud.com's private web API, which
  Apple can change. The IMAP connection (app-specific password) is more stable. On the default
  connection, a search can use only one text filter (sender, recipient, subject or text) at a time.
- **The login expires** after a while (weeks to months). Then run `mcp-icloud login` again.
  Accounts that use a hardware security key are not supported yet.
- **Unofficial.** Not affiliated with Apple.
- **Revoke access**: `mcp-icloud logout` signs out at Apple and deletes the login.
  `mcp-icloud mail-logout` deletes the stored app-specific password; also delete it at
  <https://account.apple.com>.
- **Uninstall**: run the two logout commands above, remove the server from your client
  (`claude mcp remove icloud`), then `uv tool uninstall mcp-icloud`.

Built on [pyicloud](https://github.com/timlaing/pyicloud) and the
[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk). License: [MIT](LICENSE).

<details>
<summary>Tool reference</summary>

- Hide My Email: `hme_list`, `hme_generate` (proposes an address), `hme_reserve` (saves it with a
  label and note), `hme_update`, `hme_deactivate`, `hme_reactivate`
- Mail: `mail_list_mailboxes`, `mail_search`, `mail_read`, `mail_download_attachment`,
  `mail_set_flags`, `mail_move`, `mail_archive`, `mail_trash`, `mail_send`, `mail_reply`,
  `mail_forward`, `mail_save_draft`

</details>
