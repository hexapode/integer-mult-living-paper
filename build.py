#!/usr/bin/env python3
"""Reproducible, source-bound living research paper. Python stdlib + gh + pandoc."""
import argparse
import collections
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path
from progress import fetch_history

ROOT = Path(__file__).resolve().parent
REPO = 'CrocSwap/integer-mult-bounds'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def run(args):
    return subprocess.check_output(args, text=True)


def api(path, pages=False, raw=False):
    cmd = ['gh', 'api', path]
    if pages:
        cmd += ['--paginate', '--slurp']
    if raw:
        return run(cmd + ['-H', 'Accept: application/vnd.github.raw+json'])
    return json.loads(run(cmd))


def flatten(pages):
    return [item for page in pages for item in page]


def compact(pr):
    user = pr.get('user') or {}
    return {
        'number': pr['number'], 'title': pr['title'], 'body': pr.get('body') or '',
        'author': user.get('login', 'ghost'), 'author_type': user.get('type', 'User'),
        'state': 'merged' if pr.get('merged_at') else pr['state'],
        'created_at': pr['created_at'], 'updated_at': pr['updated_at'],
        'merged_at': pr.get('merged_at'), 'url': pr['html_url'],
        'head': pr['head']['sha'], 'base': pr['base']['sha'],
        'head_repo': (pr['head'].get('repo') or {}).get('full_name'),
        'merge_commit': pr.get('merge_commit_sha'),
    }


def refresh(args):
    started = now()
    repo = args.repo
    metadata = api(f'repos/{repo}')
    commit = api(f'repos/{repo}/commits/{metadata["default_branch"]}')['sha']
    pages = json.loads(args.import_pages.read_text()) if args.import_pages else api(
        f'repos/{repo}/pulls?state=all&per_page=100&sort=created&direction=asc', pages=True)
    prs = sorted({p['number']: compact(p) for p in flatten(pages)}.values(), key=lambda p:p['number'])
    contributors = flatten(api(f'repos/{repo}/contributors?per_page=100', pages=True))
    sources = {}
    paths = ['README.md', 'CONTRIBUTORS.md', 'certificates/selected-result.json',
             'docs/research/current-status.md', 'docs/research/pr-ledger.md',
             'docs/research/bottleneck-brief.md', 'docs/research/research-glossary.md']
    for path in paths:
        sources[path] = api(f'repos/{repo}/contents/{path}?ref={commit}', raw=True)
    selected = json.loads(sources['certificates/selected-result.json'])
    review = selected.get('review') or selected.get('proof')
    if isinstance(review, str) and review not in sources:
        sources[review] = api(f'repos/{repo}/contents/{review}?ref={commit}', raw=True)
    snapshot = {'schema': 1, 'repo': repo, 'started_at': started, 'finished_at': now(),
                'main_commit': commit, 'prs': prs, 'sources': sources,
                'frontier_history': fetch_history(repo, commit, api),
                'contributors': [{'login': p['login'], 'type': p['type']} for p in contributors],
                'collection': 'Imported REST pages' if args.import_pages else 'Live paginated REST pull requests'}
    args.data.mkdir(parents=True, exist_ok=True)
    latest = args.data / 'latest.json'
    previous = json.loads(latest.read_text()) if latest.exists() else None
    old = {p['number']: p for p in previous['prs']} if previous else {}
    changes = {'at': snapshot['finished_at'], 'previous_snapshot': digest(previous) if previous else None,
               'added': [p['number'] for p in prs if p['number'] not in old],
               'changed': [p['number'] for p in prs if p['number'] in old and digest(p) != digest(old[p['number']])],
               'missing_since_previous': sorted(set(old) - {p['number'] for p in prs})}
    # Retain immutable editions; never silently discard old source evidence.
    edition = args.data / ('snapshot-' + digest(snapshot)[:16] + '.json')
    edition.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    temp = latest.with_suffix('.tmp')
    temp.write_text(edition.read_text())
    temp.replace(latest)
    with (args.data / 'changes.jsonl').open('a') as f:
        f.write(json.dumps(changes) + '\n')
    print(f'Snapshotted {len(prs)} PRs at main {commit}; {len(changes["changed"])} changed.')


