"""两遍流式扫描 yf_amazon；不修改原数据、不保存用户标识。"""
import argparse,csv,json,sys,calendar,random,hashlib
from collections import Counter
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'algo'))
from core.preprocess import clean,mask
def build(raw,out,target=194000,products=1354,end='2026-11-09'):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);raw=Path(raw)
    counts=Counter()
    with (raw/'ratings.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):counts[r['productId']]+=1
    candidates=[k for k,n in counts.items() if n>=40]
    random.Random(42).shuffle(candidates)
    # 固定商品数，按长尾评论数抽样；总量上限按每商品配额分配。
    chosen=candidates[:products];total=sum(counts[p] for p in chosen)
    quotas={p:max(40,int(counts[p]*target/total)) for p in chosen}
    rows=[];seen=set();kept=Counter();old=[]
    with (raw/'ratings.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            p=r['productId']
            if p not in quotas or kept[p]>=quotas[p]:continue
            text=clean(r.get('comment',''))
            try:rating=int(float(r['rating']));ts=int(r['timestamp'])
            except (ValueError,KeyError):continue
            key=(p,text)
            if len(text)<5 or key in seen or not 1<=rating<=5:continue
            seen.add(key);kept[p]+=1;old.append(ts)
            rows.append({'product_id':p,'content_raw':mask(r['comment'])[:2000],'rating':rating,'review_time':ts,'source_type':1,'scenario':''})
    valid={p for p,n in kept.items() if n>=20};rows=[r for r in rows if r['product_id'] in valid]
    cats={}
    with (raw/'categories.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):cats[r['catId']]=r['category']
    prods=[]
    with (raw/'products.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['productId'] in valid:
                cat=r['catIds'].split(',')[-1];prods.append({'id':r['productId'],'name':mask(r['name'])[:200],'category_id':cat,'category_name':cats.get(cat,'未分类'),'supplier_id':int(cat)%12+1,'scenario':''})
    anchor=datetime.fromisoformat(end).replace(hour=23,minute=59,second=59)
    # 固定 13 个月，最后一个月截止 anchor；加权分位且保持排序。
    months=[]
    for offset in range(12,-1,-1):
        absolute=anchor.year*12+anchor.month-1-offset;y,m=divmod(absolute,12)
        start=datetime(y,m+1,1);finish=min(anchor,datetime(y,m+1,calendar.monthrange(y,m+1)[1],23,59,59));months.append((start,finish))
    weights=[1,1,1,1,1,2,2,2,3,4,6,8,10];acc=[];s=0
    for w in weights:s+=w/sum(weights);acc.append(s)
    rows.sort(key=lambda r:r['review_time']);bucket=0
    for i,r in enumerate(rows):
        q=(i+.5)/len(rows)
        while bucket<12 and q>acc[bucket]:bucket+=1
        prev=acc[bucket-1] if bucket else 0;frac=(q-prev)/(acc[bucket]-prev)
        a,b=months[bucket];r['review_time']=(a+(b-a)*frac).isoformat(sep=' ',timespec='seconds')
    scenarios=[]
    texts=['质量非常差，外观难看，物流很慢，客服态度差，价格太贵，包装破损。','质量很差，外观不好，物流慢，客服推诿，价格贵，包装压坏。','质量很好，外观漂亮，物流很快，客服满意，价格划算，包装完美。','质量垃圾，做工差，物流慢，客服差，包装坏。','质量很好，外观漂亮，物流很快，客服满意，性价比很好，包装完好。']
    for k in range(5):
        pid=str(900000001+k);code=f'S-0{k+1}'
        prods.append({'id':pid,'name':f'{code} 教学剧本商品（模拟）','category_id':'99999','category_name':'教学剧本（模拟）','supplier_id':1,'scenario':code})
        for j in range(240):
            t=anchor-timedelta(days=80-j%70,hours=j%12)
            text='质量不错，外观漂亮，物流很快，客服很好，价格划算，包装很好。'+str(j)
            rating=5
            if k==0 and j>=40:text=texts[0]+str(j);rating=1;t=anchor-timedelta(days=j%28,hours=j%12)
            if k==1 and j>=200:text=texts[1]+str(j);rating=1;t=anchor-timedelta(days=j%6,hours=j%12)
            if k==2 and j>=120:text=texts[2]+str(j);t=anchor.replace(hour=12,minute=0,second=0)-timedelta(days=1)+timedelta(seconds=(j-120)*60)
            if k==3 and j>=205:text=texts[3]+str(j);rating=5;t=anchor-timedelta(days=j%6)
            if k==4 and j>=215:text=texts[4];rating=5;t=anchor-timedelta(days=j%6)
            rows.append({'product_id':pid,'content_raw':text,'rating':rating,'review_time':t.isoformat(sep=' ',timespec='seconds'),'source_type':3,'scenario':code})
        scenarios.append({'code':code,'product_id':pid,'event':['指数跌破阈值','近七日差评突增','单日120条聚集','五星配差评文本35条','完全模板好评25条'][k]})
    def write(name,data):
        with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    write('reviews.csv',rows);write('products.csv',prods)
    write('categories.csv',[{'id':k,'name':v} for k,v in cats.items()]+[{'id':'99999','name':'教学剧本（模拟）'}])
    (out/'scenarios.json').write_text(json.dumps(scenarios,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={'source':'yf_amazon','products':len(prods),'reviews':len(rows),'demo_end':end,'time_normalized':True,'synthetic_suppliers':True,'month_weights':weights,'original_start':datetime.fromtimestamp(min(old)).isoformat(),'original_end':datetime.fromtimestamp(max(old)).isoformat(),'seed':42}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print(manifest)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',required=True);p.add_argument('--out',default=str(ROOT/'data/seed'));p.add_argument('--target',type=int,default=194000);p.add_argument('--products',type=int,default=1354);p.add_argument('--end',default='2026-11-09');a=p.parse_args();build(a.raw,a.out,a.target,a.products,a.end)
