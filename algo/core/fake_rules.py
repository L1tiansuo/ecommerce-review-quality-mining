"""可解释刷评风险，不代表认定评论虚假。按商品分组，避免跨商品误判。"""
from collections import Counter,defaultdict
from datetime import datetime,timedelta
import hashlib,math,bisect
from .sentiment import predict
from .aspect import extract
def grams(text):return {text[i:i+3] for i in range(max(1,len(text)-2))}
def simhash(text):
    sums=[0]*64
    for g in sorted(grams(text)):
        h=int.from_bytes(hashlib.blake2b(g.encode(),digest_size=8).digest(),'big')
        for i in range(64):sums[i]+=1 if h>>i&1 else -1
    return sum(1<<i for i,v in enumerate(sums) if v>0)
def evaluate(reviews,sentiments=None,aspects=None):
    sentiments=sentiments or predict([r['content'] for r in reviews])
    aspects=aspects or [extract(r['content']) for r in reviews]
    groups=defaultdict(list)
    for i,r in enumerate(reviews):groups[str(r.get('product_id','single'))].append(i)
    user_times=defaultdict(list)
    for r in reviews:
        if r.get('user_key'):user_times[r['user_key']].append(datetime.fromisoformat(str(r['review_time']).replace('Z','+00:00')).replace(tzinfo=None))
    for ts in user_times.values():ts.sort()
    results=[None]*len(reviews)
    for indices in groups.values():
        times={i:datetime.fromisoformat(str(reviews[i]['review_time']).replace('Z','+00:00')).replace(tzinfo=None) for i in indices}
        days=Counter(t.date() for t in times.values())
        span=max(1,(max(times.values()).date()-min(times.values()).date()).days+1)
        mean=len(indices)/span;sd=math.sqrt(sum((v-mean)**2 for v in days.values())/span+(span-len(days))*mean**2/span)
        ordered=sorted(indices,key=lambda i:times[i]);left=0;diff=[0]*(len(indices)+1)
        for right,idx in enumerate(ordered):
            while times[idx]-times[ordered[left]]>=timedelta(hours=24):left+=1
            n=right-left+1
            if n>mean+3*sd and n/len(indices)>.2:diff[left]+=1;diff[right+1]-=1
        burst=set();active=0
        for j,idx in enumerate(ordered):
            active+=diff[j]
            if active:burst.add(idx)
        # 四段哈希桶：汉明距离 <=3 必有至少一段相同，避免全量两两比较。
        buckets=defaultdict(list);hashes={};templates=set();pairs=[];gram_index=defaultdict(list);sets={}
        for i in indices:
            h=simhash(reviews[i]['content']);hashes[i]=h;gs=grams(reviews[i]['content']);sets[i]=gs
            candidates=set()
            for b in range(4):candidates.update(buckets[(b,(h>>(16*b))&65535)])
            # Jaccard>0.8 时，任取20%+1的gram至少一个有交集。
            for g in sorted(gs)[:int(len(gs)*.2)+1]:candidates.update(gram_index[g])
            for j in candidates:
                similar=(h^hashes[j]).bit_count()<=3
                if not similar and min(len(gs),len(sets[j]))>.8*max(len(gs),len(sets[j])):similar=len(gs&sets[j])/max(1,len(gs|sets[j]))>.8
                if similar:
                    templates.update((i,j));pairs.append((i,j));break
            for b in range(4):buckets[(b,(h>>(16*b))&65535)].append(i)
            for g in gs:gram_index[g].append(i)
        # 并查集聚簇：单条与某条相似可能是巧合，成簇才是模板。
        parent={i:i for i in indices}
        def find(x):
            while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
            return x
        for a,b in pairs:
            ra,rb=find(a),find(b)
            if ra!=rb:parent[ra]=rb
        cluster=Counter(find(i) for i in indices)
        users=defaultdict(list)
        for i in indices:
            if reviews[i].get('user_key'):users[reviews[i]['user_key']].append(times[i])
        for i in indices:
            r=reviews[i];hits=[]
            def hit(rule,weight,detail):hits.append({'rule':rule,'weight':weight,'detail':detail})
            peak=days[times[i].date()]
            if i in burst:hit('burst',.30,'同商品24小时滑动窗口评论量超过日均值加三倍标准差，且窗口占比超过20%')
            rating=float(r.get('rating') or 3);s=sentiments[i]['score']
            if (rating>=4 and s<-.3) or (rating<=2 and s>.3):hit('contradict',.25,'星级评分与文本情感明显背离')
            if i in templates:
                cs=cluster[find(i)]
                w=.45 if cs>=20 else (.35 if cs>=5 else .20)
                hit('template',w,'同商品存在 SimHash 距离≤3或3-gram Jaccard>0.8的近重复评论，同簇 %d 条'%cs)
            if len(r['content'])<6 and not aspects[i]:hit('short',.15,'正文不足 6 字且没有质量方面信息')
            if r.get('user_key'):
                lo=times[i]-timedelta(days=7);hi=times[i];local=sum(lo<=t<=hi for t in users[r['user_key']]);ts=user_times[r['user_key']];global_count=bisect.bisect_right(ts,hi)-bisect.bisect_left(ts,lo)
                if local>3 or global_count>10:hit('repeat_user',.10,'同一模拟用户七日内同商品超过3条或跨商品超过10条')
            results[i]={'review_id':r.get('review_id'),'fake_prob':round(min(1,sum(h['weight'] for h in hits)),3),'hits':hits}
    return results