def text(value):
    # Prevent metadata from creating Markdown sections or TeX commands.
    return re.sub(r'([\\`*_{}\[\]<>#$|])', r'\\\1', str(value).replace('\n', ' '))


def source_body(body, pr, repo):
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
    # Remote assets are links, never fetched during a reproducible build.
    body = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'[Figure: \1](\2)', body)
    # Demote headings under the contribution section, outside fenced code.
    lines, fenced = [], False
    for line in body.splitlines():
        if re.match(r'^\s*(```|~~~)', line):
            fenced = not fenced
        if not fenced:
            line = re.sub(r'^#{1,6}\s+(.+)$', r'**\1**', line)
        lines.append(line)
    body = '\n'.join(lines)
    def link(match):
        label, url = match.groups()
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', url) or url.startswith('#'):
            return match.group(0)
        target = f'https://github.com/{pr.get("head_repo") or repo}/blob/{pr["head"]}/{url.lstrip("/")}'
        return f'[{label}]({target})'
    return re.sub(r'\[([^\]]+)\]\(([^\s)]+)\)', link, body).strip()


def category(pr):
    title = pr['title'].lower()
    for name, pattern in [
        ('Verification, corrections, and reproducibility', r'audit|verif|replay|correct|fix|counterexample|proof'),
        ('Obstructions and negative results', r'barrier|obstruction|lower bound|no.go|reject|infeasib|ceiling'),
        ('Constructions and quantitative improvements', r'κ|kappa|packing|construct|supplier|circuit|saving|frontier'),
        ('Research infrastructure and coordination', r'doc|tool|intake|ledger|workflow|task|research direction')]:
        if re.search(pattern, title):
            return name
    return 'Additional mathematical investigations'


def excerpt(body):
    clean = re.sub(r'<!--.*?-->', '', body, flags=re.S)
    paragraphs = re.split(r'\n\s*\n', clean)
    for para in paragraphs:
        para = para.strip()
        if len(para) > 100 and not para.startswith(('#', '```', '|', '- [', '<')):
            # Exact source excerpt, explicitly attributed; never invent a finding.
            return para
    return ''


