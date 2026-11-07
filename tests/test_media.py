import asyncio
import importlib.util
import math
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock
import wave
import zlib

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'video-report' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
try:
    import report_media as media
except ModuleNotFoundError:
    media = None


def tone(path, samples=4800):
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        stream.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(i * 0.05)))
                                    for i in range(samples)))


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(media, 'report_media must implement the real media pipeline')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def report(self):
        return {'title': '报告', 'scenes': [{'id': 's1', 'kind': 'title', 'title': '开场',
                'narration': '外部录音', 'audio': 'input.wav',
                'captions': [{'start_ms': 10, 'end_ms': 90, 'text': '真实时间'}]}]}

    def test_tool_resolution_prefers_explicit_executable(self):
        ffmpeg = self.root / 'ffmpeg.exe'
        ffprobe = self.root / 'ffprobe.exe'
        ffmpeg.touch()
        ffprobe.touch()
        with mock.patch.dict('os.environ', {'VIDEO_REPORT_FFMPEG': str(ffmpeg),
                                          'VIDEO_REPORT_FFPROBE': str(ffprobe),
                                          'VIDEO_REPORT_DEPENDENCIES': str(self.root / 'missing.json')}):
            self.assertEqual(media.resolve_tools(), {'ffmpeg': str(ffmpeg), 'ffprobe': str(ffprobe)})

    def test_external_audio_has_sample_exact_padding_and_caption_offsets(self):
        tone(self.root / 'input.wav', samples=4801)
        report = self.report()
        report['scenes'] = [dict(report['scenes'][0], id=f's{i}') for i in range(10)]
        with mock.patch.object(media, 'resolve_tools', return_value={'ffmpeg': 'unused', 'ffprobe': 'unused'}), \
                mock.patch.object(media, '_normalize_audio', side_effect=lambda src, dst, tools: shutil.copyfile(src, dst)):
            timeline, captions, manifest = media.prepare_audio(report, self.root / 'out', self.root)
        self.assertEqual(timeline[0]['duration_samples'], 28801)
        self.assertEqual(timeline[-1]['end_frame'], math.ceil(288010 * 30 / 48000))
        self.assertEqual(captions[0]['start_ms'], 160)
        self.assertEqual(captions[1]['start_ms'], 160 + 28801 / 48)
        with wave.open(str(self.root / 'out' / 'voice.wav')) as stream:
            self.assertEqual(stream.getnframes(), 288010)
            self.assertEqual((stream.getframerate(), stream.getnchannels(), stream.getsampwidth()), (48000, 1, 2))
        self.assertEqual(manifest['sample_rate'], 48000)
        for name in ('timeline.json', 'subtitles.srt', 'subtitles.ass'):
            self.assertTrue((self.root / 'out' / name).is_file())

    def test_external_caption_cannot_exceed_recording(self):
        tone(self.root / 'input.wav')
        report = self.report()
        report['scenes'][0]['captions'][0]['end_ms'] = 101
        with mock.patch.object(media, 'resolve_tools', return_value={}), \
                mock.patch.object(media, '_normalize_audio', side_effect=lambda src, dst, tools: shutil.copyfile(src, dst)):
            with self.assertRaisesRegex(ValueError, 'caption.*outside|caption.*duration'):
                media.prepare_audio(report, self.root / 'out', self.root)

    def test_external_caption_overlap_is_rejected_before_publishing_voice(self):
        tone(self.root / 'input.wav')
        report = self.report()
        report['scenes'][0]['captions'] = [
            {'start_ms': 0, 'end_ms': 60, 'text': '第一条'},
            {'start_ms': 50, 'end_ms': 90, 'text': '第二条'}]
        with mock.patch.object(media, 'resolve_tools', return_value={}), \
                mock.patch.object(media, '_normalize_audio', side_effect=lambda src, dst, tools: shutil.copyfile(src, dst)):
            with self.assertRaisesRegex(ValueError, 'overlap'):
                media.prepare_audio(report, self.root / 'out', self.root)
        self.assertFalse((self.root / 'out' / 'voice.wav').exists())

    def test_scene_audio_names_are_safe_and_unique_after_sanitizing_ids(self):
        tone(self.root / 'input.wav')
        report = self.report()
        identifiers = ['../chapter', '..\\chapter', 'x/y', 'x\\y', 'CON', '中文', '中文二',
                       'a' * 80 + 'x', 'a' * 80 + 'y', 'Case', 'case']
        report['scenes'] = [dict(report['scenes'][0], id=scene_id) for scene_id in identifiers]
        output = self.root / 'out'
        with mock.patch.object(media, 'resolve_tools', return_value={}), \
                mock.patch.object(media, '_normalize_audio', side_effect=lambda src, dst, tools: shutil.copyfile(src, dst)):
            timeline, captions, manifest = media.prepare_audio(report, output, self.root)
        paths = [Path(scene['audio']).resolve() for scene in manifest['scenes']]
        self.assertEqual(len(paths), len({str(path).casefold() for path in paths}))
        self.assertTrue(all(path.parent == (output / 'audio').resolve() for path in paths))
        self.assertTrue(all(path.is_file() for path in paths))
        self.assertEqual([entry['id'] for entry in timeline], identifiers)

    def test_missing_external_audio_fails_without_silent_voice(self):
        with mock.patch.object(media, 'resolve_tools', return_value={}):
            with self.assertRaisesRegex(RuntimeError, 'does not exist'):
                media.prepare_audio(self.report(), self.root / 'out', self.root)
        self.assertFalse((self.root / 'out' / 'voice.wav').exists())

    def test_tts_failure_without_external_audio_never_substitutes_silence(self):
        report = self.report()
        del report['scenes'][0]['audio']
        with mock.patch.object(media, 'resolve_tools', return_value={}), \
                mock.patch.object(media, '_tts_audio', side_effect=RuntimeError('provider unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'provider unavailable'):
                media.prepare_audio(report, self.root / 'out', self.root)
        self.assertFalse((self.root / 'out' / 'voice.wav').exists())

    def test_edge_stream_with_no_audio_bytes_fails(self):
        class EmptyProvider:
            def __init__(self, *args, **kwargs):
                pass
            async def stream(self):
                yield {'type': 'WordBoundary', 'offset': 0, 'duration': 1000000, 'text': '测试'}
        with mock.patch.dict(sys.modules, {'edge_tts': types.SimpleNamespace(Communicate=EmptyProvider)}):
            with self.assertRaisesRegex(RuntimeError, 'no audio'):
                asyncio.run(media._edge_stream('测试', {}, self.root / 'empty.mp3'))

    def test_silent_tts_audio_is_not_published_as_complete_cache(self):
        async def silent_stream(text, voice, audio_path):
            audio_path.write_bytes(b'simulated encoded silence')
            return []
        def normalize_silence(src, dst, tools):
            media._write_pcm(dst, b'\0\0' * 4800)
        with mock.patch.object(media, '_edge_stream', side_effect=silent_stream), \
                mock.patch.object(media, '_normalize_audio', side_effect=normalize_silence):
            with self.assertRaisesRegex(RuntimeError, 'silent'):
                media._tts_audio('测试', {}, self.root / 'cache', {})
        self.assertFalse(list((self.root / 'cache').glob('*/meta.json')))

    def test_silent_external_recording_fails_before_publishing_voice(self):
        media._write_pcm(self.root / 'input.wav', b'\0\0' * 4800)
        with mock.patch.object(media, 'resolve_tools', return_value={}), \
                mock.patch.object(media, '_normalize_audio', side_effect=lambda src, dst, tools: shutil.copyfile(src, dst)):
            with self.assertRaisesRegex(RuntimeError, 'silent'):
                media.prepare_audio(self.report(), self.root / 'out', self.root)
        self.assertFalse((self.root / 'out' / 'voice.wav').exists())

    def test_different_spoken_text_keeps_measured_segment_timing(self):
        tone(self.root / 'segment.wav', samples=4800)
        report = self.report()
        scene = report['scenes'][0]
        del scene['audio']
        del scene['captions']
        scene['narration_segments'] = [{'text': 'P/E', 'spoken': '市盈率'}, {'text': '增长'}]
        payload = {'wave': self.root / 'segment.wav', 'events': [], 'cache_key': 'test', 'cache_hit': False}
        with mock.patch.object(media, 'resolve_tools', return_value={}), \
                mock.patch.object(media, '_tts_audio', return_value=payload):
            timeline, captions, manifest = media.prepare_audio(report, self.root / 'out', self.root)
        self.assertEqual([c['text'] for c in captions], ['P/E', '增长'])
        self.assertEqual([(c['start_ms'], c['end_ms']) for c in captions], [(150, 250), (250, 350)])
        self.assertEqual(timeline[0]['duration_samples'], 33600)

    def test_tts_failure_retries_three_times_without_publishing_cache(self):
        async def fail(*args, **kwargs):
            raise RuntimeError('provider unavailable')
        with mock.patch.object(media, '_edge_stream', side_effect=fail) as provider:
            with self.assertRaisesRegex(RuntimeError, '3 attempts'):
                media._tts_audio('测试', {}, self.root / 'cache', {})
        self.assertEqual(provider.call_count, 3)
        self.assertFalse(list((self.root / 'cache').glob('*/meta.json')))

    def test_complete_tts_cache_is_reused_and_incomplete_cache_is_not(self):
        async def fake_stream(text, voice, audio_path):
            audio_path.write_bytes(b'mp3 data')
            return [{'type': 'WordBoundary', 'offset': 0, 'duration': 1000000, 'text': text}]
        def normalize(src, dst, tools):
            tone(dst)
        with mock.patch.object(media, '_edge_stream', side_effect=fake_stream) as provider, \
                mock.patch.object(media, '_normalize_audio', side_effect=normalize):
            first = media._tts_audio('测试', {}, self.root / 'cache', {})
            second = media._tts_audio('测试', {}, self.root / 'cache', {})
            self.assertEqual(provider.call_count, 1)
            self.assertTrue(second['cache_hit'])
            (second['wave'].parent / 'meta.json').unlink()
            media._tts_audio('测试', {}, self.root / 'cache', {})
            self.assertEqual(provider.call_count, 2)
        self.assertEqual(first['events'][0]['text'], '测试')

    def test_word_boundary_captions_preserve_original_punctuation(self):
        events = [{'type': 'WordBoundary', 'offset': 1000000, 'duration': 1000000, 'text': '增长'},
                  {'type': 'WordBoundary', 'offset': 3000000, 'duration': 1000000, 'text': '放缓'}]
        captions = media._event_captions(events, '增长。放缓。', 500, 22)
        self.assertEqual([c['text'] for c in captions], ['增长。', '放缓。'])
        self.assertEqual([(c['start_ms'], c['end_ms']) for c in captions], [(100, 200), (300, 400)])

    def test_unmatched_provider_words_keep_provider_times_without_forced_alignment(self):
        events = [{'type': 'WordBoundary', 'offset': 1000000, 'duration': 1000000, 'text': '归一化文本'}]
        captions = media._event_captions(events, '输入原文。', 500, 22)
        self.assertEqual(captions[0]['text'], '归一化文本')
        self.assertEqual((captions[0]['start_ms'], captions[0]['end_ms']), (100, 200))

    def test_process_errors_include_stderr_and_timeout_is_bounded(self):
        with self.assertRaisesRegex(RuntimeError, 'diagnostic failure'):
            media._run([sys.executable, '-c', "import sys;sys.stderr.write('diagnostic failure');sys.exit(2)"], timeout=10)
        with self.assertRaisesRegex(RuntimeError, 'timed out'):
            media._run([sys.executable, '-c', 'import time;time.sleep(5)'], timeout=0.01)

    def test_real_ffmpeg_pipeline_has_exact_frame_count_and_audible_audio(self):
        try:
            media.resolve_tools()
        except RuntimeError:
            self.skipTest('FFmpeg and FFprobe are not installed')
        tone(self.root / 'input.wav', samples=4801)
        report = dict(self.report(), width=320, height=180, font_size=16)
        report['scenes'].append(dict(report['scenes'][0], id='s2'))
        output = self.root / 'output with spaces'
        timeline, captions, manifest = media.prepare_audio(report, output, self.root)
        images = []
        for i, color in enumerate((b'\x20\x40\x80', b'\x80\x40\x20')):
            path = self.root / f'frame {i}.png'
            def chunk(kind, data):
                return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
            raw = b''.join(b'\0' + color * 320 for _ in range(180))
            path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 320, 180, 8, 2, 0, 0, 0))
                             + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
            images.append(path)
        encoded = media.encode_video(output, report, timeline, images)
        self.assertEqual(encoded['frames'], timeline[-1]['end_frame'])
        qa = media.check_media(output)
        self.assertTrue(qa['passed'], qa)
        self.assertEqual(qa['video']['frames'], timeline[-1]['end_frame'])
        self.assertTrue(qa['audio']['non_silent'])


if __name__ == '__main__':
    unittest.main()
