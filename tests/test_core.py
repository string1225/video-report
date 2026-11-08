import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'video-report' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
try:
    import report_core as core
except ModuleNotFoundError:
    core = None


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(core, 'report_core must implement the portable report APIs')

    def report(self):
        return {'title': '研究报告', 'scenes': [{'id': 's1', 'kind': 'title',
                'title': '开场', 'narration': '这是一份研究报告。'}]}

    def test_validation_accepts_extensions_and_segment_narration(self):
        report = self.report()
        report['custom'] = {'future': True}
        scene = report['scenes'][0]
        del scene['narration']
        scene['narration_segments'] = [{'text': 'P/E', 'spoken': '市盈率'}]
        self.assertEqual(core.validate_report(report), [])

    def test_validation_reports_duplicate_unknown_sources_and_bad_settings(self):
        report = self.report()
        report.update(width=0, height=1081, fps=float('nan'))
        report['scenes'].append(dict(report['scenes'][0], narration=' ', source_ids=['absent']))
        errors = '\n'.join(core.validate_report(report))
        for term in ('duplicate', 'source', 'narration', 'width', 'height', 'fps'):
            self.assertIn(term, errors.lower())

    def test_cache_key_is_order_independent_but_content_sensitive(self):
        self.assertEqual(core.cache_key({'中': 1, 'b': [2]}), core.cache_key({'b': [2], '中': 1}))
        self.assertNotEqual(core.cache_key({'a': 1}), core.cache_key({'a': 2}))
        self.assertEqual(len(core.cache_key({'a': 1})), 64)

    def test_timeline_uses_cumulative_frame_boundaries(self):
        timeline = core.make_timeline([101] * 200, fps=30)
        self.assertEqual(timeline[-1]['end_frame'], 606)
        for index, item in enumerate(timeline):
            self.assertEqual(item['start_frame'], math.ceil(index * 101 * 30 / 1000))
            self.assertEqual(item['end_frame'], math.ceil((index + 1) * 101 * 30 / 1000))
            self.assertEqual(item['duration_ms'], 101)
        self.assertEqual(timeline[-1]['end_ms'], 20200)

    def test_timeline_rejects_nonfinite_or_negative_durations(self):
        for value in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                core.make_timeline([value])

    def test_sentence_captions_keep_provider_timing(self):
        text = '这是一个很长的中文句子，字幕可以换行，但不能凭空制造逐字时间。'
        captions = core.make_captions([{'start_ms': 100, 'end_ms': 5000,
                                      'text': text, 'type': 'sentence'}], max_chars=12)
        self.assertEqual(len(captions), 1)
        self.assertEqual(captions[0]['start_ms'], 100)
        self.assertEqual(captions[0]['end_ms'], 5000)
        self.assertEqual(captions[0]['timing'], 'sentence')
        self.assertLessEqual(len(captions[0]['text'].splitlines()), 2)
        self.assertEqual(''.join(captions[0]['text'].splitlines()), text)

    def test_word_captions_group_actual_boundaries(self):
        events = [{'start_ms': i * 100, 'end_ms': i * 100 + 80, 'text': t, 'type': 'word'}
                  for i, t in enumerate(['中', '国', '研', '究', '报', '告'])]
        captions = core.make_captions(events, max_chars=4)
        self.assertEqual(len(captions), 1)
        self.assertEqual(captions[0]['text'].replace('\n', ''), '中国研究报告')
        self.assertEqual([(c['start_ms'], c['end_ms']) for c in captions], [(0, 580)])
        self.assertTrue(all(c['timing'] == 'word' for c in captions))

    def test_complete_sentence_is_not_split_by_character_budget_or_pause(self):
        first = '先给结论：没有一种载体能对所有人、所有任务稳赢。'
        second = '关键是区分愿不愿意看、能不能看懂，以及之后能不能用。'
        text = first + second
        events = [{'start_ms': i*200+(900 if i>12 else 0),
                   'end_ms': i*200+(900 if i>12 else 0)+100,
                   'text': char, 'type': 'word'} for i, char in enumerate(text)]
        captions = core.make_captions(events, max_chars=22)
        self.assertEqual([c['text'].replace('\n', '') for c in captions], [first, second])
        self.assertFalse(any(c['text'] in ('赢。', '不能用。') for c in captions))

    def test_long_sentence_uses_two_balanced_lines_with_original_word_times(self):
        text = '一项涉及一百一十名工程学生的研究发现，用完整结论句配合视觉证据的幻灯片，比常规默认式设计带来更好的理解、较少误解，以及更强的延迟回忆。'
        events = [{'start_ms': i*100, 'end_ms': i*100+80,
                   'text': char, 'type': 'word'} for i, char in enumerate(text)]
        captions = core.make_captions(events, max_chars=36)
        self.assertEqual(len(captions), 1)
        self.assertEqual(captions[0]['text'].replace('\n', ''), text)
        self.assertEqual(len(captions[0]['text'].splitlines()), 2)
        self.assertLessEqual(max(map(len, captions[0]['text'].splitlines())), 36)
        self.assertEqual((captions[0]['start_ms'], captions[0]['end_ms']), (0, (len(text)-1)*100+80))

    def test_sentence_ending_with_closing_quote_is_a_boundary(self):
        captions = core.make_captions([
            {'start_ms': 0, 'end_ms': 100, 'text': '他说：', 'type': 'word'},
            {'start_ms': 100, 'end_ms': 500, 'text': '“先看结论。”', 'type': 'word'},
            {'start_ms': 500, 'end_ms': 900, 'text': '再看证据。', 'type': 'word'}])
        self.assertEqual([c['text'] for c in captions], ['他说：“先看结论。”', '再看证据。'])

    def test_captions_reject_overlapping_events_even_within_word_group(self):
        for kind in ('word', 'sentence', 'segment'):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'overlap'):
                core.make_captions([
                    {'start_ms': 0, 'end_ms': 100, 'text': '第一', 'type': kind},
                    {'start_ms': 90, 'end_ms': 200, 'text': '第二', 'type': kind}])

    def test_touching_caption_intervals_are_valid(self):
        captions = core.make_captions([
            {'start_ms': 100, 'end_ms': 200, 'text': '第二。', 'type': 'sentence'},
            {'start_ms': 0, 'end_ms': 100, 'text': '第一。', 'type': 'sentence'}])
        self.assertEqual([(c['start_ms'], c['end_ms']) for c in captions], [(0, 100), (100, 200)])

    def test_subtitle_formats_escape_only_ass_and_keep_safe_area(self):
        captions = [{'start_ms': 1234, 'end_ms': 3456, 'text': r'中国{\\标签}' + '\n第二行'}]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            core.write_srt(captions, root / 'a.srt')
            core.write_ass(captions, root / 'a.ass')
            srt = (root / 'a.srt').read_text(encoding='utf-8-sig')
            ass = (root / 'a.ass').read_text(encoding='utf-8-sig')
        self.assertIn('00:00:01,234 --> 00:00:03,456', srt)
        self.assertIn(r'中国{\\标签}', srt)
        self.assertIn(r'\{', ass)
        self.assertIn(r'\}', ass)
        self.assertIn(r'\N第二行', ass)
        self.assertIn('PlayResX: 1920', ass)
        self.assertIn('PlayResY: 1080', ass)
        self.assertIn(',72,', ass)


if __name__ == '__main__':
    unittest.main()
