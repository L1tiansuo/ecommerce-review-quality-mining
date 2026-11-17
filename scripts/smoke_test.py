"""运行中系统的端到端验收：创建带“测试”标记的隔离商品和批次。

用法：QR_PASSWORD设为管理员口令，python scripts/smoke_test.py --url ...
不直接连接数据库。测试结果如实写入docs/integration_results.json。
"""
import argparse,requests,csv,io,time,json,os,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8080');a=p.parse_args();base=a.url+'/api/v1';root=Path(__file__).resolve().parents[1]
results=[];password=os.environ.get('QR_PASSWORD','QrDemo2026!')
def login(user):
    r=requests.post(base+'/auth/login',json={'username':user,'password':password,'captcha':'2026'},timeout=30);r.raise_for_status();return {'Authorization':'Bearer '+r.json()['data']['token']}
headers=login('admin')
def call(method,path,**kwargs):
    r=requests.request(method,base+path,headers=headers,timeout=180,**kwargs)
    if r.status_code!=200:raise AssertionError(f'{path}: {r.status_code} {r.text[:400]}')
    return r.json()['data']
def check(name,fn):
    try:detail=fn();results.append({'check':name,'passed':True,'detail':detail});print('PASS',name,flush=True)
    except Exception as e:results.append({'check':name,'passed':False,'detail':str(e)});print('FAIL',name,str(e),flush=True)
def permission():
    assert requests.get(base+'/products').status_code==401
    h=login('viewer');assert requests.post(base+'/mining/tasks',headers=h,json={}).status_code==403
    h=login('analyst');assert requests.get(base+'/admin/users',headers=h).status_code==403
    return '未登录401、只读写入403、分析师管理403'
check('认证与角色权限',permission)
stamp=int(time.time());pid=800000000+stamp%10000000;category=7000000+stamp%1000000
def master():
    call('POST','/admin/categories',json={'id':category,'name':'自动化测试品类'})
    call('POST','/admin/products',json={'id':pid,'name':'自动化测试商品','category_id':category,'supplier_id':1})
    r=requests.post(base+'/admin/products',headers=headers,json={'id':pid+1,'name':'错误外键测试','category_id':-999,'supplier_id':1});assert r.status_code==400
    return {'product_id':pid,'fk_rejected':True}
check('AC-03 主数据与外键',master)
batch=None
def upload_rows(rows):
    f=io.StringIO();w=csv.writer(f);w.writerow(['product_id','content_raw','rating','review_time','source_type']);w.writerows(rows)
    return call('POST','/imports',files={'file':('test.csv',f.getvalue().encode('utf-8-sig'),'text/csv')})
def importing():
    global batch
    text='质量很好，包装完美，联系13812345678。'
    rows=[[pid,text,5,'2026-11-01 12:00:00',3] for _ in range(9)]+[[-1,'外键错误评论',5,'2026-11-01 12:00:00',3]]
    b=upload_rows(rows);batch=b['id'];assert b['success']==9 and b['failed']==1 and b['skipped']==8
    got=call('GET','/reviews',params={'product_id':pid});assert '13812345678' not in json.dumps(got,ensure_ascii=False)
    assert len(json.loads(b['errors']))==1
    fail=upload_rows([[-1,'错误评论样本',5,'2026-11-01 12:00:00',3]]*6+[[pid,'正常测试评论内容',5,'2026-11-01 12:00:00',3]]*4)
    assert fail['status']==2 and fail['success']==0
    return {'batch':batch,'valid':9,'invalid':1,'duplicates':8,'over_50_percent_rollback':True}
check('AC-01/02 导入错误、重复、脱敏与回滚',importing)
def task(version='v1-2026-10',product=900000001):
    t=call('POST','/mining/tasks',json={'scope_type':1,'scope_value':str(product),'param_version':version,'period_start':'2026-11-01','period_end':'2026-11-09'})
    deadline=time.monotonic()+150
    while time.monotonic()<deadline:
        item=next(x for x in call('GET','/mining/tasks') if x['id']==t['id'])
        if item['status'] in (2,3,4):
            assert item['status']==2,item['message'];return item
        time.sleep(1)
    raise AssertionError('任务超时')
