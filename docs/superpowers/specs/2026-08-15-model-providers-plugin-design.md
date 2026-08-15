# model-providers 插件设计（v0.1.0）

日期：2026-08-15
状态：待用户审阅

## 背景与目标

各家模型厂商在 ZCode 里的正确配置组合（端点选择、协议类型、reasoning 档位、参数怪癖）是逐个踩坑试出来的：Grok 拒绝 `reasoning_effort: max`、MiniMax 官方 openai 端点不收 `thinking: enabled` 要切 anthropic 端点、x.ai 的 Responses API 回放 422 要用 chat completions。这些经验目前只存在个人的 zcode-tools skill 里，别人无法复用。

本插件把这些经验做成一份结构化的 registry 数据文件，随插件市场分发。订阅者更新插件后跑一次 `/providers-sync` 命令，本机的 provider 配置就与最新经验对齐。API key 由每个订阅者自己粘贴，插件与仓库中永远不出现 key。

## 范围

**做**：registry 数据文件 + `/providers-sync` 同步命令 + 面向订阅者的 README。

**不做（第一版）**：
- 不打包 council/swarm agent 定义（后续版本考虑，registry 的 UUID 设计已为此留了余地）。
- 不做排障 skill。
- 不做自动同步（无 hook）。
- 不收录 Google：官方端点脱离私人网关后的行为未实测，收进 registry 前必须先验证，第一版先不收。
- 不收录 `builtin:*` 条目（BigModel/Z.ai 订阅计划，与个人订阅绑定，无同步意义）。

## 插件结构

```
plugins/model-providers/
├── .zcode-plugin/plugin.json        # name: model-providers, version: 0.1.0
├── registry/registry.json           # 纯数据文件，不是插件组件类型；插件目录整体保留在缓存中，随版本更新
├── commands/providers-sync.md       # /providers-sync 命令
└── README.md                        # 面向订阅者：安装、贴 key、同步
```

根 `marketplace.json` 增加对应条目。发版时 `plugin.json` 与 `marketplace.json` 两处版本号同步 bump（仓库 AGENTS.md 已有此规则）。

## registry.json 格式

```json
{
  "schemaVersion": 1,
  "providers": [
    {
      "uuid": "2fb07fac-e43f-4095-9d71-031b7b9f03fe",
      "name": "Grok",
      "aliases": ["grok", "xai"],
      "kind": "openai-compatible",
      "baseURL": "https://api.x.ai/v1",
      "apiKeyRequired": true,
      "apiKeyDoc": "https://console.x.ai/",
      "notes": "必须用 chat completions（kind 保持 openai-compatible）；reasoning 只到 high，max 被拒",
      "models": {
        "grok-4.6": {
          "reasoning": { "enabled": true, "variants": ["low", "medium", "high"], "defaultVariant": "high" },
          "limit": { "context": 1000000 },
          "modalities": { "input": ["text"], "output": ["text"] }
        }
      }
    }
  ]
}
```

字段说明：
- `uuid`：沿用维护者本机 config.json 的现有 UUID。UUID 跨机器固定，未来若发布引用 `<uuid>/<model>` 的 agent 定义，可直接绑定。
- `aliases`：同步命令的选择参数支持 name 和 alias，大小写不敏感。
- `apiKeyRequired`：布尔值（已验证本机 config 中该字段为 bool），随条目分发。
- `apiKeyDoc`：该厂商 key 的申请页地址；实现时逐家从官网核对填写，拿不准的条目留空。
- `notes`：踩坑经验的结构化落点（端点选择原因、已验证的档位、已知怪癖），同步时展示给用户，也是维护时的备忘。
- `models.*`：与 config.json 主进程写回格式一致。`reasoning` 必须用 `variants/defaultVariant` 键名（写 `levels` 数组会被启动规范化静默丢弃）；需要钉住不被自动剪枝的模型，同步写入时统一加 `"zcode": {"modified": true}`（钉子由同步动作加，registry 数据文件本身不携带）。

**收录清单（7 家 8 条）**，baseURL 与 kind 全部来自维护者本机验证过的工作配置：

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

B.AI 与 OpenCode 属第三方中转服务，订阅者需自备账号；Kimi 端点为 Coding Plan 订阅端点。这些背景写进各条目的 notes。

## /providers-sync 命令行为

目标文件：`~/.zcode/v2/config.json` 的 `provider` 对象。定位 registry：命令正文中写 `${CLAUDE_PLUGIN_ROOT}/registry/registry.json`，由 ZCode 运行时替换为插件安装目录。

### 无参数：状态总览

