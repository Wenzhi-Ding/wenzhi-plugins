# model-providers

各家模型厂商在 ZCode 里的正确配置（端点、协议 kind、reasoning 档位、参数怪癖）是逐个踩坑试出来的：Grok 拒绝 `reasoning_effort: max`、MiniMax 官方 openai 端点不收 `thinking: enabled` 要切 anthropic 端点、x.ai 的 Responses API 回放 422 要用 chat completions。这个插件把这些经验做成一份结构化的 registry 数据文件，随插件市场分发。

订阅本插件后跑一次 `/providers-sync`，本机的 provider 配置就与最新经验对齐。API key 由每个订阅者自己粘贴，插件与仓库中永远不出现 key。

## 安装

1. 打开 ZCode → 设置 → 插件管理 → 发现
2. 点 `+` 添加 GitHub 仓库：`Wenzhi-Ding/wenzhi-plugins`（已添加过市场则跳过）
3. 在列表中找到 model-providers，点安装（默认启用，下个会话生效）

## 使用

安装后在新会话里运行：

- `/providers-sync`：无参数，输出状态总览（哪些可新增、哪些有差异），不写入。
- `/providers-sync grok qwen`：只同步指定条目，参数支持 name 和 alias，大小写不敏感。
- `/providers-sync all`：同步全部。

同步只动 `baseURL`、`kind`、`models`，你自己加的模型和你已填的 API key 不会被覆盖或删除。

## 贴 key

新建的 provider 条目 `apiKey` 是空的，两种方式填：

1. 跑 `/providers-sync` 时按提示把 key 粘贴到对话里，由 agent 写入 `~/.zcode/v2/config.json`（该文件本来就是明文存 key，不降安全性）。每家的 key 申请地址见同步时的提示。
2. 自己编辑 `~/.zcode/v2/config.json`，找到对应 provider 条目填 `options.apiKey`。

## 重启与验证

reasoning 类字段改动要重启 ZCode 才完成规范化。同步后请重启，重启后再跑一次 `/providers-sync` 确认 reasoning 档位还在。

## 收录条目（v0.1.0）

| name | kind | baseURL | 模型 |
|---|---|---|---|
| Kimi | anthropic | https://api.kimi.com/coding | k3 |
| DeepSeek | openai | https://api.deepseek.com | deepseek-v4-flash, deepseek-v4-pro |
| B.AI | anthropic | https://api.b.ai | gpt-5.6-luna, gpt-5.6-sol |
| MiniMax | anthropic | https://api.minimaxi.com/anthropic | minimax-m3 |
| Grok | openai-compatible | https://api.x.ai/v1 | grok-4.5, grok-4.6 |
| Qwen | anthropic | https://dashscope-intl.aliyuncs.com/apps/anthropic | qwen3.8-max |
| OpenCode Claude | anthropic | https://opencode.ai/zen | claude-opus-5 |
| OpenCode GPT | openai | https://opencode.ai/zen/v1 | gpt-5.6-sol |

B.AI 与 OpenCode 属第三方中转服务，订阅者需自备账号；Kimi 端点为 Coding Plan 订阅端点。各条目的坑与注意事项在同步时展示（registry 的 notes 字段）。

## 更新

厂商改端点或出现新的坑时，维护者更新 registry 并发版。你在插件管理里更新本插件，新会话里再跑一次 `/providers-sync` 即可对齐。
