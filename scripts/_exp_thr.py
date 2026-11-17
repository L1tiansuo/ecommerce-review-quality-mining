# -*- coding: utf-8 -*-
"""在候选参数下，看 QI 分布分位与 5 个剧本商品的 QI，用于确定预警阈值。"""
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Learning\Program\quality-review")
DIMS = [("quality", 0.28), ("appearance", 0.12), ("logistics", 0.15),
        ("service", 0.13), ("value", 0.17), ("package", 0.15)]

reviews = {}
scenario_of = {}
with open(ROOT / "data/seed/reviews.csv", encoding="utf-8-sig") as f:
    for i, r in enumerate(csv.DictReader(f), start=1):
        reviews[i] = (r["product_id"], r["review_time"][:10])
        if r.get("scenario"):
            scenario_of[r["product_id"]] = r["scenario"]

by_product = defaultdict(list)
with open(ROOT / "data/seed/analysis.jsonl", encoding="utf-8") as f:
    for line in f:
        a = json.loads(line)
        r = reviews.get(a["review_id"])
        if not r:
            continue
        by_product[r[0]].append((r[1], a.get("aspects") or [], a.get("fake_prob", 0)))

END = datetime.fromisoformat("2026-10-30")


def qi_of(revs, m, half=90):
    total = 0.0
    for code, w in DIMS:
        num = den = 0.0
        n = 0
        for day, aspects, fp in revs:
            st = [x["strength"] for x in aspects if x.get("dimension") == code and x["strength"] != 0]
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
        total += w * ((n * s + m * 0.55) / (n + m) if n + m else 0.55)
    return 100 * total


for m in (8, 10, 12):
    qis = {pid: qi_of(revs, m) for pid, revs in by_product.items()}
    vals = sorted(qis.values())
    q = lambda p: vals[int(p * (len(vals) - 1))]
    print("m=%d  p1=%.1f p5=%.1f p10=%.1f p25=%.1f p50=%.1f p75=%.1f p90=%.1f p99=%.1f"
          % (m, q(.01), q(.05), q(.1), q(.25), q(.5), q(.75), q(.9), q(.99)))
    sc = [(pid, s, round(qis.get(pid, float("nan")), 1)) for pid, s in scenario_of.items()]
    print("   剧本:", "; ".join("%s=%s" % (s, v) for _, s, v in sorted(sc)))
    for thr in (56, 58, 60, 62, 64):
        print("     QI<%d: %d 个 (%.1f%%)" % (thr, sum(1 for v in vals if v < thr),
                                            100 * sum(1 for v in vals if v < thr) / len(vals)))
