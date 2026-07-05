#!/usr/bin/env python3
"""Phase 0 tests: robustness batch.

Each test = one of the 5 Phase 0 deliverables per PLAN.md.
Run with: /home/openclaw/openclaw_app/.venv/bin/python3 -m unittest discover tests
"""
import os
import sys
import unittest
import importlib
from pathlib import Path
from unittest import mock

WORKSPACE = Path("/home/openclaw/workspace")
WORKSPACE_PATH = str(WORKSPACE)
if WORKSPACE_PATH not in sys.path:
    sys.path.insert(0, WORKSPACE_PATH)


class ChannelsSingleSourceOfTruth(unittest.TestCase):
    """channels.py is the single source of truth for channel name->ID."""

    def test_channels_module_exists(self):
        import channels
        self.assertTrue(hasattr(channels, "CHANNELS"))

    def test_channels_dict_has_expected_names(self):
        import channels
        expected = {
            "research-planning", "literature", "coursework", "stm32-firmware",
            "simulation", "computer-vision", "control-laws", "ros-integration",
            "briefing", "general", "inspiration", "china-drone-robotics-industry",
        }
        self.assertTrue(expected.issubset(set(channels.CHANNELS.keys())),
                        f"missing: {expected - set(channels.CHANNELS.keys())}")

    def test_digest_imports_from_channels(self):
        """digest.CHANNELS must be channels.CHANNELS (same object)."""
        import channels
        import digest
        self.assertIs(digest.CHANNELS, channels.CHANNELS)

    def test_grab_poller_uses_channels(self):
        """grab_poller.WATCH must be derived from channels.CHANNELS values."""
        import channels
        import grab_poller
        channel_ids = set(channels.CHANNELS.values())
        for wid in grab_poller.WATCH:
            self.assertIn(wid, channel_ids,
                          f"grab_poller.WATCH contains {wid} not in channels.CHANNELS")

    def test_china_industry_channel_present(self):
        import channels
        self.assertEqual(
            channels.CHANNELS.get("china-drone-robotics-industry"),
            "1522959199611650159",
        )
    def test_coursework_channel_present(self):
        import channels
        self.assertEqual(channels.CHANNELS.get("coursework"),
                         "1479106309365432320")
    def test_briefing_is_known(self):
        import channels
        self.assertEqual(channels.CHANNELS.get("briefing"),
                         "1479107278538805320")


class FormatPaperGuard(unittest.TestCase):
    """format_paper() must guard against >2000-char Discord messages."""

    def _paper(self, abstract="", title="T", authors=None, note=""):
        return {
            "id": "test:x", "title": title, "abstract": abstract,
            "url": "https://example.com", "authors": authors or ["Alice"],
            "date": "2026-07-04", "source": "Test",
            "relevance": "HIGH", "topic": "test", "channel": "control-laws",
            "rank": 1, "note": note,
        }

    def test_short_paper_unchanged(self):
        import digest
        p = self._paper(abstract="hello world")
        out = digest.format_paper(p)
        self.assertIn("hello world", out)
        self.assertLessEqual(len(out), 2000)

    def test_long_abstract_truncated_or_split(self):
        import digest
        p = self._paper(abstract="x" * 5000, title="long paper",
                        authors=["A", "B"], note="n" * 200)
        out = digest.format_paper(p)
        if isinstance(out, list):
            for chunk in out:
                self.assertLessEqual(len(chunk), 2000,
                                     f"chunk exceeds 2000: {len(chunk)}")
            joined = "\n".join(out)
            self.assertIn("long paper", joined)
        else:
            self.assertLessEqual(len(out), 2000,
                                 f"single message exceeds 2000: {len(out)}")
            self.assertIn("long paper", out)


class DeadInterleaveRemoved(unittest.TestCase):
    def test_interleave_removed_from_digest(self):
        import digest
        self.assertFalse(hasattr(digest, "interleave"),
                         "interleave() is dead code per PLAN.md and must be deleted")


class CrashReporter(unittest.TestCase):
    """main() must post a short crash report to #briefing on uncaught exception."""

    def test_crash_posts_to_briefing_channel(self):
        import digest
        import channels
        briefing_id = channels.CHANNELS["briefing"]
        with mock.patch.object(digest, "load_all_priorities",
                               side_effect=RuntimeError("boom")):
            with mock.patch.object(digest, "post_discord",
                                   return_value=200) as post:
                with mock.patch.object(digest.argparse.ArgumentParser,
                                       "parse_args",
                                       return_value=mock.MagicMock(dry_run=False)):
                    try:
                        digest.main()
                    except SystemExit:
                        pass
                    except Exception as e:
                        self.fail(f"main() leaked exception: {e}")
        calls_to_briefing = [c for c in post.call_args_list
                             if c.args[0] == briefing_id]
        self.assertGreaterEqual(len(calls_to_briefing), 1,
                                "no crash post to #briefing")
        msg = calls_to_briefing[0].args[1].lower()
        self.assertTrue(("crash" in msg or "error" in msg or "boom" in msg),
                        f"crash message content not crash-like: {calls_to_briefing[0].args[1][:200]}")


class LLMSlotSwap(unittest.TestCase):
    """gpt-oss-120b is dropped from llm_layer.WORKERS — replace with a JSON-clean free model."""

    def test_gpt_oss_removed_from_workers(self):
        import llm_layer
        for slot in llm_layer.WORKERS:
            models = slot if isinstance(slot, (tuple, list)) else (slot,)
            for m in models:
                self.assertNotIn("gpt-oss-120b", str(m),
                                 f"gpt-oss-120b still present in WORKERS: {slot}")

    def test_workers_have_three_slots(self):
        import llm_layer
        self.assertEqual(len(llm_layer.WORKERS), 3,
                         f"expected 3 worker slots, got {len(llm_layer.WORKERS)}")


if __name__ == "__main__":
    unittest.main()
