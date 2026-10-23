#!/usr/bin/env python3
"""Strictly validated federated JSON feeds. Untrusted remote JSON is data, never executable HTML.

Security boundaries:
- Each feed must be explicitly configured with a site ID and permitted HTTPS hosts.
- Outbound requests reject redirect, credentials, non-443 ports and internal DNS destinations.
- Schema/version, fields, UTF-8, image bytes, and link destinations are checked.
- Only allowlisted display fields enter the final portal JSON.
- A validated last-good cache survives a failed fetch. Invalid cache is ignored.
"""
from __future__ import annotations
import base64, binascii, hashlib, ipaddress, json, os, re, socket
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
CACHE=ROOT/'cache/feeds'
MAX_FEED_BYTES=4_000_000
MAX_ITEMS=100
MAX_THUMB_BYTES=150_000
SCHEMA='static-site-feed/v1'
SUPPORTED_MINOR=1
SITE_ID=re.compile(r'^[a-z0-9_-]{2,64}$')
SLUG=re.compile(r'^[a-z0-9_-]{1,100}$')
DATA_URI=re.compile(r'^data:image/webp;base64,([A-Za-z0-9+/]+={0,2})$')

class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError('HTTP redirect is forbidden for federation feeds')


def safe_https(raw: str, allowed_hosts: list[str], *, resolve=True) -> str:
    if not isinstance(raw,str) or len(raw)>2048 or re.search(r'[\x00-\x20\x7f]',raw):
        raise ValueError('unsafe URL')
    p=urlsplit(raw)
    if p.scheme!='https' or p.username or p.password or not p.hostname or p.port not in (None,443):
        raise ValueError('HTTPS URL without credentials or custom ports required')
    if p.hostname.lower() not in allowed_hosts:
        raise ValueError('URL host is not allowlisted')
    if not p.path.startswith('/'):
        raise ValueError('URL must use an absolute path')
    if resolve:
        try:
            infos=socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)
        except socket.gaierror as ex:
            raise ValueError('DNS resolution failed') from ex
        if not infos:raise ValueError('DNS returned no addresses')
        for info in infos:
            addr=ipaddress.ip_address(info[4][0])
            if not addr.is_global:
                raise ValueError('DNS points to non-public IP address')
    return raw


def limits(value: object, label: str, maximum: int, *, empty=False) -> str:
    if not isinstance(value,str) or len(value)>maximum or (not empty and not value.strip()):
        raise ValueError(f'{label}: invalid or oversize string')
    if any(ord(c)<32 and c not in '\n\t' for c in value):
        raise ValueError(f'{label}: control character')
    return value


def webp_cover(cover: object) -> dict:
    if not isinstance(cover,dict):raise ValueError('cover must be object')
    if cover.get('mime')!='image/webp':raise ValueError('only WebP cover images are supported')
    src=limits(cover.get('src'),'cover.src',220_000)
    m=DATA_URI.fullmatch(src)
    if not m:raise ValueError('cover must be a base64 WebP data URI')
    try:
        raw=base64.b64decode(m.group(1),validate=True)
    except (ValueError,binascii.Error) as ex:
        raise ValueError('invalid base64 cover') from ex
    if not 30<=len(raw)<=MAX_THUMB_BYTES or raw[:4]!=b'RIFF' or raw[8:12]!=b'WEBP' or int.from_bytes(raw[4:8],'little')+8!=len(raw):
        raise ValueError('invalid WebP bytes or oversized cover')
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format!='WEBP' or image.width<1 or image.height<1 or image.width*image.height>4_000_000:
                raise ValueError('WebP dimensions are invalid')
            image.verify()
    except (OSError,UnidentifiedImageError) as ex:
        raise ValueError('corrupt WebP image') from ex
    return {'src':src,'mime':'image/webp','alt':limits(cover.get('alt',''),'cover.alt',200,empty=True)}


