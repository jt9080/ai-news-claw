import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from newsclaw import judge
from newsclaw.models import Candidate, SeenRecord

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


def cand(source, sid, title="New agent framework", value=300, is_new=True,
         resurfaced=False, topics=None):
    c = Candidate(
        source=source, source_id=sid, title=title,
        url=f"https://example.com/{sid}",
        signal_name="points" if source == "hackernews" else "stars",
        signal_value=value, created_at=NOW - timedelta(hours=5),
        summary="a multi-agent thing", topics=topics or ["agent"],
    )
    c.is_new, c.resurfaced, c.velocity = is_new, resurfaced, 12.0
    return c


def mkitem(ids, **over):
    """A structurally-valid judged item; pass field=None to drop that field."""
    d = {"ids": ids, "title": "Story", "url": "https://example.com/1",
         "what": "what happened", "why": "why it matters",
         "for_builders": "builder takeaway", "kind": "repo",
         "topics": ["agent"], "resurfaced": False}
    d.update(over)
    return {k: v for k, v in d.items() if v is not None}


def reply(items):
    return json.dumps({"items": items})


class TestBuildMessages(unittest.TestCase):
    def test_user_payload_includes_ids_and_memory(self):
        c = cand("hackernews", "42", is_new=False)
        records = {"hackernews:42": SeenRecord(
            source="hackernews", source_id="42", title="t", url="u",
            signal_name="points", signal_value=300, peak_signal=280,
            prior_value=250, velocity=50.0, first_seen="x", last_seen="y",
            reported_at="2026-07-05T00:00:00+00:00")}
        system, user = judge.build_messages([c], records, NOW)
        self.assertIn("hn:42", user)
        self.assertIn("2026-07-05T00:00:00+00:00", user)
        self.assertIn("280", user)

    def test_system_prompt_asks_for_what_why_for_builders(self):
        system, _ = judge.build_messages([cand("hackernews", "1")], {}, NOW)
        low = system.lower()
        self.assertIn("what", low)
        self.assertIn("why", low)
        self.assertRegex(low, r"builder")


class TestJudge(unittest.TestCase):
    def test_maps_three_text_fields_in_order(self):
        cs = [cand("github", "acme/lib", "acme/lib"), cand("hackernews", "42")]
        resp = reply([
            mkitem(["hn:42"], title="Thread", what="devs discuss agents",
                   why="signals interest", for_builders="watch this pattern"),
            mkitem(["gh:acme/lib"], title="acme/lib", what="new framework",
                   why="fills a gap", for_builders="try it for orchestration"),
        ])
        with mock.patch("newsclaw.llm.complete", return_value=resp):
            items = judge.judge(cs, {}, NOW)
        self.assertEqual([i.title for i in items], ["Thread", "acme/lib"])
        self.assertEqual(items[0].what, "devs discuss agents")
        self.assertEqual(items[0].why, "signals interest")
        self.assertEqual(items[0].for_builders, "watch this pattern")

    def test_for_builders_is_optional(self):
        cs = [cand("hackernews", "42")]
        with mock.patch("newsclaw.llm.complete",
                        return_value=reply([mkitem(["hn:42"], for_builders=None)])):
            items = judge.judge(cs, {}, NOW)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].for_builders, "")

    def test_missing_what_is_dropped(self):
        cs = [cand("hackernews", "42")]
        with mock.patch("newsclaw.llm.complete",
                        return_value=reply([mkitem(["hn:42"], what=None)])):
            self.assertEqual(judge.judge(cs, {}, NOW), [])

    def test_missing_why_is_dropped(self):
        cs = [cand("hackernews", "42")]
        with mock.patch("newsclaw.llm.complete",
                        return_value=reply([mkitem(["hn:42"], why=None)])):
            self.assertEqual(judge.judge(cs, {}, NOW), [])

    def test_unknown_ids_are_dropped(self):
        cs = [cand("hackernews", "42")]
        resp = reply([
            mkitem(["gh:ghost"], title="gone"),
            mkitem(["hn:42", "gh:ghost"], title="keep"),
        ])
        with mock.patch("newsclaw.llm.complete", return_value=resp):
            items = judge.judge(cs, {}, NOW)
        self.assertEqual([i.title for i in items], ["keep"])
        self.assertEqual(len(items[0].sources), 1)

    def test_code_fenced_json_still_parses(self):
        cs = [cand("hackernews", "42")]
        fenced = "```json\n" + reply([mkitem(["hn:42"])]) + "\n```"
        with mock.patch("newsclaw.llm.complete", return_value=fenced):
            self.assertEqual(len(judge.judge(cs, {}, NOW)), 1)

    def test_malformed_json_raises_judge_unavailable(self):
        with mock.patch("newsclaw.llm.complete", return_value="not json at all"):
            with self.assertRaises(judge.JudgeUnavailable):
                judge.judge([cand("hackernews", "42")], {}, NOW)

    def test_items_not_a_list_raises_judge_unavailable(self):
        with mock.patch("newsclaw.llm.complete", return_value=json.dumps({"items": "nope"})):
            with self.assertRaises(judge.JudgeUnavailable):
                judge.judge([cand("hackernews", "42")], {}, NOW)

    def test_llm_error_becomes_judge_unavailable(self):
        from newsclaw.llm import LLMError
        with mock.patch("newsclaw.llm.complete", side_effect=LLMError("no key")):
            with self.assertRaises(judge.JudgeUnavailable):
                judge.judge([cand("hackernews", "42")], {}, NOW)

    def test_retries_once_on_llm_error_then_succeeds(self):
        from newsclaw.llm import LLMError
        cs = [cand("hackernews", "42")]
        with mock.patch("newsclaw.llm.complete",
                        side_effect=[LLMError("timeout"), reply([mkitem(["hn:42"])])]) as m:
            items = judge.judge(cs, {}, NOW)
        self.assertEqual(len(items), 1)
        self.assertEqual(m.call_count, 2)

    def test_no_candidates_returns_empty_without_calling_llm(self):
        with mock.patch("newsclaw.llm.complete") as m:
            self.assertEqual(judge.judge([], {}, NOW), [])
            m.assert_not_called()


if __name__ == "__main__":
    unittest.main()
