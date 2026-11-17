import sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'algo'))
from core.qi import calculate
review={'review_time':'2026-11-01','fake_prob':.2,'aspects':[{'dimension':'quality','strength':-.62}]}
started=time.perf_counter();result=calculate([review]*100000,'2026-11-09');seconds=time.perf_counter()-started
report={'reviews':100000,'seconds':seconds,'pass_300s':seconds<=300,'scope':'仅质量指数核心计算，不含NLP、HTTP、数据库','result':result}
(ROOT/'docs/benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(report)
