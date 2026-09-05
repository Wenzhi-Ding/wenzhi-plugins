#!/usr/bin/env python3
"""skill-stats 钩子的端到端冒烟测试。"""
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PLUGIN_ROOT / "hooks" / "skill_stats.py"
HOOKS_FILE = PLUGIN_ROOT / "hooks" / "hooks.json"


def clean_env(data_dir, extra_env=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SKILL_STATS_")}
    env["SKILL_STATS_DIR"] = str(data_dir)
    if extra_env:
        env.update(extra_env)
    return env


def hook_command(event_name):
    config = json.loads(HOOKS_FILE.read_text(encoding="utf-8"))
    command = config["hooks"][event_name][0]["hooks"][0]["command"]
    return command.replace("${ZCODE_PLUGIN_ROOT}", str(PLUGIN_ROOT))


def run_command(command, payload, env, keep_stdin_open=False, expected_code=0):
    proc = subprocess.Popen(
        command,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    started = time.monotonic()
    proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    proc.stdin.flush()
    if keep_stdin_open:
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise AssertionError("钩子在 stdin 保持打开时挂起")
        out, err = proc.stdout.read(), proc.stderr.read()
    else:
        out, err = proc.communicate(timeout=8)
    elapsed = time.monotonic() - started
    assert proc.returncode == expected_code, f"退出码 {proc.returncode}，stderr：{err!r}"
    assert elapsed < 5, f"耗时 {elapsed:.1f}s，超出预期"
    return out


def run_hook(mode, payload, data_dir, keep_stdin_open=False, extra_env=None):
    event = "UserPromptSubmit" if mode == "slash-prompt" else "PreToolUse"
    return run_command(
        hook_command(event),
        payload,
        clean_env(data_dir, extra_env),
        keep_stdin_open,
    )


def run_report(data_dir):
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--report"],
        capture_output=True,
        env=clean_env(data_dir),
        timeout=8,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.decode("utf-8")


def make_python_shim(directory, name):
    path = directory / name
    shift_launcher_arg = '[ "$1" = "-3" ] && shift\n' if name == "py" else ""
    path.write_text(
        f"#!/bin/sh\n{shift_launcher_arg}exec {shlex.quote(sys.executable)} \"$@\"\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_dir = root / "data"

        run_hook(
            "slash-prompt",
            {"prompt": "/mail 帮我聚合邮件", "session_id": "sess_smoke"},
            data_dir,
            keep_stdin_open=True,
        )
        run_hook(
            "skill-call",
            {"tool_input": {"skill": "mail", "args": "帮我聚合邮件"}, "session_id": "sess_smoke"},
            data_dir,
            keep_stdin_open=True,
        )
        run_hook(
            "skill-call",
            {"tool_input": {"skill": "sum-paper"}, "session_id": "sess_smoke"},
            data_dir,
            keep_stdin_open=True,
        )

        events = [
            json.loads(line)
            for line in (data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        kinds = [(event["event"], event.get("source")) for event in events]
        assert kinds == [
            ("slash_prompt", None),
            ("skill_call", "user"),
            ("skill_call", "agent"),
        ], kinds
        table = run_report(data_dir)
        assert "| mail | 1 | 0 | 1 |" in table, table
        assert "| sum-paper | 0 | 1 | 1 |" in table, table
        print("1. hooks.json 端到端流程（stdin 保持打开）：通过")

        off = root / "off"
        off.touch()
        before = len(events)
        disabled_env = {"SKILL_STATS_OFF_FILE": str(off)}
        run_hook(
            "slash-prompt",
            {"prompt": "/mail 再来一次", "session_id": "sess_smoke"},
            data_dir,
            extra_env=disabled_env,
        )
        run_hook(
            "skill-call",
            {"tool_input": {"skill": "mail"}, "session_id": "sess_smoke"},
            data_dir,
            extra_env=disabled_env,
        )
        after = len((data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
        assert after == before, "开关文件存在时仍写入了事件"
        assert "| mail |" in run_report(data_dir)
        print("2. 开关文件：通过")

        run_hook("slash-prompt", {"prompt": "普通消息", "session_id": "s"}, data_dir)
        run_hook("slash-prompt", {"prompt": "/compact", "session_id": "s"}, data_dir)
        run_hook("skill-call", {"session_id": "s"}, data_dir)
        after = len((data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
        assert after == before, "非技能输入或坏载荷产出了事件"
        print("3. 非技能输入与坏载荷：通过")

        commands = [hook_command("UserPromptSubmit"), hook_command("PreToolUse")]
        assert all("python3" in command and "python " in command and "py -3" in command for command in commands)
        print("4. 解释器回退配置：通过")

        for command_name in ("python", "py"):
            bin_dir = root / f"bin-{command_name}"
            bin_dir.mkdir()
            make_python_shim(bin_dir, command_name)
            fallback_data = root / f"data-{command_name}"
            env = {"PATH": str(bin_dir)}
            run_hook(
                "skill-call",
                {"tool_input": {"skill": command_name}, "session_id": "fallback"},
                fallback_data,
                extra_env=env,
            )
            recorded = (fallback_data / "events.jsonl").read_text(encoding="utf-8")
            assert f'"skill": "{command_name}"' in recorded
        print("5. python 与 py -3 回退路径：通过")

        missing_bin = root / "bin-missing"
        missing_bin.mkdir()
        missing_data = root / "data-missing"
        run_command(
            hook_command("PreToolUse"),
            {"tool_input": {"skill": "missing"}, "session_id": "fallback"},
            clean_env(missing_data, {"PATH": str(missing_bin)}),
            expected_code=127,
        )
        assert not (missing_data / "events.jsonl").exists()
        print("6. 全部解释器缺失时明确失败且不写事件：通过")

    print("冒烟测试全部通过。")


if __name__ == "__main__":
    main()
