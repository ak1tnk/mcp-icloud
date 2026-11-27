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

## 简介

mcp-icloud 是一个用于 iCloud“隐藏邮件地址”和 iCloud 邮件的 [MCP](https://modelcontextprotocol.io) 服务器。
可以在 Claude Code、Codex、Grok、Muse、Qwen 等 AI 智能体中使用。支持 macOS 和 Linux。

**→ [用 AI 智能体安装](#agent-install)**

## 能做什么

- 注册网站时，新建一个“隐藏邮件地址”
- 列出地址、添加标签和备注、停用或重新启用地址
- 搜索和阅读邮件
- 保存附件
- 整理邮件：标为已读、加旗标、移动、归档、移到废纸篓
- 发送、回复、转发
- 只保存草稿，不发送

“隐藏邮件地址”需要 iCloud+。

<a id="agent-install"></a>

## 用 AI 智能体安装

复制下面的内容，发给你的智能体：

```
请按照以下步骤安装 mcp-icloud。请用简体中文和我交流。
https://raw.githubusercontent.com/ak1tnk/mcp-icloud/main/docs/agent-setup.md
```

智能体会完成安装、注册和检查。你需要亲自做的是：

- 智能体提示时，打开终端运行 `mcp-icloud login`，在终端里输入 Apple ID、密码和双重认证验证码。
  一次登录同时覆盖“隐藏邮件地址”和邮件。
- 不要把密码或验证码粘贴到聊天里。靠谱的智能体不会向你索要。
- 可选：如果想让邮件连接更稳定，在 <https://account.apple.com> 创建 App 专用密码，然后运行
  `mcp-icloud mail-login`。

更多提示词（日常任务、长期指令）：[prompts.md](prompts.md)

## 手动安装

需要 Python 3.11–3.13 和 [uv](https://docs.astral.sh/uv/)。

```sh
uv tool install git+https://github.com/ak1tnk/mcp-icloud
mcp-icloud login     # Apple ID、密码、双重认证验证码
mcp-icloud status    # 检查登录状态
```

注册服务器。如果客户端找不到 `mcp-icloud`，请使用 `command -v mcp-icloud` 显示的完整路径。

- **Claude Code**：`claude mcp add icloud -- mcp-icloud serve`
- **Orca**：`orca bot tools add "mcp-icloud serve" --bot <bot-name>`
- **其他 MCP 客户端**（JSON 配置）：

  ```json
  { "mcpServers": { "icloud": { "command": "mcp-icloud", "args": ["serve"] } } }
  ```

## 配置

全部可选。在 MCP 服务器的环境变量中设置。

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `MCP_ICLOUD_SESSION_DIR` | `$XDG_CONFIG_HOME/mcp-icloud`，否则 `~/.config/mcp-icloud` | 登录信息的保存位置 |
| `MCP_ICLOUD_APPLE_ID` | 来自 `mcp-icloud login` | 覆盖已保存的 Apple ID |
| `MCP_ICLOUD_MAIL_BACKEND` | `auto` | `web`、`imap` 或 `auto`（设置了 App 专用密码则用 IMAP，否则用 web） |
| `MCP_ICLOUD_MAIL_USER` | 来自 `mail-login`；web 下为你的主 iCloud 地址 | 你的 iCloud 邮件地址，默认发件人 |
| `MCP_ICLOUD_MAIL_APP_PASSWORD` | 来自 `mail-login` | IMAP/SMTP 用的 App 专用密码 |
| `MCP_ICLOUD_MAIL_FROM_ALIASES` | — | 可用作发件人的其他地址（逗号分隔） |
| `MCP_ICLOUD_SEND_ALLOWLIST` | 不限制 | 允许的收件人：地址和 `@domain`（逗号分隔） |
| `MCP_ICLOUD_MAIL_MAX_ATTACHMENT_MB` | `20` | 附件大小上限 |

## 在 Grok、Muse、Qwen 等智能体中使用

如果智能体运行在另一台机器上（云端电脑或服务器），那台机器上也需要登录。有两种方法：

1. **自己在那台机器上登录**（推荐）：用 SSH 连接，运行 `mcp-icloud login`。
2. **从你的电脑复制登录文件夹**：在你的电脑上运行 `mcp-icloud login`，然后把 `~/.config/mcp-icloud`
   复制到智能体所在机器的相同位置。注意不要让别人读取（`chmod 700`）。

风险：有了登录文件夹，就能使用你的整个 iCloud 账户（邮件、云盘、照片等），而不只是本服务器的功能。
只放在你信任的机器上。

如果只想用邮件、不放登录文件夹：在那台机器上使用 App 专用密码
（`mcp-icloud mail-login`，或 `MCP_ICLOUD_MAIL_USER` 和 `MCP_ICLOUD_MAIL_APP_PASSWORD`）。

## 注意事项

- **不会永久删除任何内容。**“废纸篓”是移到废纸篓文件夹。
- **这里不能删除“隐藏邮件地址”**，只能停用（和重新启用）。
- **发送会立即生效。** 默认情况下，智能体可以以你的名义发给任何人。要限制收件人，请设置
  `MCP_ICLOUD_SEND_ALLOWLIST`。
- **默认的邮件连接是实验性的。** 它使用 iCloud.com 的非公开 Web API，Apple 随时可能改动。IMAP 连接
  （App 专用密码）更稳定。在默认连接下，一次搜索只能用一个文字条件（发件人、收件人、主题或正文）。
- **登录会在一段时间后（几周到几个月）失效。** 届时请再次运行 `mcp-icloud login`。
  暂不支持使用硬件安全密钥的账户。
- **非官方项目。** 与 Apple 无关。
- **撤销访问**：`mcp-icloud logout` 会在 Apple 端退出登录并删除登录信息。`mcp-icloud mail-logout`
  会删除保存的 App 专用密码；也请在 <https://account.apple.com> 删除它。
- **卸载**：运行上面两个退出命令，从客户端移除服务器（`claude mcp remove icloud`），然后运行
  `uv tool uninstall mcp-icloud`。

基于 [pyicloud](https://github.com/timlaing/pyicloud) 和
[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)。许可证：[MIT](../LICENSE)

<details>
<summary>工具列表</summary>

- 隐藏邮件地址：`hme_list`、`hme_generate`（生成候选地址）、`hme_reserve`（加上标签和备注后保存）、
  `hme_update`、`hme_deactivate`、`hme_reactivate`
- 邮件：`mail_list_mailboxes`、`mail_search`、`mail_read`、`mail_download_attachment`、`mail_set_flags`、
  `mail_move`、`mail_archive`、`mail_trash`、`mail_send`、`mail_reply`、`mail_forward`、`mail_save_draft`

</details>