def mining():
    t=task();profile=call('GET','/products/900000001/profile');assert profile['indices'] and len(profile['indices'][0]['dims'])==6
    rows=call('GET','/reviews',params={'product_id':900000001})['items'];assert all(r['model_version'] for r in rows)
    return {'task':t['id'],'progress':t['progress'],'qi':profile['indices'][0]['qi']}
check('AC-04/06 挖掘与指数功能链路（算法质量另评）',mining)
def versions():
    default=call('GET','/dictionaries')['params'][0];params=json.loads(default['params_json']);version='test-'+str(stamp)
    params['weights']['quality']=.30;params['weights']['appearance']=.10
    call('POST','/admin/params',json={'version':version,'params':params});task(version)
    rows=call('GET','/products/900000001/profile')['indices'];assert {'v1-2026-10',version}<={r['param_version'] for r in rows}
    return {'old_version_preserved':True,'new_version':version}
check('AC-07 新旧参数版本并存',versions)
def alert_test():
    call('POST','/alerts/scan');first=call('GET','/alerts');call('POST','/alerts/scan');second=call('GET','/alerts');assert first['total']==second['total']
    pending=call('GET','/alerts',params={'status':0});assert pending['items'];row=pending['items'][0]
    call('POST',f"/alerts/{row['id']}/dispose",json={'status':1,'note':'自动化验收：已核对评论证据'})
    again=requests.post(base+f"/alerts/{row['id']}/dispose",headers=headers,json={'status':2,'note':'重复处置'});assert again.status_code==409
    disposed=call('GET','/alerts',params={'status':1});assert any(x['id']==row['id'] and x['disposed_by']=='admin' and x['disposed_at'] for x in disposed['items'])
    return {'suppressed':True,'disposition_logged':True,'conflict_409':True}
check('AC-08/09 预警抑制、处置与审计',alert_test)
def retrieval_export():
    query={'product_id':900000001,'dimension':'quality','sentiment':-1};rows=call('GET','/reviews',params=query);assert rows['total']>0
    r=requests.get(base+'/reports/export',headers=headers,params={'type':'reviews',**query});assert r.status_code==200
    exported=list(csv.DictReader(io.StringIO(r.content.decode('utf-8-sig'))));assert len(exported)==rows['total']
    pdf=requests.get(base+'/reports/export',headers=headers,params={'type':'alerts','format':'pdf'});assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    return {'filtered_rows':rows['total'],'csv_rows':len(exported),'pdf_bytes':len(pdf.content)}
check('AC-11 组合检索与CSV/PDF导出',retrieval_export)
def undo():
    assert batch;call('POST',f'/imports/{batch}/undo');assert call('GET','/reviews',params={'product_id':pid})['total']==0
    return '批次评论已撤销'
check('AC-01 撤销批次',undo)
def perf():
    profile_times=[];dash_times=[]
    for _ in range(20):
        t=time.perf_counter();call('GET','/products/900000001/profile');profile_times.append(time.perf_counter()-t)
        t=time.perf_counter();d=call('GET','/dashboard/overview');dash_times.append(time.perf_counter()-t)
    return {'environment':'本机H2开发模式，非规定2核4GB/MySQL验收环境','n':20,'profile_p95_seconds':sorted(profile_times)[18],'dashboard_p95_seconds':sorted(dash_times)[18],'stats':d['stats']}
check('AC-10 聚合查询与本机响应测量',perf)
report={'results':results,'all_passed':all(r['passed'] for r in results),'algorithm_acceptance':'待人工三分类与方面金标，不包含在功能通过结论中','deployment':'H2开发模式，Docker/MySQL尚需目标环境验收'}
(root/'docs/integration_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if not report['all_passed']:raise SystemExit(1)
