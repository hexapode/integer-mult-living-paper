#!/usr/bin/env python3
"""Build an offline static reader and release assets from the paper's Pandoc AST."""
import argparse
import gzip
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit
from build import digest
from build_pdf import validate_pdf
from progress import progress_data, render_progress

ROOT=Path(__file__).resolve().parent
PUBLIC_REPO='hexapode/integer-mult-living-paper'


def clean_ast(value):
    if isinstance(value,list):
        return [clean_ast(x) for x in value]
    if not isinstance(value,dict):
        return value
    node={k:clean_ast(v) for k,v in value.items()}
    kind=node.get('t')
    if kind in ('RawInline','RawBlock'):
        return {'t':'Str','c':''} if kind=='RawInline' else {'t':'Para','c':[]}
    if kind in ('Link','Image'):
        attrs,label,target=node['c']
        url=target[0]
        try:
            safe=urlsplit(url).scheme.lower() in ('','http','https','mailto') and not any(ord(c)<32 for c in url)
        except ValueError:
            safe=False
        if not safe:
            return {'t':'Span','c':[['',[],[]],label]}
        node={'t':'Link','c':[['',[],[]],label,target]}
    # Pandoc supports author-supplied HTML attributes; drop them from the reader.
    if kind in ('Span','Div','Code','CodeBlock'):
        node['c'][0][2]=[]
    if kind=='Header':
        node['c'][1][2]=[]
    return node


def to_html(document):
    return subprocess.run(['pandoc','--from=json','--to=html5','--mathjax','--wrap=none'],
        input=json.dumps(clean_ast(document)),text=True,capture_output=True,check=True).stdout


class Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.depth=0;self.parts=[];self.number=None;self.pages={}
    def handle_starttag(self,tag,attrs):
        if tag=='div':
            if not self.depth:
                ident=dict(attrs).get('id','')
                if ident.startswith('contribution-'):
                    self.number=int(ident.split('-')[1]);self.depth=1;self.parts=[]
            else:
                self.depth+=1
        if self.depth:self.parts.append(self.get_starttag_text())
    def handle_endtag(self,tag):
        if self.depth:
            self.parts.append(f'</{tag}>')
            if tag=='div':
                self.depth-=1
                if not self.depth:self.pages[self.number]=''.join(self.parts)
    def handle_startendtag(self,tag,attrs):
        if self.depth:self.parts.append(self.get_starttag_text())
    def handle_data(self,data):
        if self.depth:self.parts.append(data)
    def handle_entityref(self,name):
        if self.depth:self.parts.append('&'+name+';')
    def handle_charref(self,name):
        if self.depth:self.parts.append('&#'+name+';')


