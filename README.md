# wenzhi-plugins

ZCode 插件市场。在 ZCode 的插件管理里添加本仓库即可一键安装下面的插件。

## 插件

### humanize

humanize 通过 UserPromptSubmit hook 向会话注入一段「说人话」要求，让模型回答时遵守。注入按轮次进行：每个会话的第一轮注入完整规则，之后每隔 4 轮再全量注入一次，其余轮只注入一行简短提醒（完整规则留在会话历史里，提醒维持存在感）：

1. 句子语法完整，不写残句，不用名词短语堆砌代替句子。
2. 不用隐喻描述论证或因果结构，不把多词说法压缩成读不懂的自造短词，改用直白说法。判据：拿掉上下文，领域新人首次读到能否不查源就懂；不能就展开成完整说法，或首次出现时紧跟一个具体实例（文学化隐喻标签最容易漏，如把「学术共同体共同接受的标准」压成「行会共识」）。
3. 中文回答时非专业名词不用英文。
4. 不写翻译腔：短句、主动语态优先；英文习语和固定说法用通行译法，不逐字直译（rule of thumb 是「经验法则」，不是「拇指规则」）；转述外文材料时，源文本自带的隐喻不照字面搬进中文（the channel is open 不是「渠道开着」，要说「这条传导路径上确有活动」），拆成平白意义再表达。
5. 不用空洞大词和夸张修饰（「赋能」「闭环」「底层逻辑」等）。
6. 避免 AI 套话（「值得注意的是」「总的来说」等）。
7. 不编造时间、疲劳、情绪场景来给停止或收尾找理由。
8. 抽象论断配具体量级数字，给不出数字的定性评价删掉。
9. 用户提出自己的解释或质疑时，顺着对方的版本回应。
10. 用户自己用的比喻、术语、自造词照用，不因撞上禁令就回避或纠正。

规则范围覆盖会话回复和为用户起草的产出物（论文、报告、对外邮件等）；产出物同时遵守该文体自身的规范，文体的硬性规范（如期刊的语态惯例、模板的字数限制）与这些规则冲突时以文体规范为准。第 7、9 条只管会话回复。转述外文材料的总结（文献综述、会议纪要、讲义汇报）交付前另有一道自查：扫一遍直接来自源措辞的表达——直译的隐喻、压缩标签——逐个展开成平白说法或补上解释。研究相关的表达纪律（讲概念按前因后果、术语先白话后挂名）归 research-interpretation skill，不在本插件。

适用场景：中文问答和写作时，抑制模型输出残句、翻译腔和 AI 套话。

配置（可选，环境变量）：

- `HUMANIZE_EVERY`：隔几轮注入一次完整规则，默认 `4`；设为 `1` 恢复每轮完整注入。
- `HUMANIZE_OFF_FILE`：开关文件路径，默认 `~/.zcode/humanize-off`。文件存在时不注入，删除后恢复；每次发消息都会重新检查，会话中途即生效。
- `HUMANIZE_RULES_FILE`：规则文件路径，默认用插件自带的 `hooks/rules.txt`；想调整规则直接编辑这个文件即可。
- `HUMANIZE_DEBUG`：设为 `1` 时往 stderr 输出一行运行诊断（会话键、轮次、注入模式）。

回归测试（需要 Python 3、Node.js 和 Git Bash）：

```bash
python plugins/humanize/tests/test_humanize.py
```

测试会检查完整规则保留两个原始案例，短提醒保留对应的两项约束，并覆盖默认注入轮次、关闭开关、规则文件缺失提示，以及 stdin 保持打开时脚本不挂起。

### model-providers

各家模型厂商在 ZCode 里的正确配置（端点、协议 kind、reasoning 档位、参数怪癖）的结构化 registry。安装后跑 `/providers-sync`，本机 `~/.zcode/v2/config.json` 的 provider 配置就与验证过的经验对齐；API key 自己粘贴，仓库中永远不出现。

- `/providers-sync`：状态总览，不写入。
- `/providers-sync grok qwen`：按 name 或 alias 选择性同步。
- `/providers-sync all`：全部同步。

收录：Kimi、DeepSeek、B.AI、MiniMax、Grok、Qwen、OpenCode（Claude/GPT 两条目）。同步只动 `baseURL`、`kind`、`models`，不动你自己的 key 和自己加的模型。

### skill-stats

统计每个技能（skill）被触发的次数，并区分触发来源：你在输入框敲 `/技能名` 触发，还是 agent 在任务中主动选择调用。在会话里输入 `/skill-stats` 查看统计表。

原理：用户输入 `/mail …` 后 agent 会跟着调用 `Skill(mail)`，插件用 UserPromptSubmit 钩子记下输入、用 PreToolUse 钩子记下调用，按「同会话同名、10 分钟内」把两者关联成一次用户触发；没有对应输入的调用则记为 agent 主动调用。普通消息不触发钩子脚本（matcher 只放行以 `/` 开头的输入）。

数据存在 `~/.zcode/skill-stats/events.jsonl`（追加式日志，含时间、会话、技能名、来源、截断到 120 字符的参数），`~/.zcode/skill-stats-off` 文件存在时停止记录。详见插件目录下的 README。

## 安装

要求：

- ZCode
- 本机可运行 `bash`（macOS/Linux 自带；Windows 用 Git Bash，ZCode 在 Windows 本身依赖它）——humanize 需要
- 本机可运行 `python`（Python 3）——skill-stats 需要

步骤：

1. 打开 ZCode → 设置 → 插件管理 → 发现
2. 点 `+` 添加 GitHub 仓库：`Wenzhi-Ding/wenzhi-plugins`
3. 在列表中找到 humanize，点安装（默认启用，下个会话生效）

## 许可

[MIT](LICENSE)
