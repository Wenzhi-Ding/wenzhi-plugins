#!/usr/bin/env python3
"""skill-stats 钩子脚本的单元测试。

运行（仓库根目录或插件目录均可）：
    python plugins/skill-stats/tests/test_skill_stats.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

import skill_stats as ss


class TestParseSlashName(unittest.TestCase):
    """从 prompt 文本识别用户触发的技能，宿主各端的提交形式都要认。"""

    def test_markdown_link_form(self):
        # 桌面端把 /mail 提交成指向 SKILL.md 的 Markdown 链接。
        prompt = "[$mail](/Users/x/.zcode/cli/plugins/cache/wenzhi-plugins/skill-stats/0.1.3/skills/mail/SKILL.md)"
        self.assertEqual(ss.parse_slash_name(prompt), ("mail", ""))

    def test_markdown_link_form_with_args(self):
        prompt = "[$mail](/root/skills/mail/SKILL.md) 帮我聚合邮件"
        self.assertEqual(ss.parse_slash_name(prompt), ("mail", "帮我聚合邮件"))

    def test_markdown_link_form_namespaced_skill(self):
        prompt = "[$browser-use:control-browser](/root/skills/control-browser/SKILL.md)"
        self.assertEqual(ss.parse_slash_name(prompt), ("browser-use:control-browser", ""))

    def test_markdown_link_form_relative_path(self):
        self.assertEqual(ss.parse_slash_name("[$reflect](skills/reflect/SKILL.md)"), ("reflect", ""))

    def test_markdown_link_form_builtin_command_ignored(self):
        self.assertIsNone(ss.parse_slash_name("[$help](/root/skills/help/SKILL.md)"))

    def test_markdown_link_to_non_skill_file_ignored(self):
        # 指向别的文件的普通链接不是技能触发。
        self.assertIsNone(ss.parse_slash_name("[$notes](/Users/x/docs/notes.md)"))

    def test_markdown_link_with_ordinary_link_text_ignored(self):
        # 链接文字没有 $ 前缀，是聊天里手写的普通链接。
        self.assertIsNone(ss.parse_slash_name("[mail](/root/skills/mail/SKILL.md)"))

    def test_plain_slash_with_args(self):
        self.assertEqual(ss.parse_slash_name("/mail 帮我聚合邮件"), ("mail", "帮我聚合邮件"))

    def test_plain_slash_without_args(self):
        self.assertEqual(ss.parse_slash_name("/mail"), ("mail", ""))

    def test_multiple_spaces_between_name_and_args(self):
        self.assertEqual(ss.parse_slash_name("/mail  帮我"), ("mail", "帮我"))

    def test_skill_command_form_takes_next_token_as_name(self):
        self.assertEqual(ss.parse_slash_name("/skill mail do X"), ("mail", "do X"))

    def test_skill_command_form_without_name(self):
        self.assertIsNone(ss.parse_slash_name("/skill"))

    def test_builtin_commands_are_not_skills(self):
        for name in ["compact", "help", "model", "new", "clear", "resume", "rewind",
                     "mode", "mcp", "plugins", "plugin", "goal", "target", "fork",
                     "init", "login", "logout", "locale", "expert", "effort",
                     "variant", "workflow", "workflows", "continue"]:
            with self.subTest(name=name):
                self.assertIsNone(ss.parse_slash_name(f"/{name} 一些参数"))

    def test_namespaced_plugin_skill(self):
        self.assertEqual(
            ss.parse_slash_name("/browser-use:control-browser"),
            ("browser-use:control-browser", ""),
        )

    def test_uppercase_name_is_normalized_to_lowercase(self):
        self.assertEqual(ss.parse_slash_name("/Mail 帮我"), ("mail", "帮我"))

    def test_non_slash_prompt(self):
        self.assertIsNone(ss.parse_slash_name("普通消息，不是命令"))

    def test_lone_slash(self):
        self.assertIsNone(ss.parse_slash_name("/"))

    def test_leading_whitespace_before_slash(self):
        self.assertEqual(ss.parse_slash_name("  /mail 帮我"), ("mail", "帮我"))

    def test_unix_path_is_not_a_skill_candidate(self):
        # 名字后面直接跟 / 的是路径而不是技能调用，解析阶段直接丢弃，
        # 不留 pending 标记、不写意向事件。
        self.assertIsNone(ss.parse_slash_name("/home/data/revelio 蠢死了"))

    def test_cli_custom_command_expansion(self):
        prompt = (
            "Run custom command /mail.\n"
            "Command source: user/project.\n"
            "\n"
            "命令正文第一行\n"
            "\n"
            "User arguments:\n"
            "帮我聚合邮件"
        )
        self.assertEqual(ss.parse_slash_name(prompt), ("mail", "帮我聚合邮件"))

    def test_cli_custom_command_expansion_without_args(self):
        prompt = "Run custom command /mail.\nCommand source: user/project.\n\n命令正文"
        self.assertEqual(ss.parse_slash_name(prompt), ("mail", ""))

    def test_cli_skill_instruction_form(self):
        prompt = (
            "Use the skill named `mail` for this turn.\n"
            "First call the `Skill` tool with name `mail` before doing the task.\n"
            "\n"
            "User request:\n"
            "帮我聚合邮件"
        )
        self.assertEqual(ss.parse_slash_name(prompt), ("mail", "帮我聚合邮件"))

    def test_command_name_tag_form(self):
        prompt = "<command-name>mail</command-name>\n帮我聚合邮件"
        self.assertEqual(ss.parse_slash_name(prompt), ("mail", "帮我聚合邮件"))


class TestTruncate(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(ss.truncate("短文本"), "短文本")

    def test_long_text_cut_with_ellipsis(self):
        out = ss.truncate("x" * 200)
        self.assertEqual(len(out), 120)
        self.assertTrue(out.endswith("..."))

    def test_exactly_120_unchanged(self):
        self.assertEqual(ss.truncate("x" * 120), "x" * 120)

    def test_none_and_empty(self):
        self.assertEqual(ss.truncate(None), "")
        self.assertEqual(ss.truncate(""), "")

    def test_newlines_collapsed(self):
        self.assertEqual(ss.truncate("a\nb\r\nc"), "a b c")


class SkillStatsTestCase(unittest.TestCase):
    """公共脚手架：每个测试一个临时数据目录。"""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def read_events(self):
        path = self.dir / "events.jsonl"
        if not path.exists():
            return []
        import json
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class TestClassifyCall(SkillStatsTestCase):
    """来源判定：pending 标记存在且新鲜记 user，否则记 agent。"""

    NOW = 1_800_000_000.0

    def make_marker(self, session, skill, t):
        ss.write_marker(self.dir / "pending", session, skill, t)

    def test_no_marker_is_agent(self):
        self.assertEqual(
            ss.classify_call(self.dir / "pending", "sess_a", "mail", self.NOW),
            "agent",
        )

    def test_fresh_marker_is_user_and_consumed(self):
        self.make_marker("sess_a", "mail", self.NOW - 5)
        self.assertEqual(
            ss.classify_call(self.dir / "pending", "sess_a", "mail", self.NOW),
            "user",
        )
        # 标记被消费：同名再次调用归 agent。
        self.assertEqual(
            ss.classify_call(self.dir / "pending", "sess_a", "mail", self.NOW),
            "agent",
        )

    def test_expired_marker_is_agent(self):
        self.make_marker("sess_a", "mail", self.NOW - 601)
        self.assertEqual(
            ss.classify_call(self.dir / "pending", "sess_a", "mail", self.NOW),
            "agent",
        )

    def test_marker_from_other_session_not_matched(self):
        self.make_marker("sess_b", "mail", self.NOW - 5)
        self.assertEqual(
            ss.classify_call(self.dir / "pending", "sess_a", "mail", self.NOW),
            "agent",
        )

    def test_marker_for_other_skill_not_matched(self):
        self.make_marker("sess_a", "sum-paper", self.NOW - 5)
        self.assertEqual(
            ss.classify_call(self.dir / "pending", "sess_a", "mail", self.NOW),
            "agent",
        )

    def test_alias_matches_namespaced_call(self):
        # 用户输入 /control-browser，agent 调 Skill("browser-use:control-browser")。
        self.make_marker("sess_a", "control-browser", self.NOW - 5)
        self.assertEqual(
            ss.classify_call(self.dir / "pending", "sess_a", "browser-use:control-browser", self.NOW),
            "user",
        )

    def test_namespaced_marker_matches_alias_call(self):
        self.make_marker("sess_a", "browser-use:control-browser", self.NOW - 5)
        self.assertEqual(
            ss.classify_call(self.dir / "pending", "sess_a", "control-browser", self.NOW),
            "user",
        )


class TestHandlers(SkillStatsTestCase):
    NOW = 1_800_000_000.0

    def test_slash_prompt_writes_marker_and_event(self):
        rec = ss.handle_slash_prompt(
            {"prompt": "/mail 帮我聚合", "session_id": "sess_a"}, self.dir, now=self.NOW
        )
        self.assertEqual(rec["event"], "slash_prompt")
        self.assertEqual(rec["skill"], "mail")
        self.assertEqual(rec["args"], "帮我聚合")
        self.assertEqual(rec["session"], "sess_a")
        events = self.read_events()
        self.assertEqual(len(events), 1)
        # pending 标记已写入，后续同名调用归 user。
        self.assertEqual(
            ss.classify_call(self.dir / "pending", "sess_a", "mail", self.NOW),
            "user",
        )

    def test_slash_prompt_ignores_non_skill_prompt(self):
        self.assertIsNone(
            ss.handle_slash_prompt({"prompt": "普通消息", "session_id": "sess_a"}, self.dir, now=self.NOW)
        )
        self.assertEqual(self.read_events(), [])

    def test_skill_call_after_user_slash_is_user(self):
        ss.handle_slash_prompt({"prompt": "/mail 帮我", "session_id": "sess_a"}, self.dir, now=self.NOW)
        rec = ss.handle_skill_call(
            {"tool_input": {"skill": "mail", "args": "帮我"}, "session_id": "sess_a"},
            self.dir, now=self.NOW + 3,
        )
        self.assertEqual(rec["source"], "user")
        self.assertEqual(rec["skill"], "mail")
        self.assertEqual(len(self.read_events()), 2)

    def test_skill_call_without_marker_is_agent(self):
        rec = ss.handle_skill_call(
            {"tool_input": {"skill": "sum-paper", "args": "某论文"}, "session_id": "sess_a"},
            self.dir, now=self.NOW,
        )
        self.assertEqual(rec["source"], "agent")

    def test_skill_call_missing_tool_input_writes_nothing(self):
        self.assertIsNone(ss.handle_skill_call({"session_id": "sess_a"}, self.dir, now=self.NOW))
        self.assertIsNone(
            ss.handle_skill_call({"tool_input": {}, "session_id": "sess_a"}, self.dir, now=self.NOW)
        )
        self.assertEqual(self.read_events(), [])

    def test_skill_call_args_truncated(self):
        rec = ss.handle_skill_call(
            {"tool_input": {"skill": "mail", "args": "长" * 200}, "session_id": "sess_a"},
            self.dir, now=self.NOW,
        )
        self.assertEqual(len(rec["args"]), 120)

    def test_stale_markers_cleaned_up(self):
        ss.write_marker(self.dir / "pending", "sess_old", "mail", self.NOW - 7000)
        ss.handle_skill_call(
            {"tool_input": {"skill": "sum-paper"}, "session_id": "sess_a"}, self.dir, now=self.NOW
        )
        remaining = list((self.dir / "pending").glob("*.json"))
        self.assertEqual(remaining, [])


class TestReport(SkillStatsTestCase):
    NOW = 1_800_000_000.0

    def test_empty_log(self):
        out = ss.report(self.dir)
        self.assertIn("暂无", out)

    def test_aggregation_and_sorting(self):
        ss.handle_slash_prompt({"prompt": "/mail 第一次", "session_id": "s1"}, self.dir, now=self.NOW)
        ss.handle_skill_call({"tool_input": {"skill": "mail"}, "session_id": "s1"}, self.dir, now=self.NOW + 1)
        ss.handle_skill_call({"tool_input": {"skill": "mail"}, "session_id": "s2"}, self.dir, now=self.NOW + 2)
        ss.handle_skill_call({"tool_input": {"skill": "sum-paper"}, "session_id": "s1"}, self.dir, now=self.NOW + 3)
        out = ss.report(self.dir)
        # mail：用户 1 + agent 1 = 2；sum-paper：agent 1。
        self.assertIn("| mail | 1 | 1 | 2 |", out)
        self.assertIn("| sum-paper | 0 | 1 | 1 |", out)
        # 按合计降序：mail 在 sum-paper 之前。
        self.assertLess(out.index("| mail |"), out.index("| sum-paper |"))
        # 总计行。
        self.assertIn("| 总计 | 1 | 2 | 3 |", out)

    def test_unmatched_intent_listed(self):
        # 用户输入了 /mail 但后续没有对应调用（如 agent 先反问、会话中断）。
        ss.handle_slash_prompt({"prompt": "/mail 帮我", "session_id": "s1"}, self.dir, now=self.NOW)
        out = ss.report(self.dir)
        self.assertIn("mail", out)
        self.assertIn("未跟进", out)

    def test_namespaced_names_share_one_row(self):
        # 用户输入 /skill-stats（原名），agent 调 Skill("skill-stats:skill-stats")：
        # 两行必须合并成一行，否则「未跟进」会把这条记成没跟上。
        ss.handle_slash_prompt(
            {"prompt": "[$skill-stats](/root/skills/skill-stats/SKILL.md)", "session_id": "s1"},
            self.dir, now=self.NOW,
        )
        ss.handle_skill_call(
            {"tool_input": {"skill": "skill-stats:skill-stats"}, "session_id": "s1"},
            self.dir, now=self.NOW + 1,
        )
        out = ss.report(self.dir)
        self.assertIn("| skill-stats | 1 | 0 | 1 |", out)
        self.assertNotIn("skill-stats:skill-stats", out)
        self.assertNotIn("未跟进", out)

    def test_markdown_link_intent_counts_as_user(self):
        ss.handle_slash_prompt(
            {"prompt": "[$reflect](/root/skills/reflect/SKILL.md)", "session_id": "s1"},
            self.dir, now=self.NOW,
        )
        rec = ss.handle_skill_call(
            {"tool_input": {"skill": "reflect"}, "session_id": "s1"},
            self.dir, now=self.NOW + 2,
        )
        self.assertEqual(rec["source"], "user")


if __name__ == "__main__":
    unittest.main(verbosity=2)
