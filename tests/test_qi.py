import math
import pytest
from core.qi import calculate
def test_manual_example_and_reproducibility():
    rows=[{'review_time':'2026-09-15','fake_prob':.12,'aspects':[{'dimension':'quality','strength':-.62}]} for _ in range(200)]
    one=calculate(rows,'2026-09-30');two=calculate(rows,'2026-09-30')
    assert one==two
    d=next(d for d in one['dims'] if d['code']=='quality')
    assert abs(d['score']-(200*.19+30*.55)/230)<1e-8
def test_empty_and_dimension_dedup():
    assert calculate([],'2026-09-30')['qi']==55
    row={'review_time':'2026-09-30','fake_prob':0,'aspects':[{'dimension':'quality','strength':1},{'dimension':'quality','strength':1}]}
    assert calculate([row],'2026-09-30')['dims'][0]['n']==1
def test_invalid_weights_and_future():
    with pytest.raises(ValueError):calculate([],'2026-09-30',{'weights':{'quality':1}})
    r={'review_time':'2026-10-01','fake_prob':0,'aspects':[{'dimension':'quality','strength':1}]}
    assert calculate([r],'2026-09-30')['dims'][0]['n']==0
def test_time_decay_and_risk_weight():
    rows=[{'review_time':'2026-09-30','fake_prob':0,'aspects':[{'dimension':'quality','strength':1}]},{'review_time':'2026-07-02','fake_prob':.5,'aspects':[{'dimension':'quality','strength':-1}]}]
    q=calculate(rows,'2026-09-30');assert abs(q['dims'][0]['score']-(2*.8+30*.55)/32)<1e-8
