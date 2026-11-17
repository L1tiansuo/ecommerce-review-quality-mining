"""离线种子预计算：与在线服务使用相同核心函数，Java 负责最终入库。"""
import csv,json,sys,calendar,time
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timedelta
from statistics import median
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'algo'))
from core.sentiment import predict,version
from core.aspect import extract,DEFAULT
from core.fake_rules import evaluate
from core.qi import calculate
seed=ROOT/'data/seed';groups=defaultdict(list)
for i,r in enumerate(csv.DictReader(open(seed/'reviews.csv',encoding='utf-8-sig')),1):
    r['review_id']=i;r['content']=r['content_raw'];groups[r['product_id']].append(r)
products={r['id']:r for r in csv.DictReader(open(seed/'products.csv',encoding='utf-8-sig'))}
analysis={};started=time.perf_counter()
with (seed/'analysis.jsonl').open('w',encoding='utf-8') as out:
    for number,(pid,rs) in enumerate(groups.items(),1):
        ss=predict([r['content'] for r in rs]);aa=[extract(r['content']) for r in rs];ff=evaluate(rs,ss,aa)
        for r,s,a,f in zip(rs,ss,aa,ff):
            item={**f,'sentiment':{'pos':1,'neu':0,'neg':-1}[s['label']],'confidence':s['confidence'],'aspects':a,'model_version':version()}
            out.write(json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n');r.update(item)
        analysis[pid]=rs
        if number%100==0:print(f'analyzed {number}/{len(groups)}, {time.perf_counter()-started:.1f}s',flush=True)
end=datetime.fromisoformat(json.loads((seed/'manifest.json').read_text(encoding='utf-8'))['demo_end'])
history=defaultdict(list)
with (seed/'indices.jsonl').open('w',encoding='utf-8') as out:
    for offset in range(12,-1,-1):
        absolute=end.year*12+end.month-1-offset;y,m=divmod(absolute,12);start=datetime(y,m+1,1);finish=min(end,datetime(y,m+1,calendar.monthrange(y,m+1)[1]))
        pending=[]
        for pid,rs in analysis.items():
            month=[r for r in rs if start.date()<=datetime.fromisoformat(r['review_time']).date()<=finish.date()]
            if not month:continue
            cat=products[pid]['category_id'];priors={}
            for dim in DEFAULT['dimensions']:
                values=[v for t,v in history[(cat,dim['code'])] if t>=finish-timedelta(days=90)]
                if values:priors[dim['code']]=median(values)
            qi=calculate(month,finish.isoformat(),priors=priors)
            item={**qi,'product_id':int(pid),'period_start':start.date().isoformat(),'period_end':finish.date().isoformat(),'param_version':'v1-2026-10'}
            out.write(json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n')
            for d in qi['dims']:pending.append(((cat,d['code']),(finish,d['score'])))
        # 同月一次发布，禁止商品遍历顺序影响品类先验。
        for key,value in pending:history[key].append(value)
        print('computed month',start.date(),flush=True)
(seed/'aspect_dict.json').write_text(json.dumps(DEFAULT,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'Completed in {time.perf_counter()-started:.1f}s',flush=True)
