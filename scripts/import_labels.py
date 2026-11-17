"""把人工标注表转成 evaluate.py 能吃的 aspects.jsonl。

用法：
    python scripts/import_labels.py                 # 默认读 data/eval/aspects_label.csv
    python scripts/import_labels.py --in xxx.csv --out data/eval/aspects.jsonl

标注列写法：`续航:负;做工:正`，分隔符支持 ; ； , ， 和换行；极性支持 正/负/中、+/-/0、1/-1/0。
特性可写中文名、英文码或同义词（同义词会自动归一为该特性）。
留空的单元格视为「这条评论没有方面」，会作为负样本保留。
"""
import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICT = json.loads((ROOT / "algo/data/aspect_dict.json").read_text(encoding="utf-8"))

NAME2CODE = {}
SYN2CODE = {}
CODE2FEATURE = {}
for d in DICT["dimensions"]:
    for ft in d["features"]:
        NAME2CODE[ft["name"]] = ft["code"]
        CODE2FEATURE[ft["code"]] = ft
        for s in ft["synonyms"]:
            SYN2CODE[s] = ft["code"]

POLARITY = {
    "正": 1, "+": 1, "1": 1, "积极": 1, "正面": 1,
    "负": -1, "-": -1, "-1": -1, "消极": -1, "负面": -1,
    "中": 0, "0": 0, "中性": 0, "": 0,
}

SPLIT = re.compile(r"[;；,，\n]+")


def resolve(token):
    token = token.strip()
    if not token:
        return None
    if token in NAME2CODE:
        return NAME2CODE[token]
    if token in CODE2FEATURE:
        return token
    if token in SYN2CODE:
        return SYN2CODE[token]
    # 别名兜底：去掉“方面/问题/质量”等后缀再试一次
    for suffix in ("方面", "问题", "质量", "服务"):
        t = token.replace(suffix, "")
        if t in NAME2CODE:
            return NAME2CODE[t]
        if t in SYN2CODE:
            return SYN2CODE[t]
    return None


def locate(text, code, token):
    """在原文里定位该方面：先用标注者写的词，再用该特性的同义词，都找不到就返回 -1。"""
    for cand in [token] + (CODE2FEATURE[code]["synonyms"] if code in CODE2FEATURE else []):
        if not cand:
            continue
        i = text.find(cand)
        if i >= 0:
            return cand, i, i + len(cand)
    return "", -1, -1


def parse_cell(cell):
    items = []
    for part in SPLIT.split(cell or ""):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            name, pol = part.rsplit(":", 1)
        elif "：" in part:
            name, pol = part.rsplit("：", 1)
        else:
            name, pol = part, ""
        code = resolve(name)
        items.append((name.strip(), code, POLARITY.get(pol.strip(), None)))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=str(ROOT / "data/eval/aspects_label.csv"))
    ap.add_argument("--out", default=str(ROOT / "data/eval/aspects.jsonl"))
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.src, encoding="utf-8-sig")))
    problems, records, labeled, empty = [], [], 0, 0

    for r in rows:
        idx = r.get("序号", "?")
        text = (r.get("原文") or "").strip()
        cell = (r.get("标注") or "").strip()
        aspects = []
        if not text:
            continue
        if cell:
            labeled += 1
        else:
            empty += 1
        for name, code, pol in parse_cell(cell):
            if code is None:
                problems.append("第 %s 行：认不出的特性「%s」" % (idx, name))
                continue
            if pol is None:
                problems.append("第 %s 行：极性「%s」无法识别（用 正/负/中）" % (idx, name))
                continue
            word, start, end = locate(text, code, name)
            aspects.append({"word": word, "feature_code": code, "polarity": pol,
                            "start": start, "end": end})
        records.append({"text": text, "status": "annotated", "aspects": aspects, "seq": idx})

    with open(a.out, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    hits = sum(len(x["aspects"]) for x in records)
    print("读入 %d 行：有标注 %d 行、留空 %d 行；共 %d 个方面" % (len(records), labeled, empty, hits))
    print("写出 %s" % a.out)
    if problems:
        print("\n有 %d 处需要修正：" % len(problems))
        for p in problems[:20]:
            print("  " + p)
        if len(problems) > 20:
            print("  ...（其余省略）")
    else:
        print("格式检查通过，可以跑 evaluate.py --aspects")


if __name__ == "__main__":
    main()
