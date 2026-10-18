"""Source-bound frontier history and accessible, dependency-free SVG progress charts."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import html
import json
from pathlib import Path


def fetch_history(repo, revision, api):
    seed=Path(__file__).with_name('frontier-seed.json')
    cached={p['sha']:p for p in json.loads(seed.read_text())} if seed.exists() else {}
    pages=api(f'repos/{repo}/commits?path=certificates/selected-result.json&sha={revision}&per_page=100',pages=True)
    records=[]
    for page in pages:
        for commit in page:
            sha=commit['sha']
            if sha in cached:
                record=dict(cached[sha])
            else:
                source=json.loads(api(f'repos/{repo}/contents/certificates/selected-result.json?ref={sha}',raw=True))
                value=Fraction(source['kappa'])
                record={'sha':sha,'kappa':str(value),'decimal':source.get('decimal',str(float(value))),
                        'source_prs':source.get('source_prs',[source['source_pr']] if 'source_pr' in source else []),
                        'status':source.get('status','Repository-selected conditional result')}
            record['time']=commit['commit']['committer']['date']
            records.append(record)
    return sorted(records,key=lambda p:(p['time'],p['sha']))


def instant(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)


def progress_data(snapshot):
    raw=snapshot.get('frontier_history',[])
    frontier=[]
    for record in sorted(raw,key=lambda p:instant(p['time'])):
        if not frontier or Fraction(record['kappa'])!=Fraction(frontier[-1]['kappa']):
            frontier.append(record)
    selected=json.loads(snapshot['sources']['certificates/selected-result.json'])
    if frontier and Fraction(frontier[-1]['kappa'])!=Fraction(selected['kappa']):
        raise ValueError('Frontier history does not end at the pinned selected result')
    corpus=[p for p in snapshot['prs'] if p['state'] in ('open','merged')]
    created=Counter(instant(p['created_at']).date() for p in corpus)
    merged=Counter(instant(p['merged_at']).date() for p in corpus if p['merged_at'])
    activity=[]
    if created:
        day=min(created);last=instant(snapshot['finished_at']).date();submitted=integrated=0
        while day<=last:
            submitted+=created[day];integrated+=merged[day]
            activity.append({'date':day.isoformat(),'submitted':submitted,'merged':integrated})
            day+=timedelta(days=1)
    return {'observed_at':snapshot['finished_at'],'repo':snapshot['repo'],
            'frontier':frontier,'activity':activity,
            'frontier_scope':'Selected-result file history on pinned main; all results retain their conditions.',
            'activity_scope':'Cumulative creations and merges of PRs in the current merged/open corpus; not historical queue size.'}


def chart(series,start,end,ymax,label,tick_format):
    left,right,top,bottom=91,785,28,265
    width=right-left;height=bottom-top;span=max(1,(end-start).total_seconds())
    x=lambda when:left+(instant(when)-start).total_seconds()/span*width
    y=lambda value:bottom-float(value)/ymax*height
    out=[f'<svg class="progress-chart" viewBox="0 0 820 320" role="img" aria-label="{html.escape(label,quote=True)}"><title>{html.escape(label)}</title>']
    for i in range(5):
        v=ymax*i/4;py=y(v)
        out.append(f'<line x1="{left}" x2="{right}" y1="{py:.2f}" y2="{py:.2f}" stroke="#d9ded4"/><text x="{left-12}" y="{py+5:.2f}" text-anchor="end">{tick_format(v)}</text>')
    for i in range(5):
        time=start+(end-start)*i/4;px=left+width*i/4
        out.append(f'<text x="{px:.2f}" y="295" text-anchor="{"start" if i==0 else "end" if i==4 else "middle"}">{time.strftime("%b %d")}</text>')
    for name,color,points in series:
        if not points:continue
        path=f'M {x(points[0][0]):.2f} {y(points[0][1]):.2f}'
        for time,value,_,_ in points[1:]:path+=f' H {x(time):.2f} V {y(value):.2f}'
        path+=f' H {right}'
        out.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3"/>')
        for time,value,tooltip,url in points:
            mark=f'<circle cx="{x(time):.2f}" cy="{y(value):.2f}" r="4" fill="{color}"><title>{html.escape(tooltip)}</title></circle>'
            if url:mark=f'<a href="{html.escape(url,quote=True)}" aria-label="{html.escape(tooltip,quote=True)}">{mark}</a>'
            out.append(mark)
    out.append('</svg>')
    return ''.join(out)


def render_progress(data):
    end=instant(data['observed_at']);repo=data['repo'];frontier=data['frontier'];activity=data['activity']
    out=['<section id="progress"><h2>Progress over time</h2><p>Follow the selected mathematical checkpoints and the activity around them. A merged contribution does not, by itself, establish a stronger bound.</p>']
    if frontier:
        points=[(p['time'],float(Fraction(p['kappa'])),f"{p['time']}: selected κ = {p['decimal']}",f"https://github.com/{repo}/blob/{p['sha']}/certificates/selected-result.json") for p in frontier]
        out+=['<h3>Selected conditional κ</h3><p class="muted">Higher means a larger exponent saving, not a measured runtime improvement. Begins at the first selected-result record. Click a checkpoint to inspect its source; dates are UTC.</p><div class="chart-scroll">',
              chart([('Selected κ','#215f51',points)],instant(frontier[0]['time']),end,max(p[1] for p in points)*1.1,'Selected conditional kappa over time',lambda v:f'{v:.4f}'),'</div>']
        rows=''.join(f'<tr><td>{html.escape(p["time"][:10])}</td><td>{html.escape(p["decimal"])}</td><td><a href="https://github.com/{repo}/blob/{p["sha"]}/certificates/selected-result.json">{p["sha"][:8]}</a></td></tr>' for p in frontier)
        out.append('<details><summary>Checkpoint values and source revisions</summary><table><thead><tr><th>Date (UTC)</th><th>Selected κ</th><th>Source</th></tr></thead><tbody>'+rows+'</tbody></table></details>')
    else:
        out.append('<p>The selected-result history is not available for this snapshot; no historical bound is inferred from PR titles.</p>')
    if activity:
        series=[]
        for field,name,color in [('submitted','Submitted','#215f51'),('merged','Merged','#a66a32')]:
            points=[(p['date']+'T00:00:00Z',p[field],f"{p['date']}: {p[field]} {name.lower()}",None) for p in activity]
            series.append((name,color,points))
        out+=['<h3>Contribution activity</h3><p class="chart-legend"><span style="color:#215f51">● Submitted</span> <span style="color:#a66a32">● Merged</span></p><div class="chart-scroll">',chart(series,instant(activity[0]['date']+'T00:00:00Z'),end,max(1,activity[-1]['submitted'])*1.1,'Cumulative submitted and merged contributions',lambda v:f'{v:,.0f}'),'</div><p class="muted">Daily cumulative counts for the current merged/open corpus, not a reconstruction of historical review status. <a href="progress.json">Download graph data</a>.</p>']
    out.append('</section>')
    return ''.join(out)
