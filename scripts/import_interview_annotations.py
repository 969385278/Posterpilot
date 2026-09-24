"""Validate user-exported blind annotations and write a new reviewed dataset."""
import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

LABELS={'generate','modify','question','clarify','out_of_scope'}

def validate_review(data, review, dataset_hash, kind, card_ids=()):
    if review.get('dataset_sha256')!=dataset_hash:raise ValueError('Dataset hash mismatch')
    if not str(review.get('reviewer','')).strip():raise ValueError('Named reviewer required')
    original=data['cases'] if kind=='routing' else data
    entries=review.get('cases',[])
    if len(entries)!=len(original):raise ValueError('Review all cases; partial review cannot produce final labels')
    by_id={r['id']:r for r in entries}
    if len(by_id)!=len(entries) or set(by_id)!={c['id'] for c in original}:raise ValueError('Duplicate, missing or unknown case ID')
    changed=[];output=[];unanswerable=[]
    for case in original:
        row=by_id[case['id']];new=dict(case)
        if kind=='routing':
            if row.get('human_label') not in LABELS:raise ValueError(case['id']+': label missing or invalid')
            if row.get('ambiguous') is not False:raise ValueError(case['id']+': ambiguity needs adjudication, do not silently exclude')
            if row['human_label']!=case['expected_intent']:changed.append(case['id'])
            new.update(expected_intent=row['human_label'],human_reviewed=True)
        else:
            if row.get('reviewed') is not True:raise ValueError(case['id']+': unreviewed')
            relevant=row.get('relevant_card_ids',[])
            if len(relevant)!=len(set(relevant)) or not set(relevant)<=set(card_ids):raise ValueError(case['id']+': invalid card IDs')
            if bool(relevant)==bool(row.get('no_answer')):raise ValueError(case['id']+': choose relevant cards OR no answer')
            if set(relevant)!=set(case['expected_card_ids']):changed.append(case['id'])
            new['expected_card_ids']=relevant
            if not relevant:unanswerable.append(new);continue
        output.append(new)
    return output,unanswerable,changed

def main():
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['routing','retrieval'],required=True)
    p.add_argument('--dataset',type=Path,required=True);p.add_argument('--review',type=Path,required=True)
    p.add_argument('--corpus',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=a.dataset.read_bytes();data=json.loads(raw);review=json.loads(a.review.read_text(encoding='utf-8-sig'))
    cards=[]
    if a.kind=='retrieval':
        if not a.corpus:raise ValueError('Frozen corpus snapshot required')
        cards=[c['id'] for c in json.loads(a.corpus.read_text(encoding='utf-8')) if c['review_status']=='approved']
    output,noanswer,changed=validate_review(data,review,hashlib.sha256(raw).hexdigest(),a.kind,cards)
    if a.output.exists():raise FileExistsError('Reviewed output already exists')
    a.output.mkdir(parents=True)
    if a.kind=='routing':
        result={**data,'dataset_kind':'agent_authored_synthetic_human_reviewed','cases':output,
                'annotation_note':'Constructed data reviewed by a named person. Not natural user data or independent authorship. Rescoring stored predictions is label review, not a new held-out run.'}
    else:result=output
    (a.output/'dataset.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (a.output/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
    (a.output/'no-answer.json').write_text(json.dumps(noanswer,ensure_ascii=False,indent=2),encoding='utf-8')
    provenance={'created_at':datetime.now(UTC).isoformat(),'reviewer':review['reviewer'],
        'input_sha256':hashlib.sha256(raw).hexdigest(),'review_sha256':hashlib.sha256(a.review.read_bytes()).hexdigest(),
        'changed_label_ids':changed,'labelled_cases':len(output),'no_answer_cases':len(noanswer),
        'independent_user_data':False,'resume_claim_ready':False,
        'next':'Recompute all stored outputs using these labels. Preserve proposed-label results. Disclose any adjudication after prediction exposure; no-answer retrieval needs separate metrics.'}
    (a.output/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(provenance,ensure_ascii=True))

if __name__=='__main__':main()
