import io
import json
import unittest
from unittest import mock
from urllib.error import HTTPError

from newsclaw import llm


def fake_completion(content):
    return io.BytesIO(json.dumps(
        {"choices": [{"message": {"role": "assistant", "content": content}}]}
    ).encode("utf-8"))


class TestComplete(unittest.TestCase):
    def test_missing_key_raises_llmerror(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(llm.LLMError):
                llm.complete("sys", "user")

    def test_successful_call_returns_content(self):
        with mock.patch.dict("os.environ", {"OPENCODE_API_KEY": "sk-x"}, clear=True):
            with mock.patch("newsclaw.llm.urlopen") as m:
                m.return_value.__enter__.return_value = fake_completion("hello judge")
                out = llm.complete("sys", "user")
        self.assertEqual(out, "hello judge")

    def test_request_carries_model_key_and_messages(self):
        captured = {}

        def spy(req, timeout=None):
            captured["url"] = req.full_url
            captured["auth"] = req.get_header("Authorization")
            captured["body"] = json.loads(req.data.decode("utf-8"))
            cm = mock.MagicMock()
            cm.__enter__.return_value = fake_completion("ok")
            return cm

        env = {"OPENCODE_API_KEY": "sk-x", "LLM_MODEL": "gpt-5.4-mini"}
        with mock.patch.dict("os.environ", env, clear=True):
            with mock.patch("newsclaw.llm.urlopen", side_effect=spy):
                llm.complete("SYS", "USER")

        self.assertTrue(captured["url"].endswith("/chat/completions"))
        self.assertEqual(captured["auth"], "Bearer sk-x")
        self.assertEqual(captured["body"]["model"], "gpt-5.4-mini")
        roles = [m["role"] for m in captured["body"]["messages"]]
        self.assertEqual(roles, ["system", "user"])
        self.assertEqual(captured["body"]["messages"][1]["content"], "USER")

    def test_http_error_raises_llmerror(self):
        with mock.patch.dict("os.environ", {"OPENCODE_API_KEY": "sk-x"}, clear=True):
            err = HTTPError("u", 429, "rate limit", {}, None)
            with mock.patch("newsclaw.llm.urlopen", side_effect=err):
                with self.assertRaises(llm.LLMError):
                    llm.complete("sys", "user")

    def test_empty_content_raises_llmerror(self):
        with mock.patch.dict("os.environ", {"OPENCODE_API_KEY": "sk-x"}, clear=True):
            with mock.patch("newsclaw.llm.urlopen") as m:
                m.return_value.__enter__.return_value = fake_completion("   ")
                with self.assertRaises(llm.LLMError):
                    llm.complete("sys", "user")


if __name__ == "__main__":
    unittest.main()
