#!/usr/bin/env python3
"""Track all 268 workflow outcomes independently of decoder maturity."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.mi_survey_priorities import survey_rows


def progress_rows(root=ROOT):
    ranked,_,_=survey_rows(root)
    doc=json.loads((root/'research/mi_capabilities.json').read_text())
    if doc['schema_version']!=1:raise ValueError('Unknown capability schema')
    entries=doc['types'];known={r['key'] for r in ranked}
    if set(entries)-known:raise ValueError('Unknown capability type')
    rows=[]
    for rank,base in enumerate(ranked,1):
        entry=entries.get(base['key'],{'state':'queued','workflow':'No type-specific Guided workflow audited yet.',
                                     'next_step':base['next_research_step']})
        if entry['state'] not in ('queued','partial','blocked','delivered'):
            raise ValueError('Unknown workflow state')
        if not entry['workflow'] or not entry['next_step']:
            raise ValueError('Missing outcome or next step')
        if entry['state']=='blocked' and not entry.get('blocker'):
            raise ValueError('Blocked requires a concrete blocker and resolving evidence')
        rows.append({'rank':rank,'code':base['code'],'key':base['key'],'name':base['name'],
                     'decoder':base['maturity'],**entry})
    return rows


def markdown(rows):
    counts=Counter(r['state'] for r in rows)
    lines=['# MI capability progress — all 268 types','',
           'The full inventory is the continuing work queue. A PR is a review checkpoint, not completion.',
           'Workflow state is independent of binary decoder maturity. Shared type/search navigation does not complete a type.',
           'Queued means a type-specific Guided workflow still needs work/audit; existing forensic decoders may already exist.',
           'Partial means a usable bounded workflow exists and its remaining scope is explicit. No type is claimed universally decoded.',
           '', 'States: '+', '.join(f'{k} {counts[k]}' for k in ('delivered','partial','blocked','queued'))+'.',
           '', 'Generated from `research/mi_capabilities.json` and the ranked research inventory.',
           'See [workflow evidence and validation](TYPE_CAPABILITY_WORKFLOWS.md).', '',
           '| Rank | MI | Type | Workflow state | Usable workflow | Next material result |',
           '|---:|---|---|---|---|---|']
    for r in rows:
        clean=lambda s:str(s).replace('|','/').replace('\n',' ')
        lines.append('| '+' | '.join(clean(r[k]) for k in ('rank','code','name','state','workflow','next_step'))+' |')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-report',action='store_true')
    p.add_argument('--format',choices=('markdown','json'),default='markdown');a=p.parse_args()
    rows=progress_rows();out=markdown(rows)
    if a.check_report:
        if (ROOT/'docs/MI_CAPABILITY_PROGRESS.md').read_text()!=out:raise SystemExit('Capability report is stale')
    else:print(json.dumps(rows,indent=2) if a.format=='json' else out,end='\n' if a.format=='json' else '')
