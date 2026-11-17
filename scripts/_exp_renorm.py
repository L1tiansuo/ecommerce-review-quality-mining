# -*- coding: utf-8 -*-
"""候选方案对比：权重按"有证据的维度"归一 + 丢弃零强度证据 + 不同 m。"""
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\Learning\Program\quality-review")
DIMS = [("quality", 0.28), ("appearance", 0.12), ("logistics", 0.15),
        ("service", 0.13), ("value", 0.17), ("package", 0.15)]

reviews, scenario_of = {}, {}
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
        if r:
            by_product[r[0]].append((r[1], a.get("aspects") or [], a.get("fake_prob", 0)))

END = datetime.fromisoformat("2026-10-30")


def qi_of(revs, m, renormalize, half=90):
    scores, covered = [], 0.0
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
        score = (n * s + m * 0.55) / (n + m)
        scores.append((score, w, n))
        if n > 0:
            covered += w
    if renormalize and covered > 0:
        return 100 * sum(sc * w for sc, w, n in scores if n > 0) / covered
    return 100 * sum(sc * w for sc, w, n in scores)


for renorm in (False, True):
    for m in (10, 20, 30):
        qis = {pid: qi_of(revs, m, renorm) for pid, revs in by_product.items()}
        vals = sorted(qis.values())
        q = lambda p: vals[int(p * (len(vals) - 1))]
        red = sum(1 for v in vals if v < 60)
        print("renorm=%-5s m=%-3d p5=%.1f p25=%.1f p50=%.1f p75=%.1f p95=%.1f spread=%.1f red<60=%d"
              % (renorm, m, q(.05), q(.25), q(.5), q(.75), q(.95), q(.95) - q(.05), red))
        if renorm and m == 10:
            sc = sorted(((s, round(qis.get(pid, float("nan")), 1)) for pid, s in scenario_of.items()))
            print("      剧本:", sc)
            for thr in (58, 60, 62, 65):
                print("        QI<%d: %d (%.1f%%)" % (thr, sum(1 for v in vals if v < thr),
                                                     100 * sum(1 for v in vals if v < thr) / len(vals)))
