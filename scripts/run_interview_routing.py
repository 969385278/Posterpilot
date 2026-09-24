"""Frozen synthetic routing benchmark; proposals are never human ground truth."""
import argparse
import asyncio
import hashlib
import json
import math
import random
import shutil
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from uuid import uuid4

from app.core.config import get_settings
from app.core.paths import PROJECT_ROOT
from app.providers.llm.deepseek import DeepSeekProvider
from app.schemas.intent import IntentRequest
from app.services.intent_router import IntentRouter, RuleIntentClassifier

LABELS = ['generate', 'modify', 'question', 'clarify', 'out_of_scope']

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def hashes():
    paths = sorted((PROJECT_ROOT / 'apps/api/app').rglob('*.py')) + [Path(__file__)]
    return {str(p.relative_to(PROJECT_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

class Recorder:
    def __init__(self, provider):
        self.provider, self.records, self.model = provider, [], provider.model

    async def complete_json(self, messages):
        record = {'messages': messages, 'response': None, 'error_type': None}
        self.records.append(record)
        start = perf_counter()
        try:
            record['response'] = await self.provider.complete_json(messages)
            return record['response']
        except BaseException as error:
            record['error_type'] = type(error).__name__
            raise
        finally:
            record['seconds'] = perf_counter() - start

def wilson(k, n):
    z = 1.959963984540054
    p = k/n
    c = (p+z*z/(2*n))/(1+z*z/n)
    h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [c-h, c+h]

def summarize(rows):
    conditions = ['rules_only', 'hybrid_live', 'all_llm_live']
    summary = {'labels_are_proposals': True, 'resume_claim_ready': False,
               'metrics': {}, 'paired_comparisons': {},
               'uncertainty_note': 'Wilson assumes independent cases; families are related. Paired family bootstrap is primary, conditional on this constructed corpus, not production traffic or model-repeat variance.'}
    grouped = {c:{r['id']:r for r in rows if r['condition']==c} for c in conditions}
    for c in conditions:
        values = list(grouped[c].values())
        n=len(values); correct=sum(r['correct'] for r in values)
        by_class={}; f1s=[]
        for label in LABELS:
            actual=[r for r in values if r['expected_intent']==label]
            tp=sum(r['correct'] for r in actual)
            fp=sum(not r['error'] and r['prediction']==label and r['expected_intent']!=label for r in values)
            fn=len(actual)-tp
            f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0
            f1s.append(f1)
            by_class[label]={'count':len(actual),'correct':tp,'accuracy':tp/len(actual) if actual else None,'f1':f1}
        summary['metrics'][c]={'requests':n,'correct':correct,'accuracy':correct/n,
            'wilson_95_iid_reference_only':wilson(correct,n),'macro_f1':sum(f1s)/len(f1s),
            'model_calls':sum(r['model_calls'] for r in values),'errors':sum(bool(r['error']) for r in values),
            'mean_seconds':sum(r['seconds'] for r in values)/n,'by_class':by_class,
            'confusion':dict(Counter(r['expected_intent']+' -> '+('ERROR' if r['error'] else r['prediction']) for r in values)),
            'failed_ids':[r['id'] for r in values if not r['correct']]}
    for base, target in [('rules_only','hybrid_live'),('all_llm_live','hybrid_live')]:
        a,b=grouped[base],grouped[target]
        if set(a)!=set(b): raise ValueError('Unpaired results')
        families={}
        for key in a:
            families.setdefault(a[key]['family_id'],[]).append(int(b[key]['correct'])-int(a[key]['correct']))
        rng=random.Random(20260924)
        family_values=list(families.values()); boot=[]
        for _ in range(10000):
            sample=[rng.choice(family_values) for _ in family_values]
            boot.append(sum(map(sum,sample))/sum(map(len,sample)))
        boot.sort()
        summary['paired_comparisons'][base+' -> '+target]={
            'accuracy_delta':sum(int(b[k]['correct'])-int(a[k]['correct']) for k in a)/len(a),
            'family_bootstrap_95':[boot[249],boot[9749]],'families':len(families),
            'wins':sum(b[k]['correct'] and not a[k]['correct'] for k in a),
            'losses':sum(a[k]['correct'] and not b[k]['correct'] for k in a)}
    full=summary['metrics']['all_llm_live']['model_calls']
    summary['model_call_reduction_vs_all_llm']=1-summary['metrics']['hybrid_live']['model_calls']/full if full else None
    summary['call_reduction_note']='Counts attempted provider invocations including failures; not token-cost savings or quality equivalence.'
    return summary

async def run(args):
    data=json.loads(args.dataset.read_text(encoding='utf-8')); cases=data['cases']
    if len(cases)!=200 or len({c['id'] for c in cases})!=200: raise ValueError('Expected 200 unique cases')
    if any(c['expected_intent'] not in LABELS for c in cases): raise ValueError('Invalid label')
    settings=get_settings()
    if not settings.deepseek_api_key: raise ValueError('Real provider credentials required')
    root=args.output_root/('routing-200-'+uuid4().hex);root.mkdir(parents=True)
    shutil.copyfile(args.dataset,root/'dataset.json')
    before=hashes()
    for name in before:
        dest=root/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(PROJECT_ROOT/name,dest)
    manifest={'state':'running','started_at':datetime.now(UTC).isoformat(),'python':sys.version,
              'model':settings.deepseek_text_model,'threshold':0.85,'concurrency':args.concurrency,
              'dataset_sha256':hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
              'source_hashes':before,'provenance':data.get('dataset_kind'),
              'human_labels_reviewed':False,'resume_claim_ready':False,
              'conditions':['rules_only','hybrid_live','all_llm_live'],
              'case_order_seed':20260924,'has_poster':False,'user_memory':False,
              'limitations':['Agent-authored constructed balanced corpus; labels proposed, not human-approved.',
                             'Author has inspected implementation; no independent-author claim.',
                             'Same-family inputs correlated; no production prevalence estimate.',
                             'One paired run; no claim of model sampling stability.']}
    save(root/'manifest.json',manifest);print(str(root),flush=True)
    provider=DeepSeekProvider(api_key=settings.deepseek_api_key,model=settings.deepseek_text_model,
                              base_url=settings.deepseek_base_url,timeout_seconds=settings.text_model_timeout_seconds)
    rows=[]; sem=asyncio.Semaphore(args.concurrency)
    ordered=list(cases);random.Random(20260924).shuffle(ordered)
    with (root/'rows.jsonl').open('x',encoding='utf-8') as stream:
        async def one_case(index,case):
            async with sem:
                order=['rules_only']+(['hybrid_live','all_llm_live'] if index%2==0 else ['all_llm_live','hybrid_live'])
                for condition in order:
                    start=perf_counter();recorder=Recorder(provider)
                    row={k:case[k] for k in ['id','family_id','text','expected_intent']}
                    row.update(condition=condition,prediction=None,error=None)
                    try:
                        if condition=='rules_only':
                            result=await RuleIntentClassifier().classify(case['text']);row['prediction']=result.label
                            row['classifier_confidence']=result.confidence
                        else:
                            runs=SimpleNamespace(executor=SimpleNamespace(text_provider=recorder),data_origin='runtime')
                            router=IntentRouter(runs,threshold=0.85,direct_llm=condition=='all_llm_live')
                            result=await router.resolve(IntentRequest(text=case['text']))
                            row['prediction']=result.intent;row['resolution']=result.model_dump(mode='json')
                            if result.route_method=='unavailable':row['error']='resolution_unavailable'
                    except Exception as error:row['error']=type(error).__name__
                    row.update(seconds=perf_counter()-start,model_calls=len(recorder.records),provider_records=recorder.records)
                    row['correct']=not row['error'] and row['prediction']==case['expected_intent']
                    rows.append(row);stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
                if (index+1)%10==0:print(f'completed case index {index+1}/200; persisted rows={len(rows)}',flush=True)
        try:
            await asyncio.gather(*(one_case(i,c) for i,c in enumerate(ordered)))
            summary=summarize(rows)
            summary['code_unchanged']=before==hashes()
            summary['data_unchanged']=manifest['dataset_sha256']==hashlib.sha256(args.dataset.read_bytes()).hexdigest()
            summary['execution_complete']=len(rows)==600
            save(root/'summary.json',summary)
            manifest['state']='completed_provisional' if all(summary[k] for k in ['code_unchanged','data_unchanged','execution_complete']) else 'invalid'
        except BaseException as error:
            manifest['state']='interrupted_or_failed';manifest['error_type']=type(error).__name__;raise
        finally:
            manifest['finished_at']=datetime.now(UTC).isoformat();save(root/'manifest.json',manifest)
    print(json.dumps({'state':manifest['state'],'metrics':summary['metrics'],'paired_comparisons':summary['paired_comparisons'],'model_call_reduction':summary['model_call_reduction_vs_all_llm']},ensure_ascii=True),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--output-root',type=Path,default=PROJECT_ROOT/'work/interview-evaluation/runs')
    p.add_argument('--concurrency',type=int,choices=[1,2],default=2)
    asyncio.run(run(p.parse_args()))
