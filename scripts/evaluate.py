"""不造评测值：方面金标缺失时写 not_evaluated；三分类缺中评也明确披露。"""
import sys,json,csv,argparse
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'algo'))
from core.sentiment import predict,version
from core.aspect import extract
from sklearn.metrics import classification_report,confusion_matrix
p=argparse.ArgumentParser();p.add_argument('--testset',default=str(ROOT/'data/eval/test_1000.csv'));p.add_argument('--aspects');p.add_argument('--out',default=str(ROOT/'docs/metrics.json'));a=p.parse_args()
rows=list(csv.DictReader(open(a.testset,encoding='utf-8-sig')));truth=[r['label'] for r in rows];pred=[r['label'] for r in predict([r['text'] for r in rows])]
report=classification_report(truth,pred,labels=['pos','neu','neg'],output_dict=True,zero_division=0)
result={'model_version':version(),'sentiment':{'macro_f1':report['macro avg']['f1-score'],'per_class':report,'n':len(rows),'confusion_matrix':confusion_matrix(truth,pred,labels=['pos','neu','neg']).tolist(),'labels':['pos','neu','neg'],'valid_three_class_acceptance':set(truth)=={'pos','neu','neg'}},'aspect':{'status':'not_evaluated','reason':'需要300条独立人工方面标注'},'generated_at':datetime.now(timezone.utc).isoformat()}
if a.aspects:
    gold=[json.loads(l) for l in open(a.aspects,encoding='utf-8') if l.strip()]
    if any(r.get('status')=='pending_human_annotation' for r in gold):
        raise ValueError('待标注样本不能用于验收评测，请先完成独立人工标注并移除pending状态')
    tp=fp=fn=correct=matched=0
    for r in gold:
        actual={(x['feature_code'],x['start'],x['end']):x for x in extract(r['text'])};expected={(x['feature_code'],x['start'],x['end']):x for x in r['aspects']}
        common=set(actual)&set(expected);tp+=len(common);fp+=len(set(actual)-set(expected));fn+=len(set(expected)-set(actual));matched+=len(common);correct+=sum(actual[k]['polarity']==expected[k]['polarity'] for k in common)
    precision=tp/max(1,tp+fp);recall=tp/max(1,tp+fn)
    result['aspect']={'precision':precision,'recall':recall,'f1':2*precision*recall/max(1e-9,precision+recall),'n':len(gold)};result['aspect_sentiment']={'accuracy':correct/max(1,matched),'n':matched}
Path(a.out).parent.mkdir(parents=True,exist_ok=True);Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
