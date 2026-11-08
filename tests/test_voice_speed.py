import inspect
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/video-report/scripts'))
import report_core as core
import report_media as media


class VoiceSpeedTests(unittest.TestCase):
    def test_speed_is_validated_before_synthesis(self):
        report = {'title': 'Sample', 'voice': {'speed': 0}, 'scenes': [
            {'id': 'one', 'kind': 'cards', 'title': 'Sample', 'narration': '完整句。'}]}
        for speed in (0, -1, float('inf'), True, 2.1):
            with self.subTest(speed=speed):
                report['voice']['speed'] = speed
                self.assertTrue(any('speed' in e for e in core.validate_report(report)))

    def test_word_boundaries_scale_with_pitch_preserving_speed(self):
        self.assertIn('speed', inspect.signature(media._event_captions).parameters,
                      'Caption conversion does not support the audio speed factor')
        events = [{'type': 'WordBoundary', 'offset': 2000000, 'duration': 1000000, 'text': '完整'},
                  {'type': 'WordBoundary', 'offset': 3000000, 'duration': 2000000, 'text': '句'}]
        cues = media._event_captions(events, '完整句。', 800, 36, speed=1.25)
        self.assertEqual(cues[0]['text'], '完整句。')
        self.assertEqual((cues[0]['start_ms'], cues[0]['end_ms']), (160, 400))

    def test_speed_only_change_reuses_the_raw_voice_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            async def stream(text, voice, path):
                path.write_bytes(b'test audio')
                return []
            def normalize(source, target, tools):
                media._write_pcm(target, b'\x00\x10' * 48000)
            with mock.patch.object(media, '_edge_stream', side_effect=stream) as provider, \
                    mock.patch.object(media, '_normalize_audio', side_effect=normalize):
                media._tts_audio('完整句。', {'rate': '+5%'}, root, {})
                result = media._tts_audio('完整句。', {'rate': '+5%', 'speed': 1.25}, root, {})
            self.assertEqual(provider.call_count, 1)
            self.assertTrue(result['cache_hit'])

    def test_external_recording_speed_and_captions_stay_synchronized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pcm = b''.join(struct.pack('<h', int(8000*math.sin(i*0.05))) for i in range(96000))
            media._write_pcm(root/'source.wav', pcm)
            report = {'title': 'Sample', 'voice': {'speed': 1.25}, 'scenes': [
                {'id': 'one', 'kind': 'cards', 'title': 'Sample', 'narration': '完整句。',
                 'audio': 'source.wav', 'captions': [{'start_ms': 200, 'end_ms': 900, 'text': '完整句。'}]}]}
            timeline, cues, manifest = media.prepare_audio(report, root/'out', root)
            speech_samples = timeline[0]['duration_samples']-24000
            self.assertAlmostEqual(speech_samples, 96000/1.25, delta=1440)
            self.assertEqual((cues[0]['start_ms'], cues[0]['end_ms']), (310, 870))
            self.assertEqual(manifest['voice']['speed'], 1.25)


if __name__ == '__main__':
    unittest.main()
