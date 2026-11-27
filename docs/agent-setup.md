# Set up mcp-icloud

For the AI agent doing the setup. Run the commands yourself. The human only does the steps
marked **Human**, in their own terminal.

mcp-icloud is a local MCP server (stdio) that gives you tools for iCloud Hide My Email (`hme_*`)
and iCloud Mail (`mail_*`). Repository: <https://github.com/ak1tnk/mcp-icloud>.

## Hard rules

- **Reply to the human in the language they used in their request.**
- **Never ask the human to type a password, 2FA code or app-specific password into the chat**, and
  never accept one if they offer it: tell them to use the terminal command instead. If one is
  pasted anyway, do not repeat it, and tell them to revoke it at <https://account.apple.com>.
- **Never try a platform's secret placeholder or proxy token as a password.** Apple's sign-in
  needs the real password inside the process, so a platform that keeps secrets away from
  programs can't log in this way; use the login folder (step 4).
- **Never print secrets.** Don't `cat` `mail.json`, `*.session`, `*.cookiejar` or env files, and
  don't echo environment variables that hold passwords.
- **Never run `mcp-icloud login` or `mcp-icloud mail-login` for the human.** They are interactive
  and need the human's credentials.
- **Only act when asked.** Don't reserve (`hme_reserve`), deactivate or reactivate addresses, and
  don't send, reply, forward, move, archive or trash mail unless the human asked for that action.
  Sending happens immediately and cannot be undone; when wording or recipients are unclear, show
  the draft first or use `mail_save_draft`.
- **Confirm before uninstalling**, after listing exactly what will be removed.

## 0. Before you start

- You need to run shell commands. If you can't, tell the human: "Please enable command execution
  for me, then ask again."
