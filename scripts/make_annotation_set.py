"""抽取待人工标注样本；不预填规则标签，避免评测循环自证。"""
import csv,json,random
from pathlib import Path
root=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader(open(root/'data/seed/reviews.csv',encoding='utf-8-sig')))
real=[r for r in rows if r['source_type']=='1'];sample=random.Random(42).sample(real,min(300,len(real)))
out=root/'data/eval/aspects_pending.jsonl'
with out.open('w',encoding='utf-8') as f:
    for r in sample:f.write(json.dumps({'text':r['content_raw'],'status':'pending_human_annotation','aspects':[]},ensure_ascii=False)+'\n')
print(out)