def shell(title,body,prefix='',article=False,math=False):
    scripts=''
    if math:
        scripts='''<script>window.MathJax={loader:{load:['ui/safe']},tex:{inlineMath:[['\\\\(','\\\\)']],displayMath:[['\\\\[','\\\\]']]}};</script><script defer src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js"></script>'''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · Living paper</title><meta name="description" content="A versioned research paper on integer multiplication, with a complete contribution record."><link rel="stylesheet" href="{prefix}style.css">{scripts}</head><body><header><a class="brand" href="{prefix}index.html">INTEGER MULTIPLICATION / LIVING PAPER</a><nav><a href="{prefix}overview.html">Read the paper</a><a href="{prefix}paper.pdf">PDF</a><a href="{prefix}index.html#progress">Progress</a><a href="{prefix}index.html#contributions">Contributions</a><a href="https://github.com/{PUBLIC_REPO}/releases">Editions</a></nav></header><main class="{'article' if article else ''}">{body}</main><footer>A living research draft. GitHub contributors retain credit; inclusion does not imply endorsement. Claims retain their stated assumptions.<br><a href="https://github.com/{PUBLIC_REPO}">Publication source &amp; update workflow</a> · <a href="https://github.com/CrocSwap/integer-mult-bounds">Research repository</a></footer></body></html>'''


def build_site():
    source=ROOT/'output'; dest=ROOT/'_site';release=ROOT/'release'
    dest.mkdir(exist_ok=True);release.mkdir(exist_ok=True)
    (dest/'contributions').mkdir(exist_ok=True)
    pdf_metadata=validate_pdf(source)
    snap=json.loads((ROOT/'data/latest.json').read_text())
    progress=progress_data(snap)
    progress_html=render_progress(progress)
    (dest/'progress.json').write_text(json.dumps(progress,indent=2)+'\n')
    (release/'progress.json').write_text(json.dumps(progress,indent=2)+'\n')
    manifest=json.loads((source/'manifest.json').read_text())
    coverage=json.loads((source/'coverage.json').read_text())
    prs={p['number']:p for p in snap['prs']}
    selected=json.loads(snap['sources']['certificates/selected-result.json'])
    document=json.loads((source/'paper.ast.json').read_text())
    overview=to_html(json.loads((source/'overview.ast.json').read_text()))
    groups={};current=None
    for block in document['blocks']:
        if block.get('t')=='Header':
            level,attr,_=block['c']
            if level==2 and re.fullmatch(r'pr-\d+',attr[0]):
                current=int(attr[0][3:]);groups[current]=[]
            elif level==1:
                current=None
        if current is not None:groups[current].append(block)
    expected={p['pr'] for p in coverage}
    if set(groups)!=expected:raise ValueError('AST contribution coverage mismatch')
    wrapped=dict(document,blocks=[{'t':'Div','c':[[f'contribution-{n}',[],[]],blocks]} for n,blocks in groups.items()])
    all_html=to_html(wrapped)
    parser=Extract();parser.feed(all_html)
    if set(parser.pages)!=expected:raise ValueError('HTML contribution coverage mismatch')
    for n,body in parser.pages.items():
        body=re.sub(r'href="#pr-(\d+)"',r'href="pr-\1.html#pr-\1"',body)
        (dest/'contributions'/f'pr-{n}.html').write_text(shell(f'PR {n}: '+prs[n]['title'],body,'../',True,True))
    overview='<div class="actions"><a class="button primary" href="paper.pdf" download>Download the complete PDF</a><a class="button" href="paper.pdf">View PDF in browser</a></div>'+overview
    (dest/'overview.html').write_text(shell('The current argument',overview+progress_html,article=True,math=True))
    (dest/'complete.html').write_text(shell('Complete paper',overview+all_html,article=True,math=True))
    index=[dict(p,title=prs[p['pr']]['title']) for p in sorted(coverage,key=lambda p:p['pr'],reverse=True)]
    (dest/'contributions.json').write_text(json.dumps(index,ensure_ascii=False))
    credited=len(manifest['authors']);full=len(coverage);edited=sum(p['explanation']=='editorial-current' for p in coverage)
    edition=manifest.get('edition_id',manifest['snapshot_sha256'][:16])
    body=f'''<div class="eyebrow">A research programme, continuously documented</div><h1>Integer multiplication,<br>in motion.</h1><p class="intro">A living account of the mathematics, the evidence, and the people moving the frontier.</p><p class="muted">Source collection completed {html.escape(snap['finished_at'])} · Edition {edition}<br>Checks for changes every 30 minutes. GitHub scheduling can be delayed.</p><div class="actions"><a class="button primary" href="overview.html">Read the current account →</a><a class="button" href="paper.pdf" download>Download PDF · {pdf_metadata["pages"]:,} pages</a><a class="button" href="paper.tex" download>LaTeX source</a><a class="button" href="complete.html">Read all contributions</a></div><div class="stats"><div class="stat"><strong>{full:,}</strong><span>merged and open contributions</span></div><div class="stat"><strong>{credited}</strong><span>credited GitHub contributors</span></div><div class="stat"><strong>{edited}</strong><span>current editorial explanations</span></div></div><h2>One programme. Different kinds of evidence.</h2><p>The selected repository record reports conditional κ = <strong>{html.escape(selected.get('decimal','unspecified'))}</strong>. Larger numbers in submissions may represent candidates or partial calculations. Selection, publication and mathematical verification are separate events.</p><div class="note"><strong>A transparent draft.</strong> Every included PR has its submitted explanation. Deeper editorial explanations are counted separately. The automated refresh imports evidence and updates the manuscript; it does not independently prove or review results.</div>{progress_html}<section id="contributions"><h2>The contribution record</h2><p>Explore constructions, corrections, independent checks and negative results. Each page preserves credit and the exact submitted revision.</p><div class="controls"><input id="query" type="search" aria-label="Search contributions" placeholder="Search by topic, contributor or PR number"><select id="state" aria-label="Publication status"><option value="all">Merged + open</option><option value="merged">Merged</option><option value="open">Open</option></select></div><p id="count" class="muted" aria-live="polite">Loading contribution index…</p><div id="results"></div><div class="paging"><button id="previous" disabled>Previous</button><button id="next">Next</button></div><noscript><p>JavaScript is needed only for search. <a href="complete.html">Read the complete contribution record</a>.</p></noscript></section><h2>Citable editions, retained evidence</h2><p>Every published edition has an archived source snapshot, manuscript and build manifest. Earlier accounts remain available as the programme changes.</p><p><a href="https://github.com/{PUBLIC_REPO}/releases">Browse archived editions →</a> · <a href="manifest.json">Inspect this edition's manifest</a></p><script defer src="search.js"></script>'''
    (dest/'index.html').write_text(shell('Integer multiplication, in motion',body))
    for name in ('style.css','search.js'):shutil.copyfile(ROOT/'web'/name,dest/name)
    for name in ('paper.tex','paper.md','overview.tex','manifest.json','coverage.json','paper-pdf-manifest.json'):
        shutil.copyfile(source/name,dest/name)
        shutil.copyfile(source/name,release/name)
    shutil.copyfile(source/'paper.pdf',dest/'paper.pdf')
    shutil.copyfile(source/'paper.pdf',release/'paper.pdf')
    with gzip.GzipFile(filename=str(release/'snapshot.json.gz'),mode='wb',mtime=0) as stream:
        stream.write((ROOT/'data/latest.json').read_bytes())
    (dest/'.nojekyll').write_text('')
    (release/'notes.md').write_text(f'Living paper edition {edition}.\n\n{full} merged/open contributions; {edited} current editorial explanations.\n\nSnapshot completed {snap["finished_at"]}; upstream main `{snap["main_commit"]}`.\n\nMerge status is not mathematical verification.\n')
    print(f'Built site with {len(parser.pages)} contribution pages.')


