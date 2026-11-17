from core.preprocess import clean
from core.aspect import extract
from core.sentiment import local_score
from core.fake_rules import evaluate
from datetime import datetime,timedelta
def test_mask_and_negation():
    assert '13812345678' not in clean('质量很好，电话13812345678，abc@example.com')
    assert local_score('质量不好')<0
    assert local_score('物流不慢')>0
    assert local_score('质量不是不好')>0
def test_aspects_scope():
    rows=extract('包装破损，质量很好。');scores={x['dimension']:x['strength'] for x in rows}
    assert scores['package']<0 and scores['quality']>0
def test_explanations_and_grouping():
    rs=[{'review_id':i,'product_id':'a','content':'质量差，垃圾。','rating':5,'review_time':'2026-11-01 12:00:00'} for i in range(5)]
    out=evaluate(rs);assert all(any(h['rule']=='contradict' for h in r['hits']) for r in out)
    assert all(h['detail'] for r in out for h in r['hits'])
def test_template_across_products_not_flagged():
    rs=[{'review_id':i,'product_id':str(i),'content':'商品质量很好，物流很快。','rating':5,'review_time':'2026-11-01'} for i in range(2)]
    assert all(not any(h['rule']=='template' for h in r['hits']) for r in evaluate(rs))

def test_cross_midnight_variance():
    rs=[{'content':'质量很好很满意','rating':5,'review_time':t} for t in ['2026-11-01 23:59:00','2026-11-02 00:01:00']]
    assert len(evaluate(rs))==2