def feed_version(payload):
    if payload.get('schema')!=SCHEMA or payload.get('version')!=1:
        raise ValueError('unsupported major feed version')
    version=payload.get('schema_version','1.0.0')
    if not isinstance(version,str) or not re.fullmatch(r'1\.(0|1)\.\d+',version):
        raise ValueError('unsupported schema_version; expected 1.0.x or 1.1.x')
    return version


def normalized_feed(payload: object, source: dict, *, resolve_urls=True) -> dict:
    if not isinstance(payload,dict):raise ValueError('feed must be an object')
    version=feed_version(payload)
    expected=source['id']
    allowed=source['allowed_hosts']
    site=payload.get('site')
    if not isinstance(site,dict) or site.get('id')!=expected or not SITE_ID.fullmatch(expected):
        raise ValueError('feed site ID must match the configured site ID')
    site_name=limits(site.get('name'),'site.name',120)
    homepage=safe_https(source['homepage'],allowed,resolve=resolve_urls)
    site_clean={'id':expected,'name':site_name,
                'kind':limits(site.get('kind','media'),'site.kind',40),
                'kind_label':limits(site.get('kind_label','External'),'site.kind_label',50),
                'description':limits(site.get('description',''),'site.description',400,empty=True),
                'subtitle':limits(site.get('subtitle',''),'site.subtitle',160,empty=True),
                'home_url':homepage,'external':True}
    if site.get('hero_thumbnail'):
        site_clean['hero_image_src']=webp_cover(site['hero_thumbnail'])['src']
    entries=payload.get('entries')
    if not isinstance(entries,list) or len(entries)>MAX_ITEMS:raise ValueError('too many entries')
    seen=set();clean=[]
    for item in entries:
        if not isinstance(item,dict):raise ValueError('entry must be object')
        slug=item.get('slug')
        if not isinstance(slug,str) or not SLUG.fullmatch(slug):raise ValueError('invalid slug')
        key=f'{expected}:{slug}'
        if item.get('id')!=key or item.get('site_id')!=expected or key in seen:
            raise ValueError('duplicate or mismatched item ID')
        seen.add(key)
        kind=item.get('type')
        if kind not in ('article','product'):raise ValueError('invalid item type')
        pub=limits(item.get('date'),'date',10)
        try:
            if date.fromisoformat(pub).isoformat()!=pub:raise ValueError()
        except ValueError as ex:raise ValueError('invalid ISO date') from ex
        url=safe_https(item.get('url'),allowed,resolve=resolve_urls)
        entry={
          'id':key,'site_id':expected,'site_name':site_name,'site_kind':site_clean['kind'],
          'slug':slug,'type':kind,'date':pub,
          'title':limits(item.get('title'),'title',180),
          'summary':limits(item.get('summary'),'summary',600,empty=True),
          'category':limits(item.get('category','その他'),'category',80),
          'url':url,'cover':webp_cover(item.get('cover')),
          'external':True,
        }
        if kind=='product':
            price=item.get('price_jpy')
            if isinstance(price,bool) or not isinstance(price,int) or not 0<=price<=100000000:
                raise ValueError('invalid price_jpy')
            entry.update({'price_jpy':price,'unit':limits(item.get('unit'),'unit',80),
                          'stock':limits(item.get('stock'),'stock',80)})
        # Translation content is strictly plain text. Never accept html, markdown or scripts.
        overlay=item.get('i18n',{})
        if overlay:
            if not isinstance(overlay,dict):raise ValueError('i18n invalid')
            en=overlay.get('en',{})
            if not isinstance(en,dict):raise ValueError('i18n.en invalid')
            valid={'title':180,'summary':600,'category':80,'site_name':120,'stock':80,'unit':80}
            entry['i18n']={'en':{k:limits(en[k],f'i18n.en.{k}',m,empty=k=='summary') for k,m in valid.items() if k in en}}
        clean.append(entry)
    return {'version':1,'schema':SCHEMA,'schema_version':version,'site':site_clean,'entries':clean}


