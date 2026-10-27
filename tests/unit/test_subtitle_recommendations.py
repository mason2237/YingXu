"""Pure offline candidate boundaries and ranking; no site visits."""
import json
import unittest

from yingxu.subtitle_sources.candidates import candidates_script, parse_candidates, rank_candidates
from yingxu.subtitle_sources.websites import website_for


def candidate(code="Ab12", release="Example.2024.1080p.BluRay", metadata="双语 简体 英语 ASS"):
    return {"url": "https://subhd.me/a/" + code, "title": "Example", "release": release, "metadata": metadata}


class RecommendationTests(unittest.TestCase):
    def test_url_boundary_dedup_and_metadata_limits(self):
        rows = [candidate(), candidate(), {**candidate(), "url": "https://other.example/a/A"},
                {**candidate(), "url": "https://subhd.me/search/download"},
                {**candidate("Cd34"), "metadata": "x" * 8000},
                {**candidate("Xy"), "url": "https://subhd.me/a/Xy?secret=never-store#fragment"}]
        status, parsed = parse_candidates(json.dumps({"status": "ready", "rows": rows}), website_for("subhd"))
        self.assertEqual(status, "ready")
        self.assertEqual(len(parsed), 3)
        self.assertEqual(len(parsed[1]["metadata"]), 400)
        self.assertEqual(parsed[2]["url"], "https://subhd.me/a/Xy")

    def test_malformed_and_unverified_source_never_become_ready(self):
        for raw in ("null", "[]", "{bad", "x" * 300000, None, '{"rows":{}}'):
            self.assertEqual(parse_candidates(raw, website_for("subhd")), ("unrecognized", []))
        raw = json.dumps({"status": "ready", "rows": [candidate()]})
        self.assertEqual(parse_candidates(raw, website_for("zimuku")), ("unrecognized", []))
        self.assertEqual(parse_candidates('{"status":"empty","rows":[]}', website_for("subhd")), ("empty", []))

    def test_bilingual_requires_explicit_metadata(self):
        rows = [candidate("A", metadata="简体 英语 ASS"), candidate("B", metadata="双语 简体 英语 ASS")]
        ranked = rank_candidates(rows, "Example.2024.1080p.mkv")
        self.assertTrue(ranked[0]["url"].endswith("/B"))
        self.assertFalse(ranked[0]["needsReview"])
        self.assertIn("未注明双语", ranked[1]["language"])
        self.assertTrue(ranked[1]["needsReview"])
        self.assertNotIn("score", ranked[0])

    def test_language_preference_changes_order(self):
        rows = [candidate("A"), candidate("B", metadata="繁体 SRT")]
        ranked = rank_candidates(rows, "Example.2024.mkv", "zh-Hant")
        self.assertTrue(ranked[0]["url"].endswith("/B"))

    def test_episode_conflict_is_last_even_with_preferred_language(self):
        rows = [candidate("A", release="Example.S01E03.1080p"),
                candidate("B", release="Example.S01E02.1080p", metadata="英语 SRT")]
        ranked = rank_candidates(rows, "Example.S01E02.1080p.mkv")
        self.assertTrue(ranked[-1]["url"].endswith("/A"))
        self.assertIn("集数不一致", ranked[-1]["warnings"])
        self.assertTrue(ranked[-1]["needsReview"])

    def test_year_missing_and_alias_are_explained(self):
        row = candidate(release="Interstellar.2014.1080p", metadata="双语 简体 英语")
        row["title"] = "Interstellar"
        ranked = rank_candidates([row], "星际穿越.2015.mkv")[0]
        self.assertIn("年份不一致", ranked["warnings"])
        self.assertEqual(ranked["label"], "信息冲突")
        self.assertTrue(any("别名" in reason for reason in ranked["warnings"]))
        self.assertTrue(any("集数" in reason for reason in rank_candidates([candidate()], "Example.S01E02.mkv")[0]["warnings"]))

    def test_result_scripts_encode_query_and_do_not_expose_local_paths(self):
        query = '\"; alert(1); 中文'
        source = candidates_script(website_for("subhd"), query)
        self.assertIn(json.dumps(query, ensure_ascii=True), source)
        self.assertIn("not_results", source)
        self.assertNotIn("QWebChannel", source)


if __name__ == "__main__":
    unittest.main()