读 registry 与本地 config.json，输出状态表。每个 provider 三种状态：
- **本地没有**（可新增）
- **两边有差异**（可更新；列出具体差异：baseURL、kind、新增模型、reasoning variants 变化）
- **仅本地存在**（不动，不提示操作）

输出后询问用户要同步哪些。

### 带参数：选择性同步

- `/providers-sync grok qwen`：只同步指定条目（name 或 alias，大小写不敏感）。
- `/providers-sync all`：全部。

### 匹配规则

先按 UUID 匹配本地条目；匹配不到再按 name（大小写不敏感）。命中已有条目则更新该条目，保留本地的 UUID、`options.apiKey`、provider 级 `zcode` 字段（如 `deletedModels`）；未命中则新建条目，用 registry 的 UUID，`apiKey` 留空。

### 合并规则

- `baseURL`、`kind`、`models` 以 registry 为准。
- 本地存在而 registry 没有的模型条目：保留不删（用户自己加的模型不动）。
- 写入的每个模型条目统一加 `"zcode": {"modified": true}` 钉子，防 ZCode 自动剪枝。
- `reasoning` 严格用 `variants/defaultVariant` 键名。
- `options.apiKey` 与 `apiKeyRequired`：本地已有的值绝不覆盖；新建条目 `apiKey` 置空、`apiKeyRequired` 用 registry 值。
- 写入格式整体遵循主进程写回格式，合并由 agent 按上述规则用文件工具执行，第一版不写独立同步脚本（规则少，agent 可靠执行，且免掉订阅者的运行时依赖；若日后发现 agent 合并出错再补脚本）。

### 贴 key 流程

新建 provider 后，命令引导用户把 key 粘贴到对话里，agent 写入 `options.apiKey`（config.json 本来就是明文存 key，不降安全性）。不愿在对话里粘贴的用户可自行编辑文件，README 两种方式都写。

### 验证

1. 写入后 agent 立即重读 config.json，逐字段核对。
2. 提醒用户重启 ZCode（reasoning 类字段改动经重启完成规范化）。
3. 建议重启后再跑一次无参数命令，核对 reasoning 字段仍在（防启动规范化静默丢弃）。

## 维护流程

某家厂商改端点或出现新的坑：改 registry 对应条目与 notes → 两处 bump 版本号 → commit + push GitHub → 插件管理里更新该插件 → 新会话跑同步。与 humanize 插件的发布链一致。

## 已验证的事实依据（设计前提）

1. 插件可分发组件仅五种（commands/skills/hooks/mcpServers/agents），`settings` 等字段 recorded but not executed——配置分发只能靠命令驱动 agent 改文件，插件无直接入口（zcode-configuration-guide）。
2. provider 配置在 `~/.zcode/v2/config.json`，`apiKey` 明文、不支持环境变量注入（zcode-tools §3，grep zcode.cjs 无 env 解析路径）。
3. 模型条目 `reasoning` 必须为 `variants` 格式，否则启动规范化静默丢弃；无 `modified:true` 钉子的模型可能被自动剪枝（zcode-tools §2.5/§3）。
4. `apiKeyRequired` 是布尔值（本机 config.json 实测）。
5. UUID 跨机器可固定，agent 的 model 字段引用 `<uuid>/<model>`（zcode-tools §3）。
6. `${CLAUDE_PLUGIN_ROOT}`/`${ZCODE_PLUGIN_ROOT}` 在 zcode.cjs 的命令处理中有占位替换逻辑（含专门的报错分支），是正式机制。
7. 插件缓存多版本并存（humanize 0.2.1/0.2.2、browser-use 三版实测），加载始终指向最新版；`${CLAUDE_PLUGIN_ROOT}` 指向当前加载版本，旧目录无害不需清理，清理属客户端行为，本插件不涉及。

## 实现时需验证的点

1. `${CLAUDE_PLUGIN_ROOT}` 在命令正文运行时实际替换（冒烟：命令里 echo 该路径）。
2. 新建 provider 条目 `apiKey` 置空串时 ZCode 是否接受；若空串被规范化拒绝，改为省略该字段，贴 key 流程相应调整。
3. 首次真实同步后重启，核对 reasoning 字段保留（命令验证步骤的一部分）。

## 未来工作（不在本版）

- Google 官方端点条目：先实测官方端点 + reasoning 配置能否脱离网关过滤工作，可行再收录。
- council/swarm agent 定义打包（依赖 registry UUID 绑定）。
- SessionStart hook 版本变化提醒（若手动同步被证明不够）。
- 独立同步脚本（若 agent 合并出现漂移）。
