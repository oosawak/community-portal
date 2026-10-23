"""Adversarial tests for the federated JSON trust boundary; no network required."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import merge_feeds as m

ROOT=Path(__file__).resolve().parents[1]
SRC=json.loads((ROOT/'data/fixtures/partner-source.json').read_text(encoding='utf-8'))
GOOD=json.loads((ROOT/'data/fixtures/partner-feed.json').read_text(encoding='utf-8'))

class FederationSecurityTest(unittest.TestCase):
    def parse(self,payload=None,source=None):
        return m.normalized_feed(copy.deepcopy(payload or GOOD),copy.deepcopy(source or SRC),resolve_urls=False)

    def test_v11_feed_normalized_to_plain_data(self):
        f=self.parse()
        self.assertEqual(f['site']['id'],'partner-town')
        self.assertTrue(f['entries'][0]['external'])
        self.assertNotIn('html',f['entries'][0])
        self.assertEqual(f['entries'][0]['url'],'https://partner.example.org/posts/autumn-day/')

    def test_old_v10_feed_supported(self):
        x=copy.deepcopy(GOOD);x.pop('schema_version')
        self.assertEqual(self.parse(x)['schema_version'],'1.0.0')

    def test_v2_feed_rejected(self):
        x=copy.deepcopy(GOOD);x['schema_version']='2.0.0'
        with self.assertRaises(ValueError):self.parse(x)

    def test_mismatched_site_and_entry_rejected(self):
        x=copy.deepcopy(GOOD);x['site']['id']='bakery'
        with self.assertRaises(ValueError):self.parse(x)
        x=copy.deepcopy(GOOD);x['entries'][0]['id']='partner-town:evil'
        with self.assertRaises(ValueError):self.parse(x)

    def test_xss_and_untrusted_html_are_not_included_in_result(self):
        x=copy.deepcopy(GOOD)
        x['entries'][0]['title']='<img src=x onerror=alert(1)>'
        x['entries'][0]['html']='<script>alert(1)</script>'
        data=self.parse(x)
        self.assertNotIn('html',data['entries'][0]);self.assertIn('<img',data['entries'][0]['title'])
        # Escaping is performed by the UI. The malicious HTML field itself is dropped.
        script=(ROOT/'assets/app.js').read_text(encoding='utf-8')
        self.assertIn('h(it.title)',script)

    def test_remote_https_links_only(self):
        for url in ['http://partner.example.org/a','javascript:alert(1)','https://localhost/x',
                    'https://evil.example.org/x','https://user:pass@partner.example.org/x',
                    'https://partner.example.org:9443/x','https://partner.example.org/a\nX:yes']:
            x=copy.deepcopy(GOOD);x['entries'][0]['url']=url
            with self.subTest(url=url),self.assertRaises(ValueError):self.parse(x)

    def test_webp_invalid_and_oversized(self):
        for data in ['data:image/svg+xml;base64,PD94bWw+','data:image/webp;base64,SGVsbG8=',
                     'data:image/webp;base64,!!notbase64!!']:
            x=copy.deepcopy(GOOD);x['entries'][0]['cover']['src']=data
            with self.subTest(data=data[:30]),self.assertRaises(ValueError):self.parse(x)
        x=copy.deepcopy(GOOD);x['entries'][0]['cover']['src']='data:image/webp;base64,'+'A'*220004
        with self.assertRaises(ValueError):self.parse(x)

    def test_feed_length_and_duplicate_ids(self):
        x=copy.deepcopy(GOOD);x['entries']=x['entries']*101
        with self.assertRaises(ValueError):self.parse(x)
        x=copy.deepcopy(GOOD);x['entries']=x['entries']*2
        with self.assertRaises(ValueError):self.parse(x)

    def test_private_dns_response_is_rejected(self):
        with patch('merge_feeds.socket.getaddrinfo',return_value=[(None,None,None,None,('127.0.0.1',443))]):
            with self.assertRaisesRegex(ValueError,'non-public'):
                m.safe_https('https://partner.example.org/data.json',['partner.example.org'])

    def test_redirect_rejected(self):
        with self.assertRaisesRegex(ValueError,'redirect'):
            m.RejectRedirect().redirect_request(None,None,302,'Found',None,'https://evil.org/')

    def test_production_html_has_restrictive_csp(self):
        html=(ROOT/'dist/index.html').read_text(encoding='utf-8')
        self.assertIn('Content-Security-Policy',html)
        self.assertIn('script-src &#x27;self&#x27;' if 'script-src &#x27;self&#x27;' in html else "script-src 'self'",html)

    def test_last_good_cache_validation(self):
        feed=self.parse()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cache.json'
            m.atomic_save(path,feed)
            self.assertEqual(m.load_cache(path,SRC)['site']['id'],'partner-town')
            path.write_text('{"oops": true}',encoding='utf-8')
            with self.assertRaises(ValueError):m.load_cache(path,SRC)

    def test_merge_keeps_local_and_adds_external(self):
        local={'schema':'static-portal/v1','version':1,'sites':[{'id':'bakery'}],
               'entries':[{'id':'bakery:hello','date':'2026-10-01'}], 'languages':['ja','en']}
        merged=m.merge(local,[self.parse()])
        self.assertEqual(len(merged['sites']),2)
        self.assertEqual(len(merged['entries']),2)
        self.assertEqual(merged['schema_version'],'1.1.0')
        with self.assertRaises(ValueError):m.merge(local,[self.parse(),self.parse()])

if __name__=='__main__':unittest.main()
