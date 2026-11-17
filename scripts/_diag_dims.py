# -*- coding: utf-8 -*-
"""诊断：方面强度分布（规则词表 vs 模型），定位 QI 挤在 55-59 的原因。"""
import csv
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\Learning\Program\quality-review")
sys.path.insert(0, str(ROOT / "algo"))

from core.aspect import extract  # noqa: E402
from core.preprocess import clean  # noqa: E402

rows = []
with open(ROOT / "data/seed/reviews.csv", encoding="utf-8") as f:
    for i, r in enumerate(csv.DictReader(f)):
        rows.append(r)
        if i >= 20000:
            break

print("reviews loaded:", len(rows))
hits = 0
zero = 0
strengths = []
per_review = []
for r in rows:
    a = extract(clean(r["content_raw"]))
    per_review.append(len(a))
    for x in a:
        hits += 1
        s = x["strength"]
        strengths.append(s)
        if s == 0:
            zero += 1

print("aspect hits:", hits, "per review:", round(hits / len(rows), 2))
print("strength==0:", zero, "=%.1f%%" % (100 * zero / max(hits, 1)))
vals = [abs(s) for s in strengths]
print("|strength| mean: %.3f  median: %.3f" % (statistics.mean(vals), statistics.median(vals)))
buckets = Counter()
for s in strengths:
    if s == 0:
        buckets["0"] += 1
    elif abs(s) < 0.2:
        buckets["(0,0.2)"] += 1
    elif abs(s) < 0.5:
        buckets["[0.2,0.5)"] += 1
    elif abs(s) < 0.8:
        buckets["[0.5,0.8)"] += 1
    else:
        buckets["[0.8,1]"] += 1
for k in ["0", "(0,0.2)", "[0.2,0.5)", "[0.5,0.8)", "[0.8,1]"]:
    print("  %-12s %6d  %5.1f%%" % (k, buckets[k], 100 * buckets[k] / max(hits, 1)))

print("reviews with 0 aspects: %.1f%%" % (100 * sum(1 for n in per_review if n == 0) / len(rows)))
print("mean aspects/review: %.2f" % (sum(per_review) / len(per_review)))
