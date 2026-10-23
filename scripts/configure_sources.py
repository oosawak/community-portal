#!/usr/bin/env python3
"""Configure 4 independent GitHub Pages HTTPS JSON sources."""
import argparse,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Configure four public static JSON site feeds')
parser.add_argument('--owner',required=True,help='GitHub account/organization name')
parser.add_argument('--bakery',default='haru-no-tane-bakery')
parser.add_argument('--town',default='midorino-town')
parser.add_argument('--fruit',default='kajitsu-biyori')
parser.add_argument('--gourmet',default='yamagata-gourmet')
args=parser.parse_args()
owner=args.owner.lower()
if not re.fullmatch(r'[a-z\d-]{1,39}',owner) or owner[0]=='-' or owner[-1]=='-':
    parser.error('Invalid GitHub owner')
results=[]
for sid in ('bakery','town','fruit','gourmet'):
    repo=getattr(args,sid)
    if not re.fullmatch(r'[A-Za-z\d_.-]+',repo):parser.error('Invalid repo name: '+repo)
    path=f'/{repo}/' if repo.lower()!=owner+'.github.io' else '/'
    homepage=f'https://{owner}.github.io{path}'
    results.append({'id':sid,'homepage':homepage,'url':homepage+f'data/sites/{sid}.json',
                    'allowed_hosts':[f'{owner}.github.io']})
path=ROOT/'data/sources.json'
path.write_text(json.dumps({'sources':results},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('Updated',path)
for s in results:print(s['id'],s['url'])