- Detect the OS: `uname -s` (`Linux` or `Darwin`). Windows is not supported; suggest WSL.
- Already installed? `mcp-icloud --help` succeeds → go to [Upgrade](#upgrade) or straight to step 2.
- `uv --version` fails? Tell the human: "I'm installing uv, a small tool that installs Python
  command-line programs. It needs no admin password." Then run:

  ```sh
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  If `uv` is still not found, open a new shell or use `~/.local/bin/uv`.

## 1. Install

```sh
uv tool install git+https://github.com/ak1tnk/mcp-icloud
mcp-icloud --help
```

If `mcp-icloud` is not found, run `uv tool update-shell` and open a new shell, or use
`~/.local/bin/mcp-icloud`. Note the absolute path: `command -v mcp-icloud`.

## 2. Register the MCP server with your host

Use the absolute path from step 1. Pick what matches your host:

- **Claude Code**: `claude mcp add icloud -- <abs-path>/mcp-icloud serve`
- **Orca**: `orca bot tools add "<abs-path>/mcp-icloud serve" --bot <bot-name>`
- **Other MCP clients**: add to the client's MCP config:

  ```json
  { "mcpServers": { "icloud": { "command": "<abs-path>/mcp-icloud", "args": ["serve"] } } }
  ```

Do not put credentials in the server command or config. If the platform has a secret store and
the human prefers it for Mail, it should inject `MCP_ICLOUD_MAIL_USER` and
`MCP_ICLOUD_MAIL_APP_PASSWORD` as environment variables.

Most hosts need a restart or a new session before new MCP tools appear.

## 3. Check

```sh
mcp-icloud status
```

It prints whether the session works and which mail backend is active. Right after install the
session is expected to be missing.

## 4. Tell the human what they must do

Say this, adapted to their situation.

**Log in once** (covers Hide My Email, which needs iCloud+, and Mail). In a terminal on the
machine where the server runs:

```
mcp-icloud login
```

It asks for the Apple ID, password and 2FA code in the terminal.

**If you can't give the human a terminal on the machine where the server runs** (a cloud VM, or a
platform such as Muse), ask them to make a separate login for you on their own computer. Tell
them exactly, with `<agent>` replaced by your name (e.g. `~/mcp-icloud-muse`):

```
MCP_ICLOUD_SESSION_DIR=~/mcp-icloud-<agent> mcp-icloud login
```

"Then upload that folder to me (zipped if this chat only takes files) or copy it to this machine.
Don't send any password or code in the chat." When you have it, put it at `~/.config/mcp-icloud`
(or point `MCP_ICLOUD_SESSION_DIR` at it), run `chmod 700` on the folder and `chmod 600` on the
files in it, then run `mcp-icloud status`. Tell them they can revoke just this login with
`MCP_ICLOUD_SESSION_DIR=~/mcp-icloud-<agent> mcp-icloud logout`, and that when it expires
(weeks to months) they repeat the same steps. If they can SSH into the machine, running
`mcp-icloud login` there also works.

Risk to state plainly: the session directory is a signed-in icloud.com session. Anyone who can
read it can use the whole iCloud account (Mail, Drive, Photos, Find My, …), not just what this
server does, until it is revoked with `mcp-icloud logout` or by changing the Apple ID password.
Only put it on machines they trust; one session per machine is best.

**Mail** then works through that session (the "web" backend, experimental). Optionally, for the
steadier IMAP/SMTP backend, or to use Mail on a machine without the session:

1. Create an app-specific password at <https://account.apple.com> → Sign-In and Security →
   App-Specific Passwords.
2. In a terminal on the machine where the server runs: `mcp-icloud mail-login` (asks for the
   address and the app-specific password, verifies them, stores them privately). Or put
   `MCP_ICLOUD_MAIL_USER` and `MCP_ICLOUD_MAIL_APP_PASSWORD` in the platform's secret store.

When an app-specific password is configured, Mail uses IMAP automatically
(`MCP_ICLOUD_MAIL_BACKEND=auto|web|imap` overrides).

Also tell them: by default any agent using this server can send mail as them to anyone. To limit
recipients they can set `MCP_ICLOUD_SEND_ALLOWLIST` (comma-separated addresses and `@domain`
entries) in the server's environment.

When they say they're done, run `mcp-icloud status` again, restart the MCP server if your host
requires it, and try a read-only tool (`hme_list` or `mail_list_mailboxes`).

## Using the tools

- Hide My Email: `hme_generate` proposes an address but does not save it; `hme_reserve` saves it
  with a label (use the site or service name) and optional note. Addresses are identified by
  `anonymous_id`. There is no delete.
- Mail: messages are identified by mailbox name + `uid` from `mail_search`. `mail_read` does not
  mark messages read unless `mark_read` is true. `mail_trash` moves to Trash; nothing is deleted
  permanently.
- On the web backend some searches are limited (one text criterion per search; unread/flagged
  filters not combined). The error says so; split the search or tell the human the IMAP backend
  removes the limit.
- An error saying the session is missing or expired means the human must run
  `mcp-icloud login` again (or make and send a new login folder, as in step 4). An error saying Mail is not configured means
  the IMAP backend was forced without an app-specific password. Relay these to the human; don't
  try to work around them.

## Upgrade

```sh
uv tool upgrade mcp-icloud
mcp-icloud status
```

If that reports the tool was not installed from git, reinstall:
`uv tool install --force git+https://github.com/ak1tnk/mcp-icloud`. Restart the MCP server
afterwards. Stored sessions and `mail.json` are kept.

## Uninstall

First list what will be removed and ask the human to confirm:

- the MCP server registration in your host,
- the `mcp-icloud` program,
- the session directory `~/.config/mcp-icloud` (or `$MCP_ICLOUD_SESSION_DIR`), which holds the
  Hide My Email session and the stored Mail password.

After they confirm:

```sh
mcp-icloud logout          # signs the session out at Apple, deletes local session files
mcp-icloud mail-logout     # deletes the stored Mail password
claude mcp remove icloud   # or remove it from your host's MCP config / the Orca bot's tools
uv tool uninstall mcp-icloud
rm -rf ~/.config/mcp-icloud
```

Then tell the human to delete the app-specific password at <https://account.apple.com> if they
created one, and to remove any session directory they copied to other machines.
