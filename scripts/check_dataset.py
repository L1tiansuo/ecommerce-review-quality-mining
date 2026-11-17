import csv,json
from collections import Counter
from pathlib import Path
from datetime import datetime,timedelta
root=Path(__file__).resolve().parents[1];rows=list(csv.DictReader(open(root/'data/seed/reviews.csv',encoding='utf-8-sig')));m=json.loads((root/'data/seed/manifest.json').read_text(encoding='utf-8'));end=datetime.fromisoformat(m['demo_end']+' 23:59:59');counts=Counter(r['product_id'] for r in rows);stars=Counter(r['rating'] for r in rows)
report={'products':len(counts),'reviews':len(rows),'head_tail_ratio':max(counts.values())/min(counts.values()),'five_star_share':stars['5']/len(rows),'recent7':sum(datetime.fromisoformat(r['review_time'])>=end-timedelta(days=7) for r in rows),'future':sum(datetime.fromisoformat(r['review_time'])>end for r in rows),'months':len(set(r['review_time'][:7] for r in rows)),'scenarios':dict(Counter(r['scenario'] for r in rows if r['scenario']))}
(root/'docs/dataset_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(report)
assert report['products']>=1000 and report['reviews']>=20000 and report['future']==0 and report['recent7']>0
