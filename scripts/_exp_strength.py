# -*- coding: utf-8 -*-
"""对比：方面强度用 43 词规则 vs 用训练模型（同窗文本）。"""
import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(r"D:\Learning\Program\quality-review")
sys.path.insert(0, str(ROOT / "algo"))

import ahocorasick  # noqa: E402

from core.aspect import DEFAULT, extract  # noqa: E402
from core.preprocess import clean  # noqa: E402
from core import sentiment  # noqa: E402

texts = []
with open(ROOT / "data/seed/reviews.csv", encoding="utf-8-sig") as f:
    for i, r in enumerate(csv.DictReader(f)):
        texts.append(clean(r["content_raw"]))
        if i >= 4000:
            break

ac = ahocorasick.Automaton()
for d in DEFAULT["dimensions"]:
    for ft in d["features"]:
        for w in ft["synonyms"]:
            ac.add_word(w, (w, ft["code"], d["code"]))
ac.make_automaton()


def windows(text):
    out = []
    for end, (word, feature, dim) in ac.iter(text):
        start = end - len(word) + 1
        left = max([text.rfind(p, 0, start) for p in "，。！？；,!?;"] + [-1]) + 1
        rights = [i for p in "，。！？；,!?;" if (i := text.find(p, end + 1)) >= 0]
        right = min(rights) if rights else len(text)
        out.append((word, feature, dim, text[max(left, start - 12):min(right, end + 13)]))
    return out


rule_vals, model_vals, pairs = [], [], []
n_win = 0
for t in texts:
    ws = windows(t)
    if not ws:
        continue
    scores = sentiment.predict([w[3] for w in ws])
    rule = extract(t)
    by_word = {a["word"]: a["strength"] for a in rule}
    for (word, feat, dim, _), sc in zip(ws, scores):
        n_win += 1
        rs = by_word.get(word, 0.0)
        rule_vals.append(rs)
        model_vals.append(sc["score"])
        pairs.append((rs, sc["score"]))

print("样本评论 %d，窗口 %d" % (len(texts), n_win))
print("规则强度: mean=%+.3f  |s|中位数=%.3f  零值占 %.1f%%"
      % (statistics.mean(rule_vals), statistics.median([abs(v) for v in rule_vals]),
         100 * sum(1 for v in rule_vals if v == 0) / len(rule_vals)))
print("模型强度: mean=%+.3f  |s|中位数=%.3f  <0占 %.1f%%  >0占 %.1f%%"
      % (statistics.mean(model_vals), statistics.median([abs(v) for v in model_vals]),
         100 * sum(1 for v in model_vals if v < -0.2) / len(model_vals),
         100 * sum(1 for v in model_vals if v > 0.2) / len(model_vals)))
print("映射后维度分 s=(mean+1)/2 → 规则 %.3f / 模型 %.3f"
      % ((statistics.mean(rule_vals) + 1) / 2, (statistics.mean(model_vals) + 1) / 2))
