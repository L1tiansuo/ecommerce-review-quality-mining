"""对比词表 v1/v2 的命中覆盖；只读 data/seed/reviews.csv，抽样即可。"""
import csv
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "algo"))
from core.aspect import extract  # noqa: E402

rows = list(csv.DictReader(open(ROOT / "data/seed/reviews.csv", encoding="utf-8-sig")))
real = [r for r in rows if r.get("source_type") == "1"]
sample = random.Random(7).sample(real, min(20000, len(real)))

hits = [len(extract(r["content_raw"])) for r in sample]
zero = sum(1 for h in hits if h == 0)
by_feature = {}
for r in sample:
    for a in extract(r["content_raw"]):
        by_feature[a["feature_code"]] = by_feature.get(a["feature_code"], 0) + 1

print("样本 %d 条" % len(sample))
print("命中次数合计 %d（%.2f 次/条）" % (sum(hits), sum(hits) / len(hits)))
print("零命中占比 %.1f%%" % (100.0 * zero / len(hits)))
print("单条命中分布 中位数=%d 均值=%.2f 最大=%d" % (statistics.median(hits), statistics.mean(hits), max(hits)))
print("按特性命中量 top10：")
for k, v in sorted(by_feature.items(), key=lambda kv: -kv[1])[:10]:
    print("  %-14s %6d" % (k, v))
print("有命中的特性数 %d" % len(by_feature))
