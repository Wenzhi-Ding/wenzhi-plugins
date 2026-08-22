# wenzhi-plugins

ZCode 插件市场。在 ZCode 的插件管理里添加本仓库即可一键安装下面的插件。

## 插件

### humanize

每次你发送消息时，humanize 通过 UserPromptSubmit hook 注入一段「说人话」要求，让模型回答时遵守：

1. 句子语法完整，不写残句，不用名词短语堆砌代替句子。
2. 不用隐喻描述论证或因果结构，不把多词说法压缩成读不懂的自造短词，改用直白说法。
3. 中文回答时非专业名词不用英文。
4. 不写翻译腔：短句、主动语态优先。
5. 不用空洞大词和夸张修饰（「赋能」「闭环」「底层逻辑」等）。
6. 避免 AI 套话（「值得注意的是」「总的来说」等）。
7. 不编造时间、疲劳、情绪场景来给停止或收尾找理由。
8. 讲概念、讲论文按前因后果组织，术语先用大白话讲清再挂名字。
9. 抽象论断配具体量级数字，给不出数字的定性评价删掉。
10. 用户提出自己的解释或质疑时，顺着对方的版本回应。
11. 用户自己用的比喻、术语、自造词照用，不因撞上禁令就回避或纠正。

规则范围限会话回复；起草产出物（论文、报告、对外邮件等）时按该文体自身的写作规范执行，不套会话规则。

适用场景：中文问答和写作时，抑制模型输出残句、翻译腔和 AI 套话。

### model-providers

各家模型厂商在 ZCode 里的正确配置（端点、协议 kind、reasoning 档位、参数怪癖）的结构化 registry。安装后跑 `/providers-sync`，本机 `~/.zcode/v2/config.json` 的 provider 配置就与验证过的经验对齐；API key 自己粘贴，仓库中永远不出现。

- `/providers-sync`：状态总览，不写入。
- `/providers-sync grok qwen`：按 name 或 alias 选择性同步。
- `/providers-sync all`：全部同步。

收录：Kimi、DeepSeek、B.AI、MiniMax、Grok、Qwen、OpenCode（Claude/GPT 两条目）。同步只动 `baseURL`、`kind`、`models`，不动你自己的 key 和自己加的模型。

## 安装

要求：

- ZCode
- 本机可运行 `bash`（macOS/Linux 自带；Windows 用 Git Bash，ZCode 在 Windows 本身依赖它）

步骤：

1. 打开 ZCode → 设置 → 插件管理 → 发现
2. 点 `+` 添加 GitHub 仓库：`Wenzhi-Ding/wenzhi-plugins`
3. 在列表中找到 humanize，点安装（默认启用，下个会话生效）

## 许可

[MIT](LICENSE)
