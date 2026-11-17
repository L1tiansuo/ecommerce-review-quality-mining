"""开发者导入示例：所有数据经业务接口校验，不直连数据库。"""
import argparse,requests,os
p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--url',default='http://localhost:8080');p.add_argument('--user',default='analyst');a=p.parse_args()
password=os.environ.get('QR_PASSWORD') or input('登录口令：')
login=requests.post(a.url+'/api/v1/auth/login',json={'username':a.user,'password':password,'captcha':'2026'},timeout=30);login.raise_for_status();token=login.json()['data']['token']
with open(a.file,'rb') as f:
    r=requests.post(a.url+'/api/v1/imports',headers={'Authorization':'Bearer '+token},files={'file':f},timeout=180);r.raise_for_status();print(r.json())
