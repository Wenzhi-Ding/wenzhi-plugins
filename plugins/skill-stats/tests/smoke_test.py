#!/usr/bin/env python3
"""skill-stats 钩子脚本的冒烟测试：用子进程模拟宿主的调用方式。

覆盖单元测试管不到的三件事：
1. 端到端流程：slash-prompt → skill-call 关联为 user，无输入跟进的调用记 agent，--report 出表。
2. stdin 保持打开不挂起（zcode-tools 4.5：宿主写完单行 JSON 不关管道，
   脚本必须靠 readline 拿一行就走，不能等 EOF）。
3. 开关文件存在时两个事件都不记录。

运行：python plugins/skill-stats/tests/smoke_test.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "hooks" / "skill_stats.py"


def run_hook(mode, payload, data_dir, keep_stdin_open=False, extra_env=None):
    """以宿主的姿势调钩子：单行 JSON 写进 stdin；keep_stdin_open=True 时不关管道。"""
    env = os.environ.copy()
    env["SKILL_STATS_DIR"] = str(data_dir)
    env.pop("SKILL_STATS_OFF_FILE", None)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT), mode],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    started = time.monotonic()
    proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    proc.stdin.flush()
    if keep_stdin_open:
        # 不关 stdin，直接等退出——挂起则 wait 超时，判失败。
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise AssertionError(f"{mode} 在 stdin 保持打开时挂起（等 EOF 的典型症状）")
        out, err = proc.stdout.read(), proc.stderr.read()
    else:
        out, err = proc.communicate(timeout=8)
    elapsed = time.monotonic() - started
    assert proc.returncode == 0, f"{mode} 退出码 {proc.returncode}，stderr：{err!r}"
    assert elapsed < 5, f"{mode} 耗时 {elapsed:.1f}s，超出预期"
    return out


def run_report(data_dir):
    env = os.environ.copy()
    env["SKILL_STATS_DIR"] = str(data_dir)
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--report"],
        capture_output=True, env=env, timeout=8,
    )
    assert out.returncode == 0
    return out.stdout.decode("utf-8")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)

        # 1. stdin 保持打开的端到端流程（与宿主行为一致）。
        run_hook("slash-prompt",
                 {"prompt": "/mail 帮我聚合邮件", "session_id": "sess_smoke"},
                 data_dir, keep_stdin_open=True)
        run_hook("skill-call",
                 {"tool_input": {"skill": "mail", "args": "帮我聚合邮件"}, "session_id": "sess_smoke"},
                 data_dir, keep_stdin_open=True)
        run_hook("skill-call",
                 {"tool_input": {"skill": "sum-paper"}, "session_id": "sess_smoke"},
                 data_dir, keep_stdin_open=True)

        events = [json.loads(x) for x in
                  (data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        kinds = [(e["event"], e.get("source")) for e in events]
        assert kinds == [("slash_prompt", None), ("skill_call", "user"), ("skill_call", "agent")], kinds

        table = run_report(data_dir)
        assert "| mail | 1 | 0 | 1 |" in table, table
        assert "| sum-paper | 0 | 1 | 1 |" in table, table
        print("1. 端到端流程（stdin 保持打开）：通过")

        # 2. 开关文件存在时不记录。
        off = Path(tmp) / "off"
        off.touch()
        before = len(events)
        run_hook("slash-prompt", {"prompt": "/mail 再来一次", "session_id": "sess_smoke"},
                 data_dir, extra_env={"SKILL_STATS_OFF_FILE": str(off)})
        run_hook("skill-call", {"tool_input": {"skill": "mail"}, "session_id": "sess_smoke"},
                 data_dir, extra_env={"SKILL_STATS_OFF_FILE": str(off)})
        after = len((data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
        assert after == before, "开关文件存在时仍写入了事件"
        # 查看统计不受开关影响。
        assert "| mail |" in run_report(data_dir)
        print("2. 开关文件：通过")

        # 3. 非技能输入与坏载荷不产出事件、不报错。
        run_hook("slash-prompt", {"prompt": "普通消息", "session_id": "s"}, data_dir)
        run_hook("slash-prompt", {"prompt": "/compact", "session_id": "s"}, data_dir)
        run_hook("skill-call", {"session_id": "s"}, data_dir)
        after = len((data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
        assert after == before, "非技能输入或坏载荷产出了事件"
        print("3. 非技能输入与坏载荷：通过")

    print("冒烟测试全部通过。")


if __name__ == "__main__":
    main()
