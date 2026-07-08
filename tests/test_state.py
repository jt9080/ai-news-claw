import json
import tempfile
import unittest
from pathlib import Path

from newsclaw.models import Run, SeenRecord
from newsclaw.state import append_run, load_state, save_state


def make_record(source_id="42", value=200):
    return SeenRecord(
        source="hackernews", source_id=source_id, title="t", url="u",
        signal_name="points", signal_value=value, peak_signal=value,
        prior_value=value, velocity=0.0,
        first_seen="2026-07-07T00:00:00+00:00",
        last_seen="2026-07-08T00:00:00+00:00", reported_at=None,
    )


class TestLoadSave(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "state.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_is_a_clean_empty_start(self):
        records, status = load_state(self.path)
        self.assertEqual(records, {})
        self.assertEqual(status, "ok")

    def test_save_then_load_round_trips(self):
        records = {"hackernews:42": make_record("42", 200)}
        save_state(self.path, records)
        loaded, status = load_state(self.path)
        self.assertEqual(status, "ok")
        self.assertEqual(loaded["hackernews:42"], records["hackernews:42"])

    def test_corrupt_file_resets_to_empty(self):
        self.path.write_text("{not json at all}}}")
        records, status = load_state(self.path)
        self.assertEqual(records, {})
        self.assertEqual(status, "reset")

    def test_save_is_atomic_leaves_no_temp_file(self):
        save_state(self.path, {"hackernews:42": make_record()})
        siblings = list(self.path.parent.iterdir())
        self.assertEqual([p.name for p in siblings], ["state.json"])
        # and the file is valid json
        json.loads(self.path.read_text())


class TestAppendRun(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "runs.json"

    def tearDown(self):
        self.dir.cleanup()

    def make_run(self, run_at):
        return Run(
            run_at=run_at, window={"start": "a", "end": "b"},
            feeds={"hackernews": "ok", "github": "ok"},
            counts={"candidates": 1, "kept": 1, "new": 1,
                    "resurfaced": 0, "suppressed": 0, "published": 1},
            state="ok",
        )

    def test_append_creates_then_grows_the_log(self):
        append_run(self.path, self.make_run("2026-07-07T00:00:00+00:00"))
        append_run(self.path, self.make_run("2026-07-08T00:00:00+00:00"))
        log = json.loads(self.path.read_text())
        self.assertEqual(len(log), 2)
        self.assertEqual(log[0]["run_at"], "2026-07-07T00:00:00+00:00")
        self.assertEqual(log[1]["run_at"], "2026-07-08T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
