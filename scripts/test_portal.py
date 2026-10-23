import unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PortalSmoke(unittest.TestCase):
    def test_portal(self):
        p=json.loads((ROOT/'dist/data/portal.json').read_text())
        self.assertEqual(p['schema_version'],'1.1.0')
        self.assertEqual(p['schema'],'static-portal/v1')
        self.assertTrue(p['hero_image_src'].startswith('data:image/webp;base64,'))
        self.assertIn('data-mode="portal"',(ROOT/'dist/index.html').read_text())
    def test_merged_only_external(self):
        p=json.loads((ROOT/'dist/data/portal.json').read_text())
        self.assertEqual(len(p['entries']),len(set(e['id'] for e in p['entries'])))
if __name__=='__main__':unittest.main()
