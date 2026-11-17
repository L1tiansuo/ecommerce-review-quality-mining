"""评测：情感分类 + 方面识别。

不造评测值：方面金标缺失时写 not_evaluated；三分类缺中评金标也明确标为未达标。

用法：
    python scripts/evaluate.py                                   # 只跑情感，方面标 not_evaluated
    python scripts/evaluate.py --aspects data/eval/aspects.jsonl  # 加上方面 P/R/F1
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "algo"))
from core.sentiment import predict, version  # noqa: E402
from core.aspect import extract  # noqa: E402
from sklearn.metrics import classification_report, confusion_matrix  # noqa: E402

DICT = json.loads((ROOT / "algo/data/aspect_dict.json").read_text(encoding="utf-8"))
FEATURE2DIM = {f["code"]: d["code"] for d in DICT["dimensions"] for f in d["features"]}
DIM_NAME = {d["code"]: d["name"] for d in DICT["dimensions"]}


def overlap(a_start, a_end, b_start, b_end, tol=3):
    if a_start < 0 or b_start < 0:
        return True  # 金标没标出位置时按“命中该特性”算
    return not (a_end + tol < b_start or b_end + tol < a_start)


def aspect_metrics(gold_rows):
    """按特性（feature_code）粒度算 P/R/F1，并单独统计位置定位与方面情感。

    人工标注只要求写“哪个特性、什么极性”，不要求数出字符位置，
    因此主指标按特性是否出现来算；位置只用于额外的一致性统计。
    """
    tp = fp = fn = 0
    loc_ok = loc_n = 0
    pol_ok = pol_n = 0
    per_feature = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    per_dim = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for row in gold_rows:
        text = row["text"]
        gold = row.get("aspects") or []
        pred = extract(text)

        gold_codes = {g["feature_code"] for g in gold}
        pred_codes = {p["feature_code"] for p in pred}

        for code in gold_codes & pred_codes:
            tp += 1
            per_feature[code]["tp"] += 1
            per_dim[FEATURE2DIM.get(code, "?")]["tp"] += 1
            g = next(x for x in gold if x["feature_code"] == code)
            p = next(x for x in pred if x["feature_code"] == code)
            loc_n += 1
            if overlap(g.get("start", -1), g.get("end", -1), p["start"], p["end"]):
                loc_ok += 1
            pol_n += 1
            if g.get("polarity") == p["polarity"]:
                pol_ok += 1
        for code in gold_codes - pred_codes:
            fn += 1
            per_feature[code]["fn"] += 1
            per_dim[FEATURE2DIM.get(code, "?")]["fn"] += 1
        for code in pred_codes - gold_codes:
            fp += 1
            per_feature[code]["fp"] += 1
            per_dim[FEATURE2DIM.get(code, "?")]["fp"] += 1

    def prf(t, f, n):
        p = t / max(1, t + f)
        r = t / max(1, t + n)
        return p, r, 2 * p * r / max(1e-9, p + r)

    precision, recall, f1 = prf(tp, fp, fn)
    dims = {}
    for code, v in per_dim.items():
        p, r, s = prf(v["tp"], v["fp"], v["fn"])
        dims[code] = {"name": DIM_NAME.get(code, code), "precision": round(p, 4),
                      "recall": round(r, 4), "f1": round(s, 4), **v}
    features = {}
    for code, v in per_feature.items():
        p, r, s = prf(v["tp"], v["fp"], v["fn"])
        features[code] = {"dimension": FEATURE2DIM.get(code), "precision": round(p, 4),
                          "recall": round(r, 4), "f1": round(s, 4), **v}

    return {
        "n": len(gold_rows),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp, "fp": fp, "fn": fn,
        "localization_accuracy": round(loc_ok / max(1, loc_n), 4),
        "aspect_sentiment_accuracy": round(pol_ok / max(1, pol_n), 4),
        "by_dimension": dict(sorted(dims.items(), key=lambda kv: -(kv[1]["tp"] + kv[1]["fn"]))),
        "by_feature": dict(sorted(features.items(), key=lambda kv: -(kv[1]["tp"] + kv[1]["fn"]))),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--testset", default=str(ROOT / "data/eval/test_1000.csv"))
    ap.add_argument("--aspects", default=None, help="人工标注的 aspects.jsonl")
    ap.add_argument("--out", default=str(ROOT / "docs/metrics.json"))
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.testset, encoding="utf-8-sig")))
    truth = [r["label"] for r in rows]
    pred = [r["label"] for r in predict([r["text"] for r in rows])]
    report = classification_report(truth, pred, labels=["pos", "neu", "neg"],
                                   output_dict=True, zero_division=0)
    result = {
        "model_version": version(),
        "dict_version": DICT.get("version"),
        "sentiment": {
            "macro_f1": report["macro avg"]["f1-score"],
            "per_class": report,
            "n": len(rows),
            "confusion_matrix": confusion_matrix(truth, pred, labels=["pos", "neu", "neg"]).tolist(),
            "labels": ["pos", "neu", "neg"],
            "valid_three_class_acceptance": set(truth) == {"pos", "neu", "neg"},
        },
        "aspect": {"status": "not_evaluated", "reason": "需要 300 条独立人工方面标注"},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if a.aspects:
        gold = [json.loads(line) for line in open(a.aspects, encoding="utf-8") if line.strip()]
        pending = [g for g in gold if g.get("status") == "pending_human_annotation"]
        if pending:
            raise ValueError("还有 %d 条处于 pending_human_annotation，先标完或删掉这些行" % len(pending))
        metrics = aspect_metrics(gold)
        result["aspect"] = metrics
        result["aspect_sentiment"] = {
            "accuracy": metrics["aspect_sentiment_accuracy"],
            "n": metrics["tp"],
        }

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    s = result["aspect"]
    if "precision" in s:
        print("方面识别：P=%.3f R=%.3f F1=%.3f（n=%d，TP=%d FP=%d FN=%d）" % (
            s["precision"], s["recall"], s["f1"], s["n"], s["tp"], s["fp"], s["fn"]))
        print("位置一致率 %.3f，方面情感准确率 %.3f" % (
            s["localization_accuracy"], s["aspect_sentiment_accuracy"]))
        print("按维度：")
        for code, v in s["by_dimension"].items():
            print("  %-10s P=%.3f R=%.3f F1=%.3f  (tp=%d fp=%d fn=%d)" % (
                v["name"], v["precision"], v["recall"], v["f1"],
                v["tp"], v["fp"], v["fn"]))
    else:
        print("方面识别：not_evaluated（%s）" % s.get("reason", ""))
    print("情感 macro-F1：%.4f（n=%d）" % (result["sentiment"]["macro_f1"], result["sentiment"]["n"]))
    print("写出 %s" % a.out)


if __name__ == "__main__":
    main()