def configured_sources(root=ROOT):
    config=json.loads((root/'data/sources.json').read_text(encoding='utf-8'))
    sources=config.get('sources',[])
    if not isinstance(sources,list) or len(sources)>20:raise ValueError('invalid source count')
    seen=set()
    for src in sources:
        if not isinstance(src,dict) or not SITE_ID.fullmatch(str(src.get('id',''))):raise ValueError('invalid source ID')
        if src['id'] in seen:raise ValueError('duplicate source ID')
        seen.add(src['id'])
        hosts=src.get('allowed_hosts')
        if not isinstance(hosts,list) or not hosts or len(hosts)>4 or any(not isinstance(h,str) or h!=h.lower() or not re.fullmatch(r'[a-z0-9.-]{4,250}',h) for h in hosts):
            raise ValueError('configure explicit lowercase allowed_hosts for each source')
        safe_https(src.get('url'),hosts,resolve=False)
        safe_https(src.get('homepage'),hosts,resolve=False)
    return sources


def fetch_live(source:dict, *,opener=None) -> dict:
    safe_https(source['url'],source['allowed_hosts'])
    client=opener or build_opener(HTTPSHandler(),RejectRedirect())
    req=Request(source['url'],headers={'User-Agent':'StaticJSONFederation/1.1','Accept':'application/json','Accept-Encoding':'identity'})
    with client.open(req,timeout=12) as response:
        if response.status!=200:raise ValueError(f'HTTP {response.status}')
        raw=response.read(MAX_FEED_BYTES+1)
    if len(raw)>MAX_FEED_BYTES:raise ValueError('feed exceeds limit')
    try:payload=json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError,json.JSONDecodeError) as ex:raise ValueError('invalid UTF-8 JSON') from ex
    return normalized_feed(payload,source)


def cache_path(source,base=CACHE) -> Path:
    key=json.dumps({k:source[k] for k in ('id','url','homepage','allowed_hosts')},sort_keys=True)
    return base/(hashlib.sha256(key.encode()).hexdigest()+'.json')


def atomic_save(path:Path,payload:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    os.replace(temp,path)


def load_cache(path,source):
    if not path.is_file() or path.stat().st_size>MAX_FEED_BYTES:raise ValueError('no valid cached feed')
    return normalized_feed(json.loads(path.read_text(encoding='utf-8')),source,resolve_urls=False)


def merge(local,feeds):
    sites={s['id']:s for s in local['sites']}
    entries={i['id']:i for i in local['entries']}
    for feed in feeds:
        sid=feed['site']['id']
        if sid in sites:raise ValueError('external feed tried to reuse an existing site ID')
        if any(i['id'] in entries for i in feed['entries']):raise ValueError('external entry ID conflicts with local portal')
        sites[sid]=feed['site']
        entries.update({i['id']:i for i in feed['entries']})
    return {**local,'schema_version':'1.1.0','sites':list(sites.values()),
            'entries':sorted(entries.values(),key=lambda x:(x['date'],x['id']),reverse=True)}


def run():
    sources=configured_sources()
    local=json.loads((DIST/'data/portal-local.json').read_text(encoding='utf-8'))
    feeds=[]
    for source in sources:
        sid=source['id'];path=cache_path(source)
        try:
            data=fetch_live(source)
            atomic_save(path,data)
            print('Fetched:',sid,len(data['entries']))
        except Exception as ex:
            print('Fetch failed:',sid,ex)
            try:
                data=load_cache(path,source)
                print('Using validated cached feed:',sid)
            except Exception as cache_ex:
                print('No usable cached feed:',sid,cache_ex)
                continue
        if any(s['id']==sid for s in local['sites']):
            print('Skipping source with local site ID:',sid)
            continue
        feeds.append(data)
    portal=merge(local,feeds)
    atomic_save(DIST/'data/portal.json',portal)
    print('Portal:',len(portal['sites']),'sites,',len(portal['entries']),'entries')

if __name__=='__main__':run()
