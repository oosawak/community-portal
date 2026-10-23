#!/usr/bin/env python3
"""Build an empty static portal, then merge remote feeds using merge_feeds.py."""
from pathlib import Path
import json, base64, shutil
from io import BytesIO
from PIL import Image, ImageOps
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'

def run():
    if DIST.exists():shutil.rmtree(DIST)
    (DIST/'assets').mkdir(parents=True)
    for name in ('app.js','style.css'):shutil.copy2(ROOT/'assets'/name,DIST/'assets'/name)
    with Image.open(ROOT/'assets/portal-hero.webp') as original:
        image=ImageOps.exif_transpose(original).convert('RGB')
        image.thumbnail((1540,1540),Image.Resampling.LANCZOS)
        buffer=BytesIO();image.save(buffer,format='WEBP',quality=82)
    hero='data:image/webp;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii')
    payload={'version':1,'schema':'static-portal/v1','schema_version':'1.1.0',
             'languages':['ja','en'],'sites':[],'entries':[],'hero_image_src':hero}
    (DIST/'data').mkdir()
    for name in ('portal.json','portal-local.json'):
        (DIST/'data'/name).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    page="""<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="安全なJSON連携で情報を集める静的ポータル"><meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'"><title>まちのつながり</title><link rel="stylesheet" href="assets/style.css"></head><body><div id="app" data-default="portal" data-root="./" data-mode="portal"><p class="loading">読み込み中…</p></div><noscript>JavaScriptを有効にしてください。</noscript><script src="assets/app.js" defer></script></body></html>"""
    (DIST/'index.html').write_text(page,encoding='utf8')
    print('Built empty portal shell; merge feeds next.')
if __name__=='__main__':run()
