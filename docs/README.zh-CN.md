<p align="center"><a href="../README.md">English</a> · <a href="README.ja.md">日本語</a> · <b>简体中文</b></p>

<h1 align="center">mcp-icloud</h1>

<p align="center">
  <strong>让你的 AI 智能体管理 iCloud“隐藏邮件地址”和 iCloud 邮件</strong>
</p>

<p align="center">
  <a href="../LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11+-green.svg?logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://github.com/ak1tnk/mcp-icloud/actions/workflows/ci.yml"><img src="https://github.com/ak1tnk/mcp-icloud/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

一个小巧的本地 [MCP](https://modelcontextprotocol.io) 服务器（stdio）。可在 Linux 和 macOS 上无界面运行，
适用于 Claude Code、Orca、运行在 Linux 虚拟机中的自主智能体，以及任何 MCP 客户端。

> 非官方项目，与 Apple 无关。“隐藏邮件地址”和默认的邮件后端使用与 icloud.com 相同的非公开 Web API，
> Apple 随时可能改动它。

---

## 为什么做这个

Apple 没有为 iCloud 提供官方 MCP 服务器或公开 API，所以智能体无法使用 iCloud：

- **隐藏邮件地址**（iCloud+）只存在于 Apple 的应用和 icloud.com 中，我们没有找到能管理它的 MCP 服务器。
  智能体替你注册某个服务时，无法为它新建转发地址、加标签，或之后停用它。
- **iCloud 邮件**没有适合智能体的接口：IMAP 需要单独的 App 专用密码，还要自己处理“不永久删除”“限制发送”等细节。

mcp-icloud 只需一次 `mcp-icloud login`，就把这两者作为 MCP 工具提供出来。Apple ID 密码不会交给智能体，
也不会永久删除任何内容。另外还提供更稳定的 IMAP/SMTP 邮件后端可选。

## 功能

| 服务 | 工具 | 需要 |
| --- | --- | --- |
| 隐藏邮件地址 | `hme_list`, `hme_generate`, `hme_reserve`, `hme_update`, `hme_deactivate`, `hme_reactivate` | iCloud+，以及 `mcp-icloud login` 得到的会话（Apple ID、密码和双重认证验证码由你在终端中输入） |
| 邮件 | `mail_list_mailboxes`, `mail_search`, `mail_read`, `mail_download_attachment`, `mail_set_flags`, `mail_move`, `mail_archive`, `mail_trash`, `mail_send`, `mail_reply`, `mail_forward`, `mail_save_draft` | 无需额外配置：使用同一个 `mcp-icloud login` 会话（Web 后端，实验性）。可选：为 IMAP/SMTP 后端准备 App 专用密码 |

- `hme_generate` 只生成候选地址，`hme_reserve` 才会保存。没有删除工具：`hme_deactivate` 停止转发，
  `hme_reactivate` 恢复。
- `mail_trash` 是移到废纸篓，绝不会永久删除。
- `mail_send`、`mail_reply`、`mail_forward` 会立即发送（见下文“发送策略”）。

## 快速开始：把这句话发给你的智能体

```
Set up mcp-icloud for me by following https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md
```

智能体会完成安装、注册 MCP 服务器并检查。你只需要亲自做一件事，而且是在终端里，不是在聊天中：

- 运行 `mcp-icloud login`，输入 Apple ID、密码和双重认证验证码。这一次登录同时覆盖隐藏邮件地址和邮件。
  如果在虚拟机上，请通过 SSH 运行，或复制会话（见下文“Linux 虚拟机与自主智能体”）。
- 可选：如果想用更稳定的 IMAP/SMTP 邮件后端，在 <https://account.apple.com> 创建 App 专用密码，
  然后运行 `mcp-icloud mail-login`（也可以用环境变量或平台的密钥存储）。

不要把密码、双重认证验证码或 App 专用密码粘贴到智能体的聊天里。靠谱的智能体不会向你索要。

更多可直接复制的提示词（虚拟机安装、日常任务、系统提示词片段）：[prompts.md](prompts.md)

## 你说 → 智能体做

| 你说 | 智能体会 |
| --- | --- |
| “为 example-shop.com 新建一个隐藏邮件地址” | `hme_generate`，再用标签“example-shop.com”调用 `hme_reserve`，然后告诉你地址 |
| “我在 example-shop 用的是哪个地址？” | 用 `hme_list` 按标签或备注查找 |
| “停用我在 example-shop 用的地址” | 用 `hme_list` 找到后调用 `hme_deactivate` |
| “给我看 billing@example.com 发来的未读邮件” | 带 `sender` 和 `unread_only` 调用 `mail_search` |
| “读最新那封，回复说我周五付款” | `mail_read`，然后 `mail_reply`（立即发送） |
| “起草回复，但先别发” | `mail_save_draft` |
| “把 newsletter@example.com 的邮件全部归档” | `mail_search`，然后 `mail_archive` |
| “检查 mcp-icloud 状态” | 运行 `mcp-icloud status`：会话是否有效、使用哪个邮件后端 |
| “卸载 mcp-icloud” | 先列出要删除的内容并征得同意，再按下文“卸载”执行 |

## 手动安装

需要：Python 3.11–3.13 和 [uv](https://docs.astral.sh/uv/)。

```sh
uv tool install git+https://github.com/ak1tnk/mcp-icloud
mcp-icloud --help
```

### 登录一次

```sh
mcp-icloud login        # Apple ID、密码（不回显），然后是双重认证验证码
mcp-icloud status       # 会话是否有效？使用哪个邮件后端？
mcp-icloud logout       # 在 Apple 端注销会话，然后删除本地文件
```

密码只使用一次，不会保存。暂不支持双重认证必须使用硬件安全密钥的账户。保存的是 Apple 返回的会话：
会话目录（权限 `0700`，文件 `0600`）中的 `account.json`（仅 Apple ID）、`<apple-id>.session` 和 `<apple-id>.cookiejar`。

### 邮件：两种后端

12 个 `mail_*` 工具在两种后端上名称和参数都相同。

| | Web 后端（默认） | IMAP/SMTP 后端（可选） |
| --- | --- | --- |
| 需要 | 只需 `mcp-icloud login` 的会话 | App 专用密码 |
| 状态 | **实验性**：使用 pyicloud 针对 icloud.com 非公开 Web API 的邮件功能 | 标准协议，稳定；密码不会像会话那样过期 |
| 何时使用 | 未配置 App 专用密码时 | 已配置 App 专用密码时 |

可用 `MCP_ICLOUD_MAIL_BACKEND=web` 或 `imap` 强制指定（默认 `auto`）。`mcp-icloud status` 会显示当前使用的后端。

Web 后端的限制（工具会返回说明限制的错误，而不是悄悄返回不同的结果）：

- `mail_search`：每次搜索只能有一个文本条件（`sender`、`recipient`、`subject` 或 `text`）；`unread_only` 和
  `flagged_only` 不能同时使用，也不能与文本条件组合；按日期筛选最多扫描 1000 封；除非能从筛选条件推断，
  `seen`/`flagged` 为 `null`；`total_matches` 为近似值。
- `mail_move`：iCloud 拒绝移入垃圾邮件、草稿等部分特殊文件夹。
- 发送时会先创建草稿再提交。如果 Apple 的响应不明确，工具会说明；重试前请先检查“已发送”和“草稿”。

设置 IMAP 后端：

1. 登录 <https://account.apple.com>，打开 **登录与安全 → App 专用密码**，创建一个（格式类似 `xxxx-xxxx-xxxx-xxxx`）。
2. 运行 `mcp-icloud mail-login`：它会询问你的 iCloud 邮件地址和 App 专用密码（不回显），分别登录一次 IMAP 和
   SMTP 进行验证，然后保存到会话目录的 `mail.json`（`0600`）。`mcp-icloud mail-logout` 可删除它。
3. 或者为服务器设置 `MCP_ICLOUD_MAIL_USER` 和 `MCP_ICLOUD_MAIL_APP_PASSWORD`，优先级高于 `mail.json`。
   服务器地址：`imap.mail.me.com:993`（TLS）、`smtp.mail.me.com:587`（STARTTLS）。

## 配置

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `MCP_ICLOUD_SESSION_DIR` | `$XDG_CONFIG_HOME/mcp-icloud`，否则 `~/.config/mcp-icloud` | 会话和 `mail.json` 的位置 |
| `MCP_ICLOUD_APPLE_ID` | 来自 `account.json` | 覆盖 `login` 保存的 Apple ID |
| `MCP_ICLOUD_MAIL_BACKEND` | `auto` | `auto`、`web` 或 `imap`（见上文“邮件：两种后端”） |
| `MCP_ICLOUD_MAIL_USER` | 来自 `mail.json`；Web 后端为 iCloud 主地址 | 你的 iCloud 邮件地址（`@icloud.com`、`@me.com` 或自定义域名）；默认发件人 |
| `MCP_ICLOUD_MAIL_APP_PASSWORD` | 来自 `mail.json` | IMAP 后端的 App 专用密码。设置后使用环境变量而不是 `mail.json` |
| `MCP_ICLOUD_MAIL_FROM_ALIASES` | — | 允许作为发件人的其他地址（逗号分隔） |
| `MCP_ICLOUD_SEND_ALLOWLIST` | 未设置 = 不限制 | 允许的收件人地址和 `@domain`（逗号分隔） |
| `MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB` | `20` | 发送或下载附件的大小上限 |

## 注册服务器

命令是 `mcp-icloud serve`。如果客户端不继承你的 shell `PATH`，请使用 `command -v mcp-icloud` 显示的绝对路径。

**Claude Code**

```sh
claude mcp add icloud -- mcp-icloud serve
```

**Orca**

```sh
orca bot tools add "mcp-icloud serve" --bot <bot-name>
```

**任意 MCP 客户端（JSON 配置）**

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

使用 `mail-login` 时，这些配置里没有任何机密。如果改用环境变量传递邮件凭据（`claude mcp add -e …` 或 JSON 的
`env`），它们会以明文保存在客户端的配置文件中；建议使用 `mail-login` 或平台的密钥存储。

## Linux 虚拟机与自主智能体

一切都是纯 Python 和文件，在 Ubuntu 或其他 Linux 上运行方式相同。

隐藏邮件地址和默认邮件后端需要会话，而双重认证登录需要有人在终端前操作，所以无人值守的虚拟机无法自行创建会话。
有两种方法：

1. **SSH 登录虚拟机，亲自登录**：`ssh vm`，然后 `mcp-icloud login`。最简单，并能保持一台机器一个会话。
2. **在自己的电脑上登录，再把会话目录复制到虚拟机**，例如 `scp -r ~/.config/mcp-icloud vm:~/.config/`。保持
   `0700`/`0600` 权限，路径不同时设置 `MCP_ICLOUD_SESSION_DIR`。会话就是普通文件，不绑定某台机器
   （如果你创建过 `mail.json`，也会一起复制）。

如果不想把会话放到虚拟机上，可以在那台虚拟机上只使用 IMAP 邮件后端：从平台的密钥存储为服务器提供
`MCP_ICLOUD_MAIL_USER` 和 `MCP_ICLOUD_MAIL_APP_PASSWORD`（或 SSH 后运行 `mcp-icloud mail-login`）。
此时隐藏邮件地址工具会提示会话缺失。

**清楚你交出的是什么。** 会话目录里是一个已用你的 Apple ID 登录的 icloud.com Web 会话。本服务器只把它用于
隐藏邮件地址和 Web 邮件后端，但任何能读取这些文件的人，在会话被撤销或过期之前，都能用它做 icloud.com 允许的
一切（邮件、iCloud 云盘、照片、通讯录、查找……）。只把它放在你信任的机器和服务上，并尽量一台机器一个会话：
各个副本会各自刷新，可能互相把对方注销。邮件的 App 专用密码范围更窄：只能用于 IMAP/SMTP，不能登录 Apple ID
或修改账户设置，并且可以单独撤销。

Web Cookie 过期后，服务器会用保存的会话和双重认证信任令牌在不需要密码的情况下续期。当 Apple 不再接受该信任时
（Apple 未公开期限；类似工具的反馈从几周到几个月不等），每个隐藏邮件地址工具都会返回错误，提示你重新运行
`mcp-icloud login`（如果用的是方法 2，还需重新复制目录）。Web 邮件后端同样如此，IMAP 后端则不受影响。

## 安全

- **不要在聊天中提供机密。** 不要把密码、双重认证验证码或 App 专用密码输入到与智能体的对话里。
  `mcp-icloud login` 和 `mcp-icloud mail-login` 在你自己的终端中读取它们。App 专用密码不会写入日志或输出，
  并会从错误信息中隐去。
- **通过命令生成的文件、环境变量或密钥存储传递机密**，不要写进提示词、命令行或提交到仓库的文件。
- **撤销访问**：
  - 会话：`mcp-icloud logout` 会在 Apple 端注销会话并删除本地文件。如果无法做到，请修改 Apple ID 密码，或在
    <https://account.apple.com> 检查已登录的设备。复制出去的会话目录也是同一个会话。
  - IMAP 邮件：`mcp-icloud mail-logout` 删除已保存的密码；App 专用密码本身请在 <https://account.apple.com>
    （App 专用密码）中删除。

### 发送策略

- **默认不做任何限制：使用本服务器的任何智能体都可以以你的账户身份立即给任何人发邮件。** 只交给你信得过的智能体。
- 设置 `MCP_ICLOUD_SEND_ALLOWLIST` 后，`mail_send`、`mail_reply` 和 `mail_forward` 会拒绝含有不在列表中的收件人
  （To、Cc、Bcc）的邮件；不会发送，也不会保存草稿。`mail_save_draft` 不受限制。
- 发件人只能是你的邮件地址或 `MCP_ICLOUD_MAIL_FROM_ALIASES` 中的地址（Web 后端还要求它是 iCloud 邮件设置中
  已启用的发件地址）。
- 接收文件路径的工具（`attachments`、`mail_download_attachment`）以运行服务器的用户身份读写文件。下载不会覆盖已有文件。

## 卸载

```sh
mcp-icloud logout          # 在 Apple 端注销并删除本地会话文件
mcp-icloud mail-logout     # 删除已保存的邮件密码
claude mcp remove icloud   # 或从客户端的 MCP 配置 / Orca 机器人的工具中移除
uv tool uninstall mcp-icloud
rm -rf ~/.config/mcp-icloud
```

如果创建过 App 专用密码，请在 <https://account.apple.com> 删除它，并删除复制到其他机器上的会话目录。

## 开发

```sh
git clone https://github.com/ak1tnk/mcp-icloud && cd mcp-icloud
uv sync
uv run pytest            # 离线：pyicloud、IMAP 和 SMTP 均为模拟；测试中网络被阻断
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

结构：每个 iCloud 服务位于 `src/mcp_icloud/services/`（`hidemyemail.py`、`mail/`），并各自提供 `register(...)`；
`server.py` 负责组装，`session.py` 读取已保存的会话，`login.py` 包含终端命令。

## 致谢

- [pyicloud](https://github.com/timlaing/pyicloud)：本项目所基于的 iCloud Web API 客户端。
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)。

## 许可证

MIT。见 [LICENSE](../LICENSE)。
