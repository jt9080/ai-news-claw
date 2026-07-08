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
        self.assertIn("2026-07-05T00:00:00+00:00", user)  # reported_at surfaced
        self.assertIn("280", user)                        # peak surfaced
        self.assertRegex(system.lower(), r"agent")        # policy names agent-dev


class TestJudge(unittest.TestCase):
    def test_maps_valid_response_to_digest_items_in_order(self):
        cs = [cand("github", "acme/lib", "acme/lib"), cand("hackernews", "42")]
        resp = reply([
            {"ids": ["hn:42"], "title": "Agent thread", "url": "https://example.com/42",
             "kind": "discussion", "topics": ["agent"], "why": "devs debate agents", "resurfaced": False},
            {"ids": ["gh:acme/lib"], "title": "acme/lib", "url": "https://example.com/acme/lib",
             "kind": "repo", "topics": ["multiagent"], "why": "new framework", "resurfaced": False},
        ])
        with mock.patch("newsclaw.llm.complete", return_value=resp):
            items = judge.judge(cs, {}, NOW)
        self.assertEqual([i.title for i in items], ["Agent thread", "acme/lib"])
        self.assertEqual(items[0].why, "devs debate agents")
        self.assertEqual(items[1].sources[0].source_id, "acme/lib")

    def test_unknown_ids_are_dropped(self):
        cs = [cand("hackernews", "42")]
        resp = reply([
            {"ids": ["gh:ghost"], "title": "x", "url": "u", "why": "w"},          # all unknown -> dropped
            {"ids": ["hn:42", "gh:ghost"], "title": "keep", "url": "u", "why": "w"},  # partial -> keep known
        ])
        with mock.patch("newsclaw.llm.complete", return_value=resp):
            items = judge.judge(cs, {}, NOW)
        self.assertEqual([i.title for i in items], ["keep"])
        self.assertEqual(len(items[0].sources), 1)

    def test_entry_missing_required_field_is_dropped(self):
        cs = [cand("hackernews", "42")]
        resp = reply([{"ids": ["hn:42"], "title": "no why here", "url": "u"}])  # missing why
        with mock.patch("newsclaw.llm.complete", return_value=resp):
            self.assertEqual(judge.judge(cs, {}, NOW), [])

    def test_code_fenced_json_still_parses(self):
        cs = [cand("hackernews", "42")]
        fenced = "```json\n" + reply([{"ids": ["hn:42"], "title": "t", "url": "u", "why": "w"}]) + "\n```"
        with mock.patch("newsclaw.llm.complete", return_value=fenced):
            items = judge.judge(cs, {}, NOW)
        self.assertEqual(len(items), 1)

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
        good = reply([{"ids": ["hn:42"], "title": "t", "url": "u", "why": "w"}])
        with mock.patch("newsclaw.llm.complete",
                        side_effect=[LLMError("timeout"), good]) as m:
            items = judge.judge(cs, {}, NOW)
        self.assertEqual(len(items), 1)
        self.assertEqual(m.call_count, 2)

    def test_no_candidates_returns_empty_without_calling_llm(self):
        with mock.patch("newsclaw.llm.complete") as m:
            self.assertEqual(judge.judge([], {}, NOW), [])
            m.assert_not_called()


if __name__ == "__main__":
    unittest.main()
