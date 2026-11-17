"""生成 300 条方面标注表（CSV，UTF-8 BOM，Excel 可直接打开）。

用法：
    python scripts/make_label_sheet.py            # 默认 300 条
    python scripts/make_label_sheet.py --n 300 --seed 42
产出：
    data/eval/aspects_label.csv   待标注表（原文 + 空标注列）
    data/eval/aspects_legend.csv  特性码对照表
    data/eval/标注说明.md          给标注人的规则
只从 source_type=1（真实语料）里抽，且不预填任何规则结果，避免评测自证。
"""
import argparse
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICT = json.loads((ROOT / "algo/data/aspect_dict.json").read_text(encoding="utf-8"))

INSTRUCTION = """# 方面标注说明（300 条）

## 要做什么

每条评论读一遍，判断它在评价**商品的哪个具体方面**，以及对这个方面的**态度**。
一条评论可能有 0 个、1 个或多个方面。

## 怎么填

在 `aspects_label.csv` 的「标注」列，按 `特性:极性` 写，多个用分号隔开：

```
续航:负;做工:正
包装:正
```

- 特性写中文名（见 `aspects_legend.csv`）或英文码都可以，中英文混用也行；
- 极性只有三种：`正` / `负` / `中`（也可以用 `1` / `-1` / `0`）；
- **只写评论里明确提到的方面**。泛泛一句「很好」「不错」没有具体方面，就留空；
- 不要根据星级去猜方面，只按文本判断；
- 拿不准的边界情况，写在「备注」列，标完一起讨论。

## 例子

| 原文 | 标注 |
|---|---|
| 续航太虚标了，说 8 小时实际 4 小时就没电，不过做工还行 | `续航:负;做工:正` |
| 快递很快，第二天就到了 | `配送时效:正` |
| 内容很实用，装帧也漂亮 | `内容品质:正;外观设计:正` |
| 一般般吧 | （留空） |

## 分给两个人时

- 第 1–50 行**两人都标**（用来算 Kappa，检验标准是否一致）；
- 第 51–300 行按单双号各标一半。

## 标完

```bash
python scripts/import_labels.py      # CSV → data/eval/aspects.jsonl，会报错指出填错的行
python scripts/evaluate.py --aspects data/eval/aspects.jsonl
```
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--overlap", type=int, default=50, help="前 N 行标为双标行")
    a = ap.parse_args()

    reviews = list(csv.DictReader(open(ROOT / "data/seed/reviews.csv", encoding="utf-8-sig")))
    real = [r for r in reviews if r.get("source_type") == "1"]
    sample = random.Random(a.seed).sample(real, min(a.n, len(real)))

    out = ROOT / "data/eval/aspects_label.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["序号", "review_id", "product_id", "双标", "原文", "标注", "备注"])
        for i, r in enumerate(sample, 1):
            w.writerow([i, r.get("review_id", ""), r.get("product_id", ""),
                        "是" if i <= a.overlap else "", r["content_raw"], "", ""])

    with (ROOT / "data/eval/aspects_legend.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["维度", "维度码", "特性中文名", "特性码", "同义词（系统会识别的写法）"])
        for d in DICT["dimensions"]:
            for ft in d["features"]:
                w.writerow([d["name"], d["code"], ft["name"], ft["code"], " / ".join(ft["synonyms"])])

    (ROOT / "data/eval/标注说明.md").write_text(INSTRUCTION, encoding="utf-8")

    print("标注表：%s（%d 行，其中前 %d 行为双标）" % (out, len(sample), a.overlap))
    print("对照表：%s" % (ROOT / "data/eval/aspects_legend.csv"))
    print("说明：  %s" % (ROOT / "data/eval/标注说明.md"))
    print("词表版本：%s，%d 维度 / %d 特性" % (
        DICT.get("version"),
        len(DICT["dimensions"]),
        sum(len(d["features"]) for d in DICT["dimensions"]),
    ))


if __name__ == "__main__":
    main()
