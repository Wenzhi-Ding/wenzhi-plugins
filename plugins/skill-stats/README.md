# skill-stats

统计每个技能（skill）被触发的次数，并区分触发来源：用户输入 `/技能名` 触发，还是 agent 主动选择调用。在会话里输入 `/skill-stats` 查看统计表。

## 原理

桌面端把用户输入的 `/mail 帮我…` 以原文提交给模型，模型再调用 `Skill` 工具加载技能。所以一次用户触发会先后产生两个可观测事件，插件各注册一个钩子：

| 钩子 | matcher | 作用 |
| --- | --- | --- |
| UserPromptSubmit | `^/|^Run custom command /|Use the skill named|<command-name>` | 解析技能名，写 pending 标记（按会话+技能名，含时间戳），并记录一条 `slash_prompt` 意向事件 |
| PreToolUse | `^Skill$` | 记录 `skill_call` 事件；同会话同名标记在 10 分钟内存在则消费标记、来源记 `user`，否则记 `agent` |

pending 标记让「用户输入 /X → agent 跟着调用 Skill(X)」只计一次且归为用户；agent 在任务中自行选择调用的技能则归为 agent。matcher 让普通消息和无关工具调用完全不触发脚本。以斜杠开头的 Unix 路径（如 `/home/...`）在解析阶段就被丢弃，不会进入统计。

## 存储

数据目录默认 `~/.zcode/skill-stats/`：

- `events.jsonl`：追加式事件日志，每行一条，字段为时间 `t`、会话 `session`、事件类型 `event`（`slash_prompt` 或 `skill_call`）、技能名 `skill`、来源 `source`（仅 skill_call）、参数 `args`（截断到 120 字符）。追加写入不做读改写，多个会话并行写不会损坏文件。
- `pending/`：待确认标记，过期自动清理。

## 配置（可选，环境变量）

- `SKILL_STATS_DIR`：数据目录，默认 `~/.zcode/skill-stats`。
- `SKILL_STATS_OFF_FILE`：开关文件路径，默认 `~/.zcode/skill-stats-off`。文件存在时完全不记录（每次触发重新检查，中途生效），不影响 `/skill-stats` 查看已有数据。
- `SKILL_STATS_PENDING_TTL`：pending 标记有效期（秒），默认 `600`。

## 依赖与可靠性

- 钩子依次尝试 `python3`、`python`、Windows Python Launcher 的 `py -3`，使用本机可用的 Python 3；不要求用户创建命令别名。
- 宿主把单行 JSON 写进 stdin 后不关管道，脚本用 `readline()` 读一行即返回，不依赖 EOF。
- 脚本任何异常都静默 exit 0，统计功能不阻塞会话；诊断写 stderr。

## 测试

```bash
python3 plugins/skill-stats/tests/test_skill_stats.py   # 单元测试（38 个用例）
python3 plugins/skill-stats/tests/smoke_test.py         # 冒烟测试（执行 hooks.json，覆盖解释器回退与 stdin 不关管道）
```

手动冒烟（模拟宿主调用）：

```bash
cd plugins/skill-stats
export SKILL_STATS_DIR=/tmp/skill-stats-test
echo '{"prompt":"/mail 帮我聚合","session_id":"sess_demo"}' | python3 hooks/skill_stats.py slash-prompt
echo '{"tool_input":{"skill":"mail","args":"帮我聚合"},"session_id":"sess_demo"}' | python3 hooks/skill_stats.py skill-call
echo '{"tool_input":{"skill":"sum-paper"},"session_id":"sess_demo"}' | python3 hooks/skill_stats.py skill-call
python3 hooks/skill_stats.py --report    # mail 应记 1 次用户触发，sum-paper 记 1 次 agent 触发
```
