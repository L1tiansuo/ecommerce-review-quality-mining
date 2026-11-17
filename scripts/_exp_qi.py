# -*- coding: utf-8 -*-
"""离线实验：比较不同先验强度/零强度处理下的 QI 分布与预警数量。"""
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Learning\Program\quality-review")
DIMS = [("quality", 0.28), ("appearance", 0.12), ("logistics", 0.15),
        ("service", 0.13), ("value", 0.17), ("package", 0.15)]

reviews = {}
with open(ROOT / "data/seed/reviews.csv", encoding="utf-8-sig") as f:
    for i, r in enumerate(csv.DictReader(f), start=1):
        reviews[i] = (r["product_id"], r["review_time"][:10])

by_product = defaultdict(list)
n_aspects = defaultdict(int)
with open(ROOT / "data/seed/analysis.jsonl", encoding="utf-8") as f:
    for line in f:
        a = json.loads(line)
        rid = a["review_id"]
        if rid not in reviews:
            continue
        pid, day = reviews[rid]
        if a.get("aspects"):
            n_aspects[pid] += len(a["aspects"])
        by_product[pid].append((day, a.get("aspects") or [], a.get("fake_prob", 0)))

print("products:", len(by_product), "aspects total:", sum(n_aspects.values()))
print("products with 0 aspects:", sum(1 for p in by_product if n_aspects[p] == 0))

END = datetime.fromisoformat("2026-10-30")


def compute(revs, m, drop_zero, half=90):
    out = {}
    for code, w in DIMS:
        num = den = 0.0
        n = 0
        for day, aspects, fp in revs:
            st = [x["strength"] for x in aspects if x.get("dimension") == code
                  and (not drop_zero or x["strength"] != 0)]
            if not st:
                continue
            days = (END - datetime.fromisoformat(day)).days
            if days < 0:
                continue
            ww = math.exp(-math.log(2) * days / half) * (1 - fp)
            num += ww * sum(st) / len(st)
            den += ww
            n += 1
        s = ((num / den if den else 0) + 1) / 2
        out[code] = (n * s + m * 0.55) / (n + m) if (n + m) else 0.55
    qi = 100 * sum(w * out[c] for c, w in DIMS)
    return qi


def report(tag, m, drop_zero):
    qis = []
    for pid, revs in by_product.items():
        q = compute(revs, m, drop_zero)
        qis.append((pid, q))
    vals = sorted(v for _, v in qis)
    def pct(p):
        return vals[int(p * (len(vals) - 1))]
    red = sum(1 for _, v in qis if v < 60)
    orange = sum(1 for _, v in qis if 60 <= v < 70)
    print("%-28s p10=%.1f p50=%.1f p90=%.1f  spread=%.1f  red=%d orange=%d"
          % (tag, pct(0.1), pct(0.5), pct(0.9), pct(0.9) - pct(0.1), red, orange))
    return qis


report("m=30 drop_zero=False (现状)", 30, False)
report("m=30 drop_zero=True", 30, True)
report("m=10 drop_zero=True", 10, True)
report("m=5  drop_zero=True", 5, True)
report("m=1  drop_zero=True", 1, True)

# 维度层面的离散度（以 m=10, drop_zero=True 为例）
revs = by_product[list(by_product)[0]]
