"""纯计算服务：不连接数据库；全部持久化由 Java 业务服务负责。"""
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field
from core import sentiment
from core.aspect import extract,DICT_PATH
from core.fake_rules import evaluate
from core.qi import calculate
from core.preprocess import clean
app=FastAPI(title='评论质量算法服务',version='1.0.0')
@app.middleware('http')
async def limit(request:Request,call_next):
    if request.method=='POST' and request.url.path.startswith('/v1/'):
        body=await request.body()
        if len(body)>32768:return JSONResponse(status_code=413,content={'code':413,'message':'同步请求不得超过 32 KB','data':None})
    return await call_next(request)
def ok(data):return {'code':0,'message':'ok','data':{'model_version':sentiment.version(),**data}}
class Texts(BaseModel):
    texts:list[str]=Field(max_length=100)
    model_version:str='auto'
    dictionary:dict|None=None
class Reviews(BaseModel):
    reviews:list[dict]
@app.get('/v1/health')
def health():return ok({'status':'ok' if sentiment.MODEL.exists() and DICT_PATH.exists() else 'degraded','sentiment_model':sentiment.version(),'aspect_dict':'2026-11-v1'})
@app.post('/v1/sentiment')
def sentiments(p:Texts):return ok({'items':sentiment.predict([clean(t) for t in p.texts])})
@app.post('/v1/aspects')
def aspects(p:Texts):return ok({'items':[{'aspects':extract(clean(t),p.dictionary)} for t in p.texts]})
@app.post('/v1/fake')
def fake(p:Reviews):return ok({'items':evaluate(p.reviews)})
@app.post('/v1/analyze')
@app.post('/internal/analyze',include_in_schema=False)
def analyze(p:dict):
    rs=p.get('reviews',[]);texts=[clean(r['content']) for r in rs]
    ss=sentiment.predict(texts);aa=[extract(t,p.get('dictionary')) for t in texts]
    ff=evaluate(rs,ss,aa)
    return ok({'items':[{**s,**f,'aspects':a} for s,f,a in zip(ss,ff,aa)]})
@app.post('/v1/index')
@app.post('/internal/index',include_in_schema=False)
def index(p:dict):
    # 无数据库的算法服务必须由调用者携带评论；仅凭商品编号不可取数。
    if 'reviews' not in p:raise HTTPException(400,'请由业务服务传入 reviews，算法服务不读取数据库')
    return ok({**calculate(p['reviews'],p['period_end'],p.get('params'),p.get('priors')),'param_version':p.get('param_version','v1-2026-10')})
@app.get('/v1/jobs/{job_id}')
def jobs(job_id:str):raise HTTPException(404,'任务由业务服务 /api/v1/mining/tasks 管理')
