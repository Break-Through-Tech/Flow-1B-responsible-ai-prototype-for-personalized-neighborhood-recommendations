"""Run: python -m unittest tests.test_nlp_themes -v   (no API key needed)"""

import json
import tempfile
import unittest
from pathlib import Path

from src.nlp.config import RECOMMENDER_TAGS
from src.nlp.growth import promote, record
from src.nlp.pipeline import (build_location_tags, crowd_themes, internal_flags,
                              load_snippets, sentiment_records)
from src.nlp.sentiment import analyze, combine
from src.nlp.tag_index import (build_index, similar_zips, tag_matrix, tags_for_zip,
                               zips_with_tag)
from src.nlp.tagging import TaggingError, build_prompt, parse_response, tag_snippets
from src.nlp.try_sentences import SENTIMENT_SAMPLES
from src.nlp.vocabulary import (add_tag, find_existing, is_blocked, load_vocabulary,
                                parents, with_parents)

VOCAB = load_vocabulary()


def fresh_vocab():
    return json.loads(json.dumps(VOCAB))


def snip(sid, z, text):
    return {"snippet_id": sid, "zip": z, "source": "test", "text": text, "is_demo": True}


class FakeLLM:
    """Stands in for Gemini: returns a fixed JSON answer and counts calls."""
    def __init__(self, answers):
        self.answers, self.calls = answers, 0

    def __call__(self, prompt):
        self.calls += 1
        return json.dumps({"results": self.answers})


# ---------------------------------------------------------------------------
# Part 1: sentiment
# ---------------------------------------------------------------------------
class TestSentiment(unittest.TestCase):
    def test_samples(self):
        for sentence, rent, area in SENTIMENT_SAMPLES:
            with self.subTest(sentence=sentence):
                a = analyze(sentence)
                self.assertEqual((a["rent"]["label"], a["area"]["label"]), (rent, area))

    def test_high_only_negative_for_rent(self):
        self.assertNotEqual(analyze("High ceilings and lots of light.")["area"]["label"], "negative")

    def test_safety_clause_not_scored(self):
        a = analyze("Felt unsafe at night; great food though.")
        self.assertTrue(a["needs_review"])
        self.assertEqual(a["area"]["label"], "positive")   # only the food clause counts

    def test_combine(self):
        self.assertEqual(combine(["positive", "negative"]), "mixed")
        self.assertEqual(combine(["neutral", "negative"]), "negative")
        self.assertEqual(combine([]), "not_mentioned")

    def test_internal_flags(self):
        recs = sentiment_records([snip("A", "11111", "Rent is way too expensive."),
                                  snip("B", "22222", "Great parks and calm streets."),
                                  snip("C", "33333", "Street noise all night.")])
        got = {(f["zip"], f["flag"]) for f in internal_flags(recs)}
        self.assertEqual(got, {("11111", "rent_negative"), ("33333", "area_negative")})


