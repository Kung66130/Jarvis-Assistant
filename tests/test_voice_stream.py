import threading
import unittest
from unittest import mock

from voice_stream import StreamingSegmentBuffer, split_for_speech
from pro_speak import build_provider_chain, get_cache_path, wait_for_playback


class SplitForSpeechTests(unittest.TestCase):
    def test_preserves_sentence_boundaries(self):
        text = "สวัสดีครับบอส วันนี้มีงานด่วนไหมครับ? ถ้ามีผมพร้อมช่วยครับ"
        self.assertEqual(
            split_for_speech(text, max_chars=80),
            [
                "สวัสดีครับบอส วันนี้มีงานด่วนไหมครับ?",
                "ถ้ามีผมพร้อมช่วยครับ",
            ],
        )

    def test_splits_long_text_without_punctuation(self):
        text = "หนึ่งสองสามสี่ห้าหกเจ็ดแปดเก้าสิบสิบเอ็ดสิบสองสิบสามสิบสี่สิบห้า"
        segments = split_for_speech(text, max_chars=20)
        self.assertGreater(len(segments), 1)
        self.assertTrue(all(len(segment) <= 20 for segment in segments))


class StreamingSegmentBufferTests(unittest.TestCase):
    def test_emits_segment_when_sentence_completes(self):
        buffer = StreamingSegmentBuffer(max_chars=80)
        emitted = buffer.push("กำลังตรวจ")
        self.assertEqual(emitted, [])

        emitted = buffer.push("สอบให้ครับบอส.")
        self.assertEqual(emitted, ["กำลังตรวจสอบให้ครับบอส."])
        self.assertIsNone(buffer.flush())

    def test_flushes_remainder(self):
        buffer = StreamingSegmentBuffer(max_chars=80)
        buffer.push("ยังไม่จบประโยค")
        self.assertEqual(buffer.flush(), "ยังไม่จบประโยค")


class WaitForPlaybackTests(unittest.TestCase):
    def test_terminates_process_when_stop_requested(self):
        fake_proc = mock.Mock()
        fake_proc.poll.side_effect = [None, None, None, 0]
        stop_event = threading.Event()

        def trigger_stop(_timeout):
            stop_event.set()
            return True

        stop_event.wait = trigger_stop
        wait_for_playback(fake_proc, stop_event=stop_event, poll_interval=0.01)

        fake_proc.terminate.assert_called_once()


class CachePathTests(unittest.TestCase):
    def test_provider_changes_cache_extension(self):
        edge_path = get_cache_path("ทดสอบ", "niwat", "edge")
        sapi_path = get_cache_path("ทดสอบ", "niwat", "sapi")
        self.assertTrue(edge_path.endswith(".mp3"))
        self.assertTrue(sapi_path.endswith(".wav"))


class ProviderChainTests(unittest.TestCase):
    def test_auto_prefers_sapi_when_requested(self):
        self.assertEqual(build_provider_chain("auto", preferred_provider="sapi"), ["sapi", "edge"])

    def test_auto_prefers_edge_when_requested(self):
        self.assertEqual(build_provider_chain("auto", preferred_provider="edge"), ["edge", "sapi"])


if __name__ == "__main__":
    unittest.main()
