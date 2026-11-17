from fastapi.testclient import TestClient
from main import app
client=TestClient(app)
def test_contract():
    r=client.post('/v1/sentiment',json={'texts':['质量很好']});assert r.status_code==200;assert 'model_version' in r.json()['data']
    assert client.post('/v1/aspects',json={'texts':['包装很差']}).json()['data']['items'][0]['aspects']
def test_limits_and_no_database():
    assert client.post('/v1/sentiment',json={'texts':['中'*12000]}).status_code==413
    assert client.post('/v1/index',json={'product_id':1}).status_code==400
