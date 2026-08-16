---
description: 把插件 registry 里验证过的模型厂商 provider 配置同步到本机 ~/.zcode/v2/config.json。
argument-hint: "[provider 名或 alias（空格分隔）；all 同步全部；无参数只看状态]"
---

把插件 registry 中的 provider 配置同步到本机 `~/.zcode/v2/config.json` 的 `provider` 对象。registry 文件位于 `${CLAUDE_PLUGIN_ROOT}/registry/registry.json`（路径中的占位符由 ZCode 运行时替换为插件安装目录）。如果读文件时发现路径里还有字面的 `${CLAUDE_PLUGIN_ROOT}`，说明占位符替换没有生效，直接向用户报告这个问题并停止，不要尝试猜测插件目录。

用户参数：$ARGUMENTS

## 参数语义

- 参数为空（上面的参数行没有内容）：只做状态总览，不写入任何东西。
- `all`：同步 registry 里的全部条目。
- 其他：按 name 或 alias 匹配（大小写不敏感），只同步命中的条目。有一个词匹配不到任何条目时，列出可选的 name/alias 让用户重新选择，不写入。

## 状态总览（无参数时）

读 registry 和 config.json，对每个 registry 条目输出一行状态：

- **本地没有**：可新增，标注「新增后需贴 key」。
- **两边有差异**：可更新，列出具体差异：baseURL、kind、registry 有而本地没有的模型、模型 reasoning 的 variants/defaultVariant 变化。本地有而 registry 没有的模型不算差异（见合并规则 3）。
- **一致**：无需操作。
- 仅本地存在而 registry 没有的 provider：不展示、不提示任何操作。

输出后问用户要同步哪些（可以回答名字，也可以直接说 all）。

## 匹配与合并规则（写入时严格遵守）

1. 匹配本地条目：先按 registry 的 uuid 匹配 config.json 的 provider 键，匹配不到再按 name（大小写不敏感）。命中已有条目则更新它；未命中则新建条目，键用 registry 的 uuid。
2. 更新已有条目时，绝不改动本地的：provider 键（UUID）、`options.apiKey` 的值、provider 级 `zcode` 字段（如 `deletedModels`）。
3. `baseURL`、`kind`、`models` 以 registry 为准；本地有而 registry 没有的模型条目原样保留，不删不改。
4. 写入的每个模型条目统一设 `"zcode": {"modified": true}`，防止 ZCode 自动剪枝。registry 数据本身不携带这个字段，由这次同步动作加；模型条目里已有的其他 `zcode` 子字段（如 `priority`）保留，只确保 `modified` 为 true。
5. `reasoning` 字段只能用 `variants` / `defaultVariant` 键名（写 `levels` 数组会被启动规范化静默丢弃），完全按 registry 的内容写。
6. 新建条目的结构对齐本地已有自定义 provider 的格式：`name`、`kind`、`options`（含 `apiKey`、`baseURL`、`apiKeyRequired`）、`source: "custom"`、`models`。`options.apiKey` 置空字符串；如果重启后发现空串被 ZCode 规范化拒绝，改为整个省略 `apiKey` 字段并提醒用户。
7. `apiKeyRequired` 用 registry 的值（布尔）。模型条目里的 `name` 覆盖字段（如 MiniMax 的 `MiniMax-M3`）按 registry 原样写入。
8. 用文件工具直接编辑 config.json，保持原有缩进和其余内容不动。

## 贴 key

新建 provider 后，引导用户两种方式任选：

1. 把该厂商的 API key 粘贴到对话里，你写入对应条目的 `options.apiKey`（config.json 本来就明文存 key，不降安全性）。key 的申请地址在该条目的 `apiKeyDoc` 字段里，展示给用户。
2. 用户自己编辑 `~/.zcode/v2/config.json` 填 key。

用户明确表示不在对话里粘贴就不再追问。

## 验证

写入完成后：

1. 立即重读 config.json，逐字段核对：baseURL、kind、每个写入模型的 reasoning（variants/defaultVariant）、limit、`zcode.modified` 钉子。有出入就修正后重读，直到一致。
2. 提醒用户重启 ZCode：reasoning 类字段的改动经重启完成规范化。
3. 建议重启后再跑一次无参数的 `/providers-sync`，确认 reasoning 字段仍在（防启动规范化静默丢弃）；如果丢了，把丢失情况报告给用户。

## 安全边界

config.json 里已有的任何 `apiKey` 值：不输出到对话、不写进任何其他文件、不放进任何日志。同步过程中需要展示差异时，只展示结构字段，不展示 key。
