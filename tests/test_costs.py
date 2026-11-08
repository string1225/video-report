import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/video-report/scripts'))


class CostSummaryTests(unittest.TestCase):
    def test_cached_voice_and_unknown_model_bill_are_reported_separately(self):
        self.assertIsNotNone(importlib.util.find_spec('report_costs'), 'Run cost reporting is missing')
        from report_costs import summarize_run_costs
        manifest = {'scenes': [{'provider': 'edge-tts', 'cache': [
            {'hit': True, 'spoken': '缓存旁白。'}]}]}
        result = summarize_run_costs(manifest, 25.5, {'encode': 20}, 12345)
        self.assertEqual(result['audio']['cache_hits'], 1)
        self.assertEqual(result['audio']['new_synthesis_characters'], 0)
        self.assertEqual(result['direct_external_service_cost_cny'], 0)
        self.assertIsNone(result['model_cost_cny'])
        self.assertIsNone(result['total_cost_cny'])
        self.assertEqual(result['build_elapsed_seconds'], 25.5)

    def test_new_synthesis_units_are_not_confused_with_cached_audio(self):
        self.assertIsNotNone(importlib.util.find_spec('report_costs'), 'Run cost reporting is missing')
        from report_costs import summarize_run_costs
        manifest = {'scenes': [{'provider': 'edge-tts', 'cache': [
            {'hit': True, 'spoken': '已有'}, {'hit': False, 'spoken': '新增旁白。'}]}]}
        result = summarize_run_costs(manifest, 12, {}, 999)
        self.assertEqual(result['audio']['new_synthesis_units'], 1)
        self.assertEqual(result['audio']['new_synthesis_characters'], 5)


if __name__ == '__main__':
    unittest.main()
