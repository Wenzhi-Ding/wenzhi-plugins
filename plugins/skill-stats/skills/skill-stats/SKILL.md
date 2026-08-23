---
name: skill-stats
description: 查看技能触发次数统计，区分用户输入 /技能名 触发与 agent 主动调用。Use when the user asks for skill usage statistics, trigger counts, 技能使用统计, or 各技能触发次数。
---

# 查看技能触发统计

向用户展示每个技能被触发的次数与来源构成。

## 步骤

1. 运行统计脚本（它读事件日志、打印 markdown 表格）：

   ```bash
   python "${CLAUDE_SKILL_DIR}/../../hooks/skill_stats.py" --report
   ```

   若 `${CLAUDE_SKILL_DIR}` 未展开成绝对路径：技能清单里标注了本 SKILL.md 的绝对路径，向上两级是插件根目录，脚本在插件根目录的 `hooks/skill_stats.py`。

2. 把输出的表格原样贴进回复。表格之后可以加一两句解读，比如哪个技能最常用、用户触发和 agent 主动调用哪个占多数；不要逐格复述数字。

3. 如果输出是「暂无技能触发记录」，告诉用户数据会随使用累积；如果用户以为早就在统计了，检查开关文件 `~/.zcode/skill-stats-off` 是否存在。

## 数据说明（用户追问细节时再讲）

- 事件日志在 `~/.zcode/skill-stats/events.jsonl`，每行一条事件：`slash_prompt` 是用户输入 `/技能名` 的意向记录，`skill_call` 是一次实际的 Skill 工具调用（含 source 字段区分 user/agent）。
- 判定逻辑：用户输入 `/X` 后 10 分钟内同会话出现 `Skill(X)` 调用，这次调用记为 user；其余 Skill 调用记为 agent。
- 表格末尾的「未跟进」区段列出用户输入了但 agent 没有发起对应调用的次数，多是 agent 先反问或会话中断导致。