def render(args):
    snap = json.loads(args.snapshot.read_text())
    all_prs = snap['prs']
    prs = [p for p in all_prs if p['state'] in ('merged', 'open')]
    repo = snap['repo']
    selected = json.loads(snap['sources']['certificates/selected-result.json'])
    authors = sorted({p['author'] for p in prs if p['author_type'] != 'Bot'} |
                     {c['login'] for c in snap['contributors'] if c['type'] != 'Bot'}, key=str.lower)
    counts = collections.Counter(p['state'] for p in prs)
    groups = collections.defaultdict(list)
    for pr in prs:
        groups[category(pr)].append(pr)
    args.output.mkdir(parents=True, exist_ok=True)
    args.editorial.mkdir(parents=True, exist_ok=True)
    coverage, stale = [], []
    front = f'''---
title: "Integer Multiplication as a Living Research Programme"
subtitle: "A versioned research survey and complete contribution record"
author: "The integer-mult-bounds GitHub contributors"
date: "{snap['finished_at']}"
documentclass: report
classoption: [11pt, oneside]
geometry: margin=1in
colorlinks: true
---

# Authorship and edition

**GitHub contributors:** {', '.join(text(a) for a in authors)}.

Authorship is attributed automatically to non-bot GitHub repository contributors and
PR authors in the included corpus. Handles are preserved rather than guessing names.
This is a draft attribution policy, not evidence that contributors approved this
manuscript. Individual contribution sections retain their PR authors. Commit
coauthors, reviewers, and non-GitHub antecedents may require additional credit;
the pinned CONTRIBUTORS record is retained in the source snapshot.

Edition `{digest(snap)[:16]}`; repository [{repo}](https://github.com/{repo});
main commit `{snap['main_commit']}`.

# Abstract

We organize a collaborative investigation of the exponent saving in integer
multiplication into a versioned research survey. This edition includes all
{len(prs)} merged and open pull requests observed in the source collection:
{counts['merged']} merged contributions and {counts['open']} open proposals.
The mathematical setting is the conditional bound
$T(n)=O(n(\\log n)^{{1-\\kappa}})$.
The selected repository record reports $\\kappa={selected.get('kappa', 'not specified')}$.
This value is an exponent saving, not a runtime measurement. Each contribution
has a stable identifier, source revision, publication status, and its complete
available PR description. The paper distinguishes repository selection,
experimental evidence, and proposed claims. Its source-derived contribution
record is complete for this snapshot; mathematical editorial synthesis remains
a separate, explicitly tracked layer.

# What a living research paper asserts

A research paper is an argument supported by evidence. In an automated research
programme, submissions arrive faster than that argument can safely be rewritten.
We therefore separate the current mathematical account from the history of
contributions. A change to a PR updates its evidence record; it does not silently
promote a claimed result into a theorem. A merged archive may remain only
partially reviewed. Failed searches and scoped obstructions belong in the account
because they explain which avenues remain plausible and which hypotheses matter.

The unit of explanation is a contribution: the question it addresses, the mechanism
it changes, the evidence it offers, its scope, and its relationship to earlier work.
Source text supplies the first draft of this explanation. Editorial notes can
provide a fuller mathematical account without overwriting contributor testimony.
Every editorial note is bound to a source fingerprint and marked stale if that
source changes. Frozen editions make the evolving account citable.

# Mathematical setting and selected result

The project studies how finite bit and complex primitives support a recursive
integer multiplication algorithm under retained framework assumptions. Primitive
cost, scheduling, workspace restoration, and transfer to the outer algorithm
are separate obligations. A better local construction need not improve the final
exponent when a different primitive or transfer condition is limiting.

The following is the repository's selected record at the pinned main revision,
not the largest number found in a PR title:

```json
{json.dumps({k: selected[k] for k in ['status', 'kappa', 'decimal', 'proof', 'reproduce'] if k in selected}, ensure_ascii=False, indent=2)}
```

Selection is reported from the repository; this paper generator does not replay
certificates or independently prove the multiplication bound.

# How to read the contribution record

Every merged or open PR receives a section below, ordered by PR number within
broad navigational themes. Theme assignment is a title-based heuristic, not a
scientific classification or ranking. The complete available body is included,
with headings normalized and figures linked rather than fetched. Equations and
code are preserved through Pandoc. An empty body is disclosed as an explanation
gap. An attributed opening passage provides orientation where available; it is
not presented as an independently verified summary.

Open contributions remain proposals. Merged contributions remain subject to the
pinned review ledger and their stated assumptions. Neither status alone establishes
correctness. Source references within a PR retain the contributor's attribution.
This edition does not fetch discussion comments, reviews, diffs, or linked artifacts;
claims depending on those sources need further editorial investigation.

PR pages were collected over an interval, not an atomic GitHub transaction.
Collection metadata: {text(snap['collection'])}; {text(snap['started_at'])} to
{text(snap['finished_at'])}. Closed, unmerged PRs are retained in the snapshot but
excluded from this edition's requested merged/open corpus. Earlier editions retain
contributions that subsequently leave that corpus.

# Research programme at this edition

'''
    for name, members in sorted(groups.items()):
        merged = sum(p['state']=='merged' for p in members)
        front += f'- **{name}:** {len(members)} contributions ({merged} merged, {len(members)-merged} open).\n'
    story = args.editorial / 'narrative.md'
    if story.exists():
        binding = args.editorial / 'narrative-sources.json'
        narrative_current = False
        if binding.exists():
            bound = json.loads(binding.read_text())
            by_number = {str(p['number']): digest(p) for p in prs}
            narrative_current = (bound.get('selected_sha256') == digest(selected) and
                all(by_number.get(n) == fingerprint for n, fingerprint in bound.get('prs', {}).items()))
        notice = ('Source bindings are current; this is editorial interpretation, not independent verification.'
                  if narrative_current else 'Historical editorial narrative: its source bindings require review. Use the selected record above for the current result.')
        front += '\n# Editorial synthesis\n\n**' + notice + '**\n\n' + story.read_text() + '\n'

    else:
        front += '\nThe cross-contribution editorial narrative has not yet been written. The following\nchapters provide source-attributed explanations and expose that unfinished work\nrather than fabricating a unified proof.\n'
    chapters = []
    for name, members in sorted(groups.items()):
        chapter = f'\n# {name}\n\n'
        for p in members:
            fingerprint = digest(p)
            note = args.editorial / f'pr-{p["number"]}.json'
            chapter += f'\n## PR {p["number"]}: {text(p["title"])} {{#pr-{p["number"]}}}\n\n'
            chapter += f'**Contributor:** {text(p["author"])}. **Publication status:** {p["state"]}. '
            chapter += f'[Original contribution]({p["url"]}).\n\n'
            chapter += f'Created {p["created_at"]}.  \nUpdated {p["updated_at"]}.  \n'
            chapter += f'Head revision `{p["head"]}`.\n\n'
            status = 'source-only'
            if note.exists():
                annotation = json.loads(note.read_text())
                fresh = annotation.get('source_sha256') == fingerprint
                status = 'editorial-current' if fresh else 'editorial-stale'
                if not fresh:
                    stale.append(p['number'])
                chapter += '**Editorial explanation' + ('' if fresh else ' — stale: source changed') + '.**\n\n'
                chapter += annotation['explanation_markdown'] + '\n\n'
            else:
                quote = excerpt(p['body'])
                if quote:
                    chapter += '**Orientation, in the contributor’s words.**\n\n'
                    chapter += '\n'.join('> ' + line for line in source_body(quote,p,repo).splitlines()) + '\n\n'
            chapter += '**Complete submitted explanation.**\n\n'
            chapter += source_body(p['body'], p, repo) if p['body'].strip() else (
                'No PR description was supplied. A mathematical explanation requires examining '
                'the linked patch and associated artifacts; the title alone is insufficient.')
            chapter += '\n\n**Evidence boundary.** This section reports the submitted contribution. '
            chapter += 'Merge status does not establish mathematical validity; consult the source-bound review ledger.\n\n'
            coverage.append({'pr': p['number'], 'status': p['state'], 'author': p['author'],
                             'source_sha256': fingerprint, 'explanation': status,
                             'empty_body': not bool(p['body'].strip()), 'url': p['url']})
        chapters.append(chapter)
    ending = '\n# Reproducibility and editorial obligations\n\n'
    ending += ('The immutable JSON snapshot contains every fetched PR, the pinned selected result, '
               'the review ledger, contributor credits, and repository context. A deterministic build '
               'requires that snapshot, this generator, any editorial notes, and the recorded Pandoc '
               'version. The generator checks corpus coverage and detects stale editorial notes. '
               'It does not validate mathematics. Research and writing infrastructure assisted by Codex.\n\n')
    ending += f'{len(stale)} editorial explanations are stale in this edition. '
    ending += f'{sum(c["empty_body"] for c in coverage)} contributions have no submitted description.\n'
    for path in ['docs/research/bottleneck-brief.md', 'docs/research/research-glossary.md']:
        ending += f'\nSee the pinned [{path}](https://github.com/{repo}/blob/{snap["main_commit"]}/{path}).\n'
    paper = front + '\n'.join(chapters) + ending
    (args.output / 'paper.md').write_text(paper)
    (args.output / 'overview.md').write_text(front + ending)
    (args.output / 'coverage.json').write_text(json.dumps(coverage, indent=2) + '\n')
    if len(coverage) != len(prs) or len({c['pr'] for c in coverage}) != len(prs):
        raise RuntimeError('Contribution coverage mismatch')
    metadata = args.output / 'metadata.yaml'
    metadata.write_text(front.split('---', 2)[1])
    reader = 'markdown-raw_tex-raw_html-yaml_metadata_block'
    def parse_fragment(fragment):
        result = subprocess.run(['pandoc', '--from=' + reader, '--to=json'],
                                input=fragment, text=True, capture_output=True, check=True)
        return json.loads(result.stdout)['blocks']
    # Parse each contribution in isolation. Unclosed code/math in one source
    # must never swallow another author's section or reference definitions.
    base = json.loads(subprocess.run(['pandoc', '--metadata-file', str(metadata),
        '--from=' + reader, '--to=json'], input=front.split('---', 2)[2],
        text=True, capture_output=True, check=True).stdout)
    end_blocks = parse_fragment(ending)
    overview = dict(base, blocks=base['blocks'] + end_blocks)
    fragments = [fragment for chapter in chapters
                 for fragment in re.split(r'(?=^## PR )', chapter, flags=re.M) if fragment.strip()]
    blocks = list(base['blocks'])
    with ThreadPoolExecutor(max_workers=4) as pool:
        for parsed in pool.map(parse_fragment, fragments):
            blocks.extend(parsed)
    complete = dict(base, blocks=blocks + end_blocks)
    (args.output / 'paper.ast.json').write_text(json.dumps(complete))
    (args.output / 'overview.ast.json').write_text(json.dumps(overview))
    for stem, document in [('overview', overview), ('paper', complete)]:
        subprocess.run(['pandoc', '--from=json', '--to=latex', '--standalone',
             '--top-level-division=chapter', '--toc', '--number-sections', '--wrap=auto',
             '--include-in-header', str(ROOT/'web/latex-header.tex'),
             '-o', str(args.output / f'{stem}.tex')], input=json.dumps(document), text=True, check=True)
    # Retain raw control bytes in the snapshot, but make them visible and printable in TeX.
    for stem in ['paper', 'overview']:
        target = args.output / f'{stem}.tex'
        target.write_text(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',
            lambda match: '[control U+%04X]' % ord(match.group()), target.read_text()))
    labels = set(map(int, re.findall(r'\\label\{pr-(\d+)\}', (args.output/'paper.tex').read_text())))
    if labels != {p['number'] for p in prs}:
        raise ValueError('LaTeX contribution labels do not match source coverage')
    manifest = {'snapshot_sha256': digest(snap), 'included_prs': len(prs), 'authors': authors,
                'counts': dict(counts), 'stale_editorial': stale,
                'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'pandoc': run(['pandoc', '--version']).splitlines()[0],
                'editorial_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted(args.editorial.glob('*')) if p.is_file()},
                'outputs_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(args.output.glob('*')) if p.suffix in ('.tex','.md')}}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Built {len(prs)} contribution sections; {len(authors)} credited authors; {len(stale)} stale notes.')
    print(args.output / 'paper.tex')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    fetch = sub.add_parser('refresh', help='Fetch a complete new GitHub snapshot, preserving past editions')
    fetch.add_argument('--repo', default=REPO)
    fetch.add_argument('--data', type=Path, default=ROOT/'data')
    fetch.add_argument('--import-pages', type=Path, help='Import previously fetched REST pages; no freshness claim')
    build = sub.add_parser('build', help='Build offline from a frozen snapshot')
    build.add_argument('--snapshot', type=Path, default=ROOT/'data/latest.json')
    build.add_argument('--output', type=Path, default=ROOT/'output')
    build.add_argument('--editorial', type=Path, default=ROOT/'editorial')
    args = parser.parse_args()
    try:
        (refresh if args.command=='refresh' else render)(args)
    except (subprocess.CalledProcessError, ValueError, OSError) as exc:
        parser.exit(1, f'Build failed (no successful completion claimed): {exc}\n')


if __name__ == '__main__':
    main()