# ---------------------------------------------------------------------------
# Part 2: LLM tagging (fake model, no network)
# ---------------------------------------------------------------------------
class TestTagging(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache.json"
        self.batch = [snip("A", "11111", "Five minutes from the sand."),
                      snip("B", "22222", "Bars right downstairs.")]

    def tearDown(self):
        self.tmp.cleanup()

    def test_prompt_lists_vocab_and_text(self):
        p = build_prompt(self.batch, VOCAB)
        self.assertIn("- beach:", p)
        self.assertIn("    - metromover:", p)          # specific tags indented under parent
        self.assertIn("Five minutes from the sand.", p)

    def test_parse_keeps_known_tags_and_cleans_proposals(self):
        raw = json.dumps({"results": [
            {"id": "A", "tags": [{"tag": "beach", "evidence": "from the sand"},
                                 {"tag": "Ocean View", "evidence": "x"}]},
            {"id": "B", "tags": [{"tag": "nightlife", "evidence": "not in text"}],
             "proposed": [{"tag": "family_friendly"},
                          {"tag": "rooftop bars", "parent": "after_work_scene", "description": "d"},
                          {"tag": "metro_rail", "parent": "transit"}]},
            {"id": "ZZZ", "tags": [{"tag": "beach"}]},          # unknown id ignored
        ]})
        out = parse_response(raw, self.batch, VOCAB)
        self.assertEqual([t["tag"] for t in out["A"]["tags"]], ["beach"])
        self.assertTrue(out["A"]["tags"][0]["evidence_found"])
        self.assertEqual(out["A"]["proposed"], [{"tag": "ocean_view", "parent": None, "description": ""}])
        self.assertFalse(out["B"]["tags"][0]["evidence_found"])
        # family_* blocked; metro_rail duplicates metrorail; child parent lifted to top level
        self.assertEqual(out["B"]["proposed"],
                         [{"tag": "rooftop_bars", "parent": "nightlife", "description": "d"}])
        self.assertNotIn("ZZZ", out)

    def test_parse_handles_code_fence_and_bad_json(self):
        fenced = '```json\n{"results": [{"id": "A", "tags": ["beach"]}]}\n```'
        self.assertEqual(parse_response(fenced, self.batch, VOCAB)["A"]["tags"][0]["tag"], "beach")
        with self.assertRaises(TaggingError):
            parse_response("not json", self.batch, VOCAB)

    def test_blocked_terms(self):
        for t in ["family_friendly", "safe_area", "hispanic_community", "religious"]:
            self.assertTrue(is_blocked(t), t)
        self.assertFalse(is_blocked("rooftop_pool"))

    def test_cache_avoids_second_call(self):
        llm = FakeLLM([{"id": "A", "tags": [{"tag": "beach", "evidence": "sand"}]},
                       {"id": "B", "tags": [{"tag": "nightlife", "evidence": "Bars"}]}])
        r1 = tag_snippets(self.batch, client=llm, vocab=VOCAB, cache_path=self.cache)
        r2 = tag_snippets(self.batch, client=llm, vocab=VOCAB, cache_path=self.cache)
        self.assertEqual(llm.calls, 1)
        self.assertEqual(r1["tags"], r2["tags"])
        self.assertEqual(r2["untagged"], [])

    def test_offline_and_errors(self):
        r = tag_snippets(self.batch, vocab=VOCAB, cache_path=self.cache, offline=True)
        self.assertEqual(r["untagged"], ["A", "B"])
        broken = lambda prompt: "oops"
        r = tag_snippets(self.batch, client=broken, vocab=VOCAB, cache_path=self.cache)
        self.assertEqual(len(r["errors"]), 1)
        self.assertEqual(r["untagged"], ["A", "B"])

    def test_stale_entries_are_retagged(self):
        llm = FakeLLM([{"id": "A", "tags": [{"tag": "beach", "evidence": "sand"}]},
                       {"id": "B", "tags": []}])
        tag_snippets(self.batch, client=llm, vocab=VOCAB, cache_path=self.cache)
        tag_snippets(self.batch, client=llm, vocab=VOCAB, cache_path=self.cache,
                     min_vocab_version=VOCAB["version"] + 1)
        self.assertEqual(llm.calls, 2)


# ---------------------------------------------------------------------------
# Tag list and automatic growth
# ---------------------------------------------------------------------------
class TestVocabulary(unittest.TestCase):
    def test_recommender_tags_are_top_level(self):
        for t in RECOMMENDER_TAGS:
            self.assertIn(t, parents(VOCAB), t)

    def test_every_parent_exists(self):
        for t, v in VOCAB["tags"].items():
            if v["parent"]:
                self.assertIn(v["parent"], parents(VOCAB), t)

    def test_with_parents(self):
        self.assertEqual(with_parents(VOCAB, ["metromover", "transit"]), ["metromover", "transit"])

    def test_find_existing(self):
        self.assertEqual(find_existing(VOCAB, "Metro Rail"), "metrorail")
        self.assertEqual(find_existing(VOCAB, "tree_lined_street"), "tree_lined_streets")
        self.assertIsNone(find_existing(VOCAB, "live_music"))

    def test_add_tag_bumps_version_and_fixes_parent(self):
        v = fresh_vocab()
        add_tag(v, "live_music", "after_work_scene", "d")     # child given as parent
        self.assertEqual(v["version"], VOCAB["version"] + 1)
        self.assertIsNone(v["tags"]["live_music"]["parent"])  # only top-level parents allowed


class TestGrowth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "log.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_added_after_two_reviews(self):
        v, ledger = fresh_vocab(), {}
        p = {"tag": "live_music", "parent": "nightlife", "description": "Live music venues"}
        record(ledger, [("A", p)], {"A": "11111"})
        self.assertEqual(promote(v, ledger, log_path=self.log), [])     # 1 review: wait
        record(ledger, [("A", p)], {"A": "11111"})                       # same review again
        self.assertEqual(promote(v, ledger, log_path=self.log), [])
        record(ledger, [("B", p)], {"B": "22222"})                       # second review
        self.assertEqual(promote(v, ledger, log_path=self.log), ["live_music"])
        self.assertEqual(v["tags"]["live_music"]["parent"], "nightlife")
        self.assertEqual(v["tags"]["live_music"]["source"], "auto")
        self.assertNotIn("live_music", ledger)
        row = json.loads(self.log.read_text().splitlines()[0])
        self.assertEqual(row["zips"], ["11111", "22222"])

    def test_duplicates_are_dropped(self):
        v, ledger = fresh_vocab(), {}
        record(ledger, [("A", {"tag": "metro_rails"}), ("B", {"tag": "metro_rails"})], {})
        self.assertEqual(promote(v, ledger, log_path=self.log), [])
        self.assertEqual(ledger, {})

    def test_area_loop_grows_list_and_backfills(self):
        """Area 1 proposes live_music, area 2 confirms it, area 1 is then re-checked."""
        snips = [snip("A", "11111", "Jazz bar downstairs."), snip("B", "22222", "Bands play on Fridays.")]
        answers = {
            "A": {"id": "A", "tags": [{"tag": "nightlife", "evidence": "bar"}],
                  "proposed": [{"tag": "live_music", "parent": "nightlife", "description": "Live music"}]},
            "B": {"id": "B", "tags": [{"tag": "nightlife", "evidence": "Bands"}],
                  "proposed": [{"tag": "live_music", "parent": "nightlife", "description": "Live music"}]},
        }

        def llm(prompt):
            ids = [k for k in answers if f'"id": "{k}"' in prompt]
            out = []
            for k in ids:
                a = json.loads(json.dumps(answers[k]))
                if "- live_music" in prompt or "    - live_music" in prompt:   # tag now exists
                    a["tags"].append({"tag": "live_music", "evidence": a["tags"][0]["evidence"]})
                    a["proposed"] = []
                out.append(a)
            return json.dumps({"results": out})

        tmp = Path(self.tmp.name)
        index, res = build_location_tags(snips, client=llm, save=False, vocab=fresh_vocab(),
                                         cache_path=tmp / "cache.json",
                                         ledger_path=tmp / "ledger.json", log_path=self.log)
        self.assertEqual(res["added"], ["live_music"])
        self.assertEqual(sorted(res["backfilled"]), ["A", "B"])
        self.assertIn("live_music", tags_for_zip(index, "11111"))       # area 1 got the new tag
        self.assertIn("live_music", tags_for_zip(index, "22222"))


# ---------------------------------------------------------------------------
# Location tag repository
# ---------------------------------------------------------------------------
class TestTagIndex(unittest.TestCase):
    def setUp(self):
        snips = [snip("A", "11111", "a"), snip("B", "11111", "b"),
                 snip("C", "22222", "c"), snip("D", "33333", "d")]
        tag = lambda *ts: {"tags": [{"tag": t, "evidence": ""} for t in ts], "proposed": []}
        tagged = {"A": tag("beach", "after_work_scene"), "B": tag("beach"),
                  "C": tag("beach", "nightlife", "metromover"), "D": tag("quiet")}
        self.index = build_index(snips, tagged, VOCAB, "fake")

    def test_children_roll_up_to_parent(self):
        self.assertEqual(tags_for_zip(self.index, "11111"), ["beach", "after_work_scene", "nightlife"])
        self.assertEqual(tags_for_zip(self.index, "11111", "parent"), ["beach", "nightlife"])
        self.assertEqual(tags_for_zip(self.index, "22222", "specific"), ["metromover"])

    def test_parent_counted_once_per_review(self):
        index = build_index([snip("A", "1", "a")],
                            {"A": {"tags": [{"tag": "metrorail", "evidence": ""},
                                            {"tag": "metromover", "evidence": ""}]}}, VOCAB, "f")
        self.assertEqual(index["locations"]["1"]["tags"]["transit"]["count"], 1)

    def test_queries(self):
        self.assertEqual(zips_with_tag(self.index, "beach"), [("11111", 2), ("22222", 1)])
        self.assertEqual(zips_with_tag(self.index, "nightlife"), [("11111", 1), ("22222", 1)])

    def test_similar_zips_through_parent(self):
        sim = similar_zips(self.index, "11111")
        self.assertEqual(sim[0]["zip"], "22222")
        self.assertEqual(sim[0]["shared_tags"], ["beach", "nightlife"])

    def test_tag_matrix(self):
        m = tag_matrix(self.index, ["beach", "quiet"])
        self.assertEqual(m["11111"], {"beach": 1.0, "quiet": 0.0})

    def test_crowd_themes(self):
        self.assertEqual(crowd_themes("11111", index=self.index)["status"], "ok")
        self.assertEqual(crowd_themes("99999", index=self.index)["status"], "no_evidence")
        self.assertEqual(crowd_themes("331", index=self.index)["status"], "invalid_zip")
        out = crowd_themes("22222", tags=["transit"], index=self.index)
        self.assertEqual([t["tag"] for t in out["tags"]], ["transit"])


# ---------------------------------------------------------------------------
# Repository demo data
# ---------------------------------------------------------------------------
class TestRepoData(unittest.TestCase):
    def test_demo_file_loads(self):
        snips = load_snippets()
        self.assertEqual(len(snips), 20)
        self.assertTrue(all(len(s["zip"]) == 5 for s in snips))


if __name__ == "__main__":
    unittest.main()
