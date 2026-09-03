#!/usr/bin/env python3
"""humanize hook 的回归测试。

运行：python plugins/humanize/tests/test_humanize.py
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parent.parent
SCRIPT = PLUGIN_DIR / "hooks" / "humanize.sh"
RULES = PLUGIN_DIR / "hooks" / "rules.txt"
OPEN_STDIN_PROBE = Path(__file__).resolve().parent / "open_stdin_probe.js"
DEFAULT_WINDOWS_BASH = Path(r"C:\Program Files\Git\usr\bin\bash.exe")
BASH = Path(
    os.environ.get("GIT_BASH")
    or (DEFAULT_WINDOWS_BASH if os.name == "nt" else shutil.which("bash") or "bash")
)


def bash_path(path):
    """把路径转成当前 Bash 可识别的形式。"""
    resolved = Path(path).resolve()
    if os.name != "nt":
        return str(resolved)
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix()[len(resolved.drive):].lstrip("/")
    return f"/{drive}/{tail}"


class HumanizeHookTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.state_dir = self.tmp / "state"
        self.off_file = self.tmp / "humanize-off"

    def tearDown(self):
        self._tmp.cleanup()

    def run_hook(self, *, session="sess_test", keep_stdin_open=False, extra_env=None):
        env = os.environ.copy()
        for name in tuple(env):
            if name.startswith("HUMANIZE_"):
                env.pop(name)
        env.update(
            {
                "ZCODE_SESSION_ID": session,
                "HUMANIZE_STATE_DIR": bash_path(self.state_dir),
                "HUMANIZE_OFF_FILE": bash_path(self.off_file),
            }
        )
        if extra_env:
            env.update(extra_env)
        if "HUMANIZE_RULES_FILE" in env:
            env["HUMANIZE_RULES_FILE"] = bash_path(env["HUMANIZE_RULES_FILE"])

        self.assertTrue(BASH.is_file(), f"找不到 Bash：{BASH}")
        command = [str(BASH), bash_path(SCRIPT)]
        stdin = subprocess.PIPE
        if keep_stdin_open:
            command = ["node", str(OPEN_STDIN_PROBE), str(BASH), bash_path(SCRIPT)]
            stdin = subprocess.DEVNULL
        proc = subprocess.Popen(
            command,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        started = time.monotonic()
        stdout, stderr = proc.communicate(timeout=8)

        elapsed = time.monotonic() - started
        self.assertEqual(proc.returncode, 0, stderr.decode("utf-8", errors="replace"))
        self.assertLess(elapsed, 5)
        text = stdout.decode("utf-8")
        return json.loads(text) if text else None

    @staticmethod
    def context(payload):
        return payload["hookSpecificOutput"]["additionalContext"]


class TestRuleRegression(HumanizeHookTestCase):
    def test_full_rules_cover_opaque_labels_and_source_metaphors(self):
        payload = self.run_hook()
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        context = self.context(payload)

        for phrase in (
            "行会共识",
            "学术共同体共同接受的标准",
            "拿掉上下文",
            "领域新人",
            "具体实例",
            "the channel is open",
            "渠道开着",
            "这条传导路径上确有活动",
            "引用原文并加以解释",
            "文献综述、会议纪要、讲义汇报",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, context)

    def test_full_rules_define_minimal_sufficient_answer_and_stop_condition(self):
        context = self.context(self.run_hook(session="sess_scope"))
        for phrase in (
            "最短充分答案",
            "核心问题答完就停",
            "删掉这一项会不会妨碍用户理解核心结论",
            "不把短问题自动升级成完整论文摘要",
            "复杂任务不套固定长度",
            "完整性优先",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, context)


class TestInjectionBehavior(HumanizeHookTestCase):
    def test_default_injects_full_rules_every_turn(self):
        contexts = [
            self.context(self.run_hook(session="sess_schedule"))
            for _ in range(5)
        ]
        for context in contexts:
            self.assertTrue(context.startswith("【说人话要求】"))

    def test_interval_env_knob_is_inert(self):
        for _ in range(3):
            context = self.context(
                self.run_hook(session="sess_every_gone", extra_env={"HUMANIZE_EVERY": "4"})
            )
            self.assertTrue(context.startswith("【说人话要求】"))

    def test_off_switch_suppresses_output(self):
        self.off_file.touch()
        self.assertIsNone(self.run_hook())

    def test_missing_rules_warning_appears_once_per_session(self):
        missing = str(self.tmp / "missing-rules.txt")
        first = self.run_hook(
            session="sess_missing", extra_env={"HUMANIZE_RULES_FILE": missing}
        )
        second = self.run_hook(
            session="sess_missing", extra_env={"HUMANIZE_RULES_FILE": missing}
        )
        self.assertIn("规则文件缺失或为空", first["systemMessage"])
        self.assertIsNone(second)

    def test_open_stdin_does_not_hang(self):
        payload = self.run_hook(session="sess_open_stdin", keep_stdin_open=True)
        self.assertTrue(self.context(payload).startswith("【说人话要求】"))

    def test_smoke_comment_current_and_no_interval_residue(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("bash hooks/humanize.sh                 # 每次运行都输出完整规则", source)
        self.assertNotIn("HUMANIZE_EVERY", source)
        self.assertNotIn("说人话要求·提醒", source)


class TestVersionRegistration(unittest.TestCase):
    def test_plugin_and_marketplace_versions_match(self):
        plugin = json.loads((PLUGIN_DIR / ".zcode-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((PLUGIN_DIR.parent.parent / "marketplace.json").read_text(encoding="utf-8"))
        entry = next(item for item in marketplace["plugins"] if item["name"] == "humanize")
        self.assertEqual(plugin["version"], "0.6.0")
        self.assertEqual(entry["version"], "0.6.0")

    def test_rules_file_is_not_empty(self):
        self.assertTrue(RULES.read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main(verbosity=2)