def prepare():
    subprocess.run(['python3',str(ROOT/'build.py'),'refresh'],check=True)
    snap=json.loads((ROOT/'data/latest.json').read_text())
    inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob('*.py'))}
    inputs['frontier-seed.json']=hashlib.sha256((ROOT/'frontier-seed.json').read_bytes()).hexdigest()
    inputs.update({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                   for folder in ['editorial','web','.github'] for p in sorted((ROOT/folder).rglob('*')) if p.is_file()})
    key=digest({'snapshot':{k:snap[k] for k in ['repo','main_commit','prs','sources','contributors','frontier_history']},'inputs':inputs})[:16]
    tag='edition-'+key
    exists=subprocess.run(['gh','api',f'repos/{PUBLIC_REPO}/releases/tags/{tag}'],capture_output=True,text=True)
    if exists.returncode and '404' not in exists.stderr:raise RuntimeError(exists.stderr)
    should_build=exists.returncode!=0
    with open(os.environ['GITHUB_OUTPUT'],'a') as stream:
        stream.write(f'publish={str(should_build).lower()}\ntag={tag}\nedition={key}\n')
    (ROOT/'data/edition-id.txt').write_text(key)
    print(f'{tag}: '+('building new edition' if should_build else 'already published; no changes'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','site'])
    args=parser.parse_args()
    if args.command=='prepare':prepare()
    else:
        edition=ROOT/'data/edition-id.txt'
        if edition.exists():
            manifest=ROOT/'output/manifest.json';value=json.loads(manifest.read_text())
            value['edition_id']=edition.read_text().strip();manifest.write_text(json.dumps(value,indent=2)+'\n')
        build_site()
