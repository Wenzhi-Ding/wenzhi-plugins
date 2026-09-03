# wenzhi-plugins

ZCode 插件市场。在 ZCode 的插件管理里添加本仓库即可一键安装下面的插件。

## 插件

### humanize

humanize 通过 UserPromptSubmit hook 在每条用户消息后注入一段「说人话」要求，让模型回答时遵守：

1. 句子语法完整，不写残句，不用名词短语堆砌代替句子。
2. 因果与论证直说谁影响谁、什么支持什么，不拿比喻或具体形象充当逻辑连接；不自造读者还原不出原意的压缩说法。
3. 中文表达里非专业名词不用英文；外文名词按意思选最恰当的译法，不逐字直译；按语言自身的语序和习惯行文，不写翻译腔。
4. 不用空洞的大词和夸张修饰，用具体事实代替评价。
5. 在保证信息充分的前提下尽可能简洁。

规则范围覆盖中英文的会话回复和为用户起草的产出物（论文、报告、对外邮件等）；产出物同时遵守该文体自身的规范，文体的硬性规范（如期刊的语态惯例、模板的字数限制）与这些规则冲突时以文体规范为准。规则只给普适原则，不带场景化条款和错/对示例——需要完整示例版（约 2000 字）见 git 标签 `humanize-v0.6.0`。研究相关的表达纪律（讲概念按前因后果、术语先白话后挂名）归 research-interpretation skill，不在本插件。

适用场景：中英文问答和写作时，抑制模型输出残句、翻译腔和空洞大词。

配置（可选，环境变量）：

- `HUMANIZE_OFF_FILE`：开关文件路径，默认 `~/.zcode/humanize-off`。文件存在时不注入，删除后恢复；每次发消息都会重新检查，会话中途即生效。
- `HUMANIZE_RULES_FILE`：规则文件路径，默认用插件自带的 `hooks/rules.txt`；想调整规则直接编辑这个文件即可。

回归测试（需要 Python 3、Node.js 和 Git Bash）：

```bash
python plugins/humanize/tests/test_humanize.py
```

测试会检查完整规则保留原始语言案例和回答范围门槛，并覆盖每轮全量注入、外部残留的 `HUMANIZE_EVERY` 不改变行为、关闭开关、规则文件缺失提示，以及 stdin 保持打开时脚本不挂起。

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
