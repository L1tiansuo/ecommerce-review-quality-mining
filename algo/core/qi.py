"""确定性质量指数：固定 period_end；禁止使用墙上时钟参与结果。"""
import math
from datetime import datetime
from .aspect import DEFAULT
def calculate(reviews,period_end,params=None,priors=None):
    params=params or {};priors=priors or {}
    dims=DEFAULT['dimensions'];weights=params.get('weights',{d['code']:d['weight'] for d in dims})
    if set(weights)!={d['code'] for d in dims} or abs(sum(weights.values())-1)>1e-8 or any(w<0 for w in weights.values()):raise ValueError('六维权重必须非负且合计为 1')
    end=datetime.fromisoformat(period_end[:10]);half=float(params.get('half_life',90));m=float(params.get('m',10))
    if half<=0 or m<=0:raise ValueError('半衰期与先验强度必须为正数')
    result=[]
    for d in dims:
        code=d['code'];num=den=0.;n=0
        for r in reviews:
            # 同评论同维度先聚合多个特性，避免重复计样本量。
            # 强度为 0 表示该窗口没有任何情感证据，不能当成"中性"计入样本，
            # 否则大量无语义的方面命中会把维度分拉向 0.5，指标失去区分度。
            strengths=[float(a['strength']) for a in r.get('aspects',[]) if a.get('dimension',a.get('dimension_code'))==code and float(a.get('strength',0))!=0]
            if not strengths:continue
            days=(end-datetime.fromisoformat(str(r['review_time'])[:10])).days
            if days<0:continue
            w=math.exp(-math.log(2)*days/half)*(1-float(r.get('fake_prob',0)))
            num+=w*sum(strengths)/len(strengths);den+=w;n+=1
        s=((num/den if den else 0)+1)/2
        score=(n*s+m*float(priors.get(code,.55)))/(n+m)
        result.append({'code':code,'name':d['name'],'score':round(score,8),'n':n,'contribution':round(100*weights[code]*score,6)})
    qi=round(sum(x['contribution'] for x in result),2)
    return {'qi':qi,'grade':5 if qi>=85 else 4 if qi>=75 else 3 if qi>=65 else 2 if qi>=55 else 1,'sample_size':len(reviews),'dims':result,'reference':len(reviews)<30}
