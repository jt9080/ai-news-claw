import unittest
from datetime import datetime, timezone

from newsclaw.feedparse import parse

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Lab Blog</title>
<item>
  <title>Introducing our new agent SDK</title>
  <link>https://openai.com/blog/agent-sdk</link>
  <pubDate>Tue, 07 Jul 2026 17:00:00 GMT</pubDate>
  <description>Today we release an agent SDK.</description>
</item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>arXiv</title>
<entry>
  <title>Emergent Coordination in LLM Multi-Agent Debate</title>
  <link href="http://arxiv.org/abs/2607.04567v1" rel="alternate"/>
  <published>2026-07-07T18:02:11Z</published>
  <summary>We study coordination.</summary>
</entry>
</feed>"""

ATOM_NO_DATE = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>No date here</title><link href="https://x/y"/></entry>
</feed>"""


class TestParse(unittest.TestCase):
    def test_parses_rss_item(self):
        entries = parse(RSS)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["title"], "Introducing our new agent SDK")
        self.assertEqual(e["link"], "https://openai.com/blog/agent-sdk")
        self.assertEqual(e["summary"], "Today we release an agent SDK.")
        self.assertEqual(e["published"], datetime(2026, 7, 7, 17, 0, 0, tzinfo=timezone.utc))

    def test_parses_atom_entry_with_href_link(self):
        entries = parse(ATOM)
        e = entries[0]
        self.assertEqual(e["title"], "Emergent Coordination in LLM Multi-Agent Debate")
        self.assertEqual(e["link"], "http://arxiv.org/abs/2607.04567v1")
        self.assertEqual(e["published"], datetime(2026, 7, 7, 18, 2, 11, tzinfo=timezone.utc))
        self.assertIn("coordination", e["summary"])

    def test_missing_date_is_none(self):
        e = parse(ATOM_NO_DATE)[0]
        self.assertIsNone(e["published"])

    def test_malformed_xml_returns_empty(self):
        self.assertEqual(parse(b"<not xml {{{"), [])

    def test_empty_bytes_returns_empty(self):
        self.assertEqual(parse(b""), [])


if __name__ == "__main__":
    unittest.main()
