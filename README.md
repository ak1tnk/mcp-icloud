# mcp-icloud

A small local [MCP](https://modelcontextprotocol.io) server (stdio) that lets an AI agent manage
iCloud+ **Hide My Email** addresses. It wraps [pyicloud](https://github.com/timlaing/pyicloud).

- Runs on Linux and macOS, headless (no TTY, no browser, no Keychain).
- The server never sees your password: you log in once with a separate command, and the server
  reuses the stored session.
- Hide My Email only for now. Deleting addresses is intentionally not supported.

> Unofficial. Not affiliated with Apple. It uses the same private web APIs as icloud.com, which
> Apple can change at any time.

## Tools

| Tool | What it does |
| --- | --- |
| `hme_list` | List all addresses: email, label, note, active, forward-to, anonymous id |
| `hme_generate` | Get a new candidate address. **Not saved** until `hme_reserve` |
| `hme_reserve` | Save a generated address with a label (and optional note) |
| `hme_update` | Change the label and/or note of an address |
| `hme_deactivate` | Stop forwarding for an address (it stays in your list) |
| `hme_reactivate` | Resume forwarding for a deactivated address |

Addresses are identified by `anonymous_id`, as returned by `hme_list` / `hme_reserve`.

## Requirements

- Python 3.11–3.13
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- An Apple ID with iCloud+ and two-factor authentication by code (trusted device or SMS).
  Accounts that require a hardware security key are not supported yet.

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
mcp-icloud logout                      # deletes the local session files
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

Prefer one session per machine: each running copy refreshes the same session, and two machines
sharing one copy may sign each other out.

When the session is missing or has expired, every tool returns an error that says so and tells
you to run `mcp-icloud login` again (and re-copy the directory, if you use option 2). Apple's
trust for a session typically lasts on the order of weeks to a couple of months; after that a new
login with password and 2FA is needed.

## Register the server

The server command is `mcp-icloud serve` (or just `mcp-icloud`). Use the absolute path if the
client does not inherit your shell's `PATH` (`command -v mcp-icloud` prints it).

Claude Code:

```sh
claude mcp add icloud -- mcp-icloud serve
# with a non-default session directory:
claude mcp add icloud -e MCP_ICLOUD_SESSION_DIR=/path/to/session -- mcp-icloud serve
```

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
- **Revoke it.** `mcp-icloud logout` only deletes local files. To cut the session off at Apple,
  change your Apple ID password, or review signed-in sessions and devices at
  <https://account.apple.com>.
- The agent can create and deactivate addresses but not delete them. Deactivating stops
  forwarding; `hme_reactivate` undoes it.

## Development

```sh
uv sync
uv run pytest            # offline: pyicloud is mocked and network access is blocked in tests
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

Layout: `src/mcp_icloud/services/<service>.py` holds one iCloud service's tools and exposes
`register(server, provider)`; `server.py` wires them up; `session.py` loads the stored session;
`login.py` holds the interactive commands.

## 日本語メモ

iCloud+ の「メールを非公開」アドレスを AI エージェントから一覧・生成・予約・ラベル編集・停止/再開する
ローカル MCP サーバーです。パスワードと 2FA はターミナルで `mcp-icloud login` を一度実行して入力し、
サーバーは保存されたセッションだけを使います。Linux VM で使う場合は VM に SSH して login するか、
セッションディレクトリをコピーしてください。セッションファイルはパスワード同等に扱ってください。

## License

MIT. See [LICENSE](LICENSE).
