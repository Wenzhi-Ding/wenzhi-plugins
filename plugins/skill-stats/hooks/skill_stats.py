#!/usr/bin/env python3
"""skill-stats 插件的钩子脚本：记录技能触发次数并区分来源。

两类事件（hooks.json 里各注册一个钩子，均调用本脚本）：

- ``slash-prompt``：UserPromptSubmit。宿主提交用户输入时，这里从 prompt 解析技能名，
  写下 pending 标记（按会话+技能名，含时间戳），并往事件日志追加一条 slash_prompt 意向记录。
- ``skill-call``：PreToolUse（matcher 为 Skill）。读取 tool_input.skill，
  查同会话同名 pending 标记：有新鲜标记则消费掉、来源记 user，否则记 agent，
  然后追加一条 skill_call 事件。

这样用户输入 /X 后 agent 跟着调用 Skill(X) 的固定流程只计一次且归为用户；
agent 自行选择调用的 Skill 则归为 agent。

另提供 ``--report`` 读取事件日志并打印统计表（/skill-stats 技能用它展示）。

协议注意：宿主把单行 JSON 写进 stdin 后不关管道，这里用 readline 读一行即返回，
不依赖 EOF（zcode-tools 4.5）。任何异常都静默 exit 0，统计功能不阻塞会话。
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# ZCode 客户端拦截的内置斜杠命令（zcode.cjs 的 fie 函数）。它们不是技能，不计入。
BUILTIN_COMMANDS = frozenset({
    "compact", "expert", "effort", "variant", "workflow", "workflows", "fork",
    "help", "init", "login", "logout", "locale", "resume", "continue", "new",
    "clear", "rewind", "mode", "mcp", "plugins", "plugin", "model", "goal",
    "target",
})

# 原始形式：/mail 参数。名字字符集排除空白和 /（名字后直接跟 / 的是路径，整体不匹配）。
_RAW_SLASH_RE = re.compile(r"^\s*/([^\s/]+)(?:\s+(.*))?$", re.DOTALL)
# CLI 自定义命令展开形式：「Run custom command /mail.」开头，用户参数在 User arguments: 块。
_CUSTOM_COMMAND_RE = re.compile(r"^Run custom command /([\w:.-]+)\.")
_CUSTOM_ARGS_RE = re.compile(r"(?:^|\n)User arguments:\n(.*)$", re.DOTALL)
# CLI /skill 指令形式：「Use the skill named `mail` for this turn.」，参数在 User request: 块。
_SKILL_INSTRUCTION_RE = re.compile(r"Use the skill named `([\w:.-]+)`")
_SKILL_REQUEST_RE = re.compile(r"(?:^|\n)User request:\n(.*)$", re.DOTALL)
# 带 <command-name> 标签的形式（部分客户端把技能内容连同标签一起塞进 prompt）。
_COMMAND_TAG_RE = re.compile(r"<command-name>([\w:.-]+)</command-name>(.*)$", re.DOTALL)
# 桌面端（GUI）形式：用户输入 /mail 后宿主提交的是指向 SKILL.md 的 Markdown 链接，
# 形如「[$mail](/path/to/skills/mail/SKILL.md)」，链接文字带 $ 前缀，参数跟在链接之后。
# 目标路径必须以 SKILL.md 收尾，避免把普通的 [$词](链接) 误判成技能触发。
_MD_LINK_RE = re.compile(
    r"^\s*\[\$([\w:.-]+)\]\(([^)\s]*/)?SKILL\.md\)(?:\s+(.*))?$", re.DOTALL
)


def truncate(text, limit=120):
    """压平空白（含换行）后截断到 limit 字符，超长以 ... 收尾。None 按空串处理。"""
    if not text:
        return ""
    flat = " ".join(str(text).split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 3] + "..."


def _split_name_args(text):
    """把「名字 参数」拆成 (名字小写, 参数)；拆不出名字返回 None。"""
    m = re.match(r"^([^\s/]+)(?:\s+(.*))?$", text.strip(), re.DOTALL)
    if not m:
        return None
    return m.group(1).lower(), truncate(m.group(2) or "")


def parse_slash_name(prompt):
    """从 UserPromptSubmit 的 prompt 文本识别用户触发的技能，返回 (技能名, 参数) 或 None。

    覆盖五种形式：桌面端 Markdown 链接、桌面端/CLI 原文 /mail 参数、CLI 自定义命令展开、
    CLI /skill 指令、<command-name> 标签。内置命令与 Unix 路径返回 None。
    """
    if not prompt:
        return None

    m = _MD_LINK_RE.match(prompt)
    if m:
        name = m.group(1).lower()
        if name in BUILTIN_COMMANDS:
            return None
        return name, truncate(m.group(3) or "")

    m = _RAW_SLASH_RE.match(prompt)
    if m:
        name = m.group(1).lower()
        args = truncate(m.group(2) or "")
        if name == "skill":
            # /skill <名字> <任务>：真正的技能名是下一个词。
            return _split_name_args(args)
        if name in BUILTIN_COMMANDS:
            return None
        return name, args

    m = _CUSTOM_COMMAND_RE.match(prompt.strip())
    if m:
        am = _CUSTOM_ARGS_RE.search(prompt)
        return m.group(1).lower(), truncate(am.group(1) if am else "")

    m = _SKILL_INSTRUCTION_RE.search(prompt)
    if m:
        rm = _SKILL_REQUEST_RE.search(prompt)
        return m.group(1).lower(), truncate(rm.group(1) if rm else "")

    m = _COMMAND_TAG_RE.search(prompt)
    if m:
        return m.group(1).lower(), truncate(m.group(2))

    return None


# ---- 存储与来源判定 ---------------------------------------------------------

DEFAULT_DATA_DIR = Path.home() / ".zcode" / "skill-stats"
DEFAULT_OFF_FILE = Path.home() / ".zcode" / "skill-stats-off"
# 用户输入 /X 到 agent 调用 Skill(X) 之间允许的最大间隔，超过就不再把这次调用归给用户。
PENDING_TTL = int(os.environ.get("SKILL_STATS_PENDING_TTL", "600"))


def _safe(name):
    """文件名安全化：会话标识与技能名只留字母数字和 . _ -。"""
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(name)) or "unknown"


def _bare(name):
    """去掉插件命名空间前缀：browser-use:control-browser 与别名 control-browser 视为同名。"""
    return str(name).split(":")[-1].lower()


def _iso(now):
    return datetime.fromtimestamp(now).astimezone().isoformat(timespec="seconds")


def _marker_path(pending_dir, session, skill):
    return pending_dir / f"{_safe(session)}--{_safe(_bare(skill))}.json"


def write_marker(pending_dir, session, skill, t):
    pending_dir.mkdir(parents=True, exist_ok=True)
    _marker_path(pending_dir, session, skill).write_text(
        json.dumps({"t": t, "skill": skill}), encoding="utf-8"
    )


def classify_call(pending_dir, session, skill, now, ttl=PENDING_TTL):
    """判定一次 Skill 调用的来源：同名 pending 标记新鲜则消费并记 user，否则记 agent。"""
    marker = _marker_path(pending_dir, session, skill)
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        fresh = (now - float(data.get("t", 0))) <= ttl
    except (OSError, ValueError):
        fresh = False
    if fresh:
        marker.unlink(missing_ok=True)
        return "user"
    return "agent"


def _cleanup_pending(pending_dir, now, ttl=PENDING_TTL):
    if not pending_dir.is_dir():
        return
    for f in pending_dir.glob("*.json"):
        try:
            t = float(json.loads(f.read_text(encoding="utf-8")).get("t", 0))
        except (OSError, ValueError):
            t = 0
        if now - t > ttl:
            f.unlink(missing_ok=True)


def append_event(data_dir, record):
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(data_dir / "events.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _session_of(payload):
    return str(
        payload.get("session_id") or os.environ.get("ZCODE_SESSION_ID") or "shared"
    )


def handle_slash_prompt(payload, data_dir, now=None):
    """UserPromptSubmit 侧：识别 /技能名，写 pending 标记并记录 slash_prompt 事件。"""
    now = time.time() if now is None else now
    parsed = parse_slash_name(payload.get("prompt") or "")
    if not parsed:
        return None
    name, args = parsed
    session = _session_of(payload)
    pending_dir = data_dir / "pending"
    write_marker(pending_dir, session, name, now)
    rec = {
        "t": _iso(now),
        "event": "slash_prompt",
        "session": session,
        "skill": name,
        "args": args,
    }
    append_event(data_dir, rec)
    _cleanup_pending(pending_dir, now)
    return rec


def handle_skill_call(payload, data_dir, now=None):
    """PreToolUse 侧：记录 Skill 调用，按 pending 标记判定来源。"""
    now = time.time() if now is None else now
    tool_input = payload.get("tool_input") or {}
    name = str(tool_input.get("skill") or "").strip().lower()
    if not name:
        return None
    session = _session_of(payload)
    pending_dir = data_dir / "pending"
    source = classify_call(pending_dir, session, name, now)
    rec = {
        "t": _iso(now),
        "event": "skill_call",
        "session": session,
        "skill": name,
        "source": source,
        "args": truncate(tool_input.get("args")),
    }
    append_event(data_dir, rec)
    _cleanup_pending(pending_dir, now)
    return rec


# ---- 统计报表 ---------------------------------------------------------------


def report(data_dir):
    path = data_dir / "events.jsonl"
    events = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except ValueError:
                continue

    calls = {}   # 技能 -> {"user": n, "agent": n, "last": 时间串}
    intents = {}  # 技能 -> 用户斜杠输入次数
    for e in events:
        skill = e.get("skill")
        if not skill:
            continue
        # 按裸名归并：用户输入 /X 记的是原名，Skill 调用记的可能是插件命名空间名
        # （browser-use:control-browser），不归并会让同一技能拆成两行。
        key = _bare(skill)
        if e.get("event") == "skill_call":
            slot = calls.setdefault(key, {"user": 0, "agent": 0, "last": ""})
            slot["user" if e.get("source") == "user" else "agent"] += 1
            slot["last"] = max(slot["last"], e.get("t") or "")
        elif e.get("event") == "slash_prompt":
            intents[key] = intents.get(key, 0) + 1

    if not calls and not intents:
        return "暂无技能触发记录。"

    lines = [
        "## 技能触发统计",
        "",
        "| 技能 | 用户触发 | agent 触发 | 合计 | 最近触发 |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    tot_user = tot_agent = 0
    for skill, slot in sorted(calls.items(), key=lambda kv: (-(kv[1]["user"] + kv[1]["agent"]), kv[0])):
        u, a = slot["user"], slot["agent"]
        tot_user += u
        tot_agent += a
        last = slot["last"][:16].replace("T", " ")
        lines.append(f"| {skill} | {u} | {a} | {u + a} | {last} |")
    lines.append(f"| 总计 | {tot_user} | {tot_agent} | {tot_user + tot_agent} |  |")

    # 用户输入了 /X 但没有同名 user 调用跟进的次数，用于发现「输入了却没触发」的情况。
    unmatched = {
        k: intents.get(k, 0) - calls.get(k, {}).get("user", 0)
        for k in intents
        if intents.get(k, 0) - calls.get(k, {}).get("user", 0) > 0
    }
    if unmatched:
        lines += ["", "用户输入后 agent 未跟进调用的次数："]
        for skill, n in sorted(unmatched.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"- {skill}：{n} 次")
    return "\n".join(lines)


# ---- 入口 -------------------------------------------------------------------


def main(argv):
    data_dir = Path(os.environ.get("SKILL_STATS_DIR", str(DEFAULT_DATA_DIR)))
    if "--report" in argv:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(report(data_dir))
        return 0

    off_file = Path(os.environ.get("SKILL_STATS_OFF_FILE", str(DEFAULT_OFF_FILE)))
    if off_file.exists():
        return 0

    mode = argv[1] if len(argv) > 1 else ""
    if mode not in ("slash-prompt", "skill-call"):
        return 0

    # 宿主把单行 JSON 写进 stdin 后保持管道打开：readline 拿到换行就返回，不等 EOF。
    line = sys.stdin.readline()
    if not line.strip():
        return 0
    payload = json.loads(line)
    if mode == "slash-prompt":
        handle_slash_prompt(payload, data_dir)
    else:
        handle_skill_call(payload, data_dir)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:  # 统计功能永不阻塞会话：任何异常都静默放行。
        print(f"skill-stats: {exc}", file=sys.stderr)
        sys.exit(0)
