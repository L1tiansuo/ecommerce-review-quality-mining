# 电商商品评论质量分析系统 · 实施手册

> **读者**：另一台电脑上的 DSH 实例（或接手开发的人）。本文档假设你没有任何本项目的历史上下文，只凭这一份文件 + 配套的《软件需求分析规格说明书 V2.0》就能从零把系统做出来。
>
> **定位**：这不是需求文档，是施工图。需求讲"要什么"，这里讲"怎么做、按什么顺序做、做到什么程度算完"。
>
> 遇到本文档与 SRS 冲突时：**以本文档的接口契约和技术参数为准**，以 SRS 的需求编号和验收标准为准绳。两者都指同一件事。

---

## 0. 一分钟理解

一个面向单一电商平台的**评论质量分析系统**：把商品评论清洗后做情感分析、方面识别、刷评识别，聚合成一个 0—100 的**质量指数**，指数异常时按规则生成**分级预警**，质量管理员在界面上**处置并留痕**，最后用驾驶舱和商品画像把结论呈现出来。

五个模块，一条流水线：

```
M1 数据接入与治理 → M2 评论挖掘 → M3 质量指数 → M4 预警与处置 → M5 可视化
```

**规模约束（决定了所有取舍）**：4 人、8 周、单机部署、10 万条评论量级、课程作业定位但要能写进简历。

**不做**：多平台爬虫、工单状态机、整改复评、移动端、微服务拆分、实时流计算、大模型进主链路。

---

## 1. 完成定义（DoD）

全部满足才算交付：

| # | 判定项 | 检验方式 |
|---|---|---|
| 1 | `docker compose up` 起 4 个服务（web / backend / algo / mysql） | 浏览器打开 `http://localhost:8080` 能登录 |
| 2 | 演示数据自动就绪：≥1000 商品、≥2 万评论、≥6 个月指数 | `GET /api/v1/dashboard/overview` 返回非零指标 |
| 3 | 三条主线能现场走通（见 §14 演示脚本） | 照着点，不卡壳 |
| 4 | 情感宏 F1 ≥ 0.85、方面精确率 ≥ 0.85 / 召回 ≥ 0.65 | `python scripts/evaluate.py` 输出的 metrics.json |
| 5 | 指数可复算：同输入同参数版本重算完全一致 | `pytest tests/test_qi.py` |
| 6 | 10 万条指数批算 ≤ 5 分钟 | `scripts/bench_qi.py` 计时 |
| 7 | 画像首屏 P95 ≤ 3 秒 | 浏览器 Network 面板，20 次取 P95 |
| 8 | AC-01…AC-11 全部通过 | §15 自查表逐项打勾 |

---

## 2. 技术栈（锁定，不要换）

| 层 | 选型 | 版本 | 为什么是它 |
|---|---|---|---|
| 前端 | Vue 3 + Vite + Element Plus + ECharts | Vue 3.4 / Vite 5 | 上手快，ECharts 雷达图开箱可用 |
| 业务服务 | Spring Boot | 3.2 + JDK 17 | 课程要求的企业级栈，简历友好 |
| 算法服务 | FastAPI + uvicorn | Python 3.10 / FastAPI 0.110 | 文本处理生态在 Python，独立进程可单独重启 |
| 模型 | scikit-learn（基线）+ PyTorch（可选微调） | sklearn 1.4 / torch 2.2 | 无显卡也能跑，有显卡再上 BERT |
| 数据库 | MySQL | 8.0 | JSON 字段、窗口函数够用 |
| 部署 | Docker Compose | 24+ | 一条命令起全部服务 |

**禁止**：引入 Redis/Kafka/ES（数据量不需要）、引入 Nacos/网关（单机不需要）、把算法塞进 Java（Java 做 NLP 是自找麻烦）。

---

## 3. 仓库结构

```
quality-review/
├─ docker-compose.yml
├─ .env.example
├─ Makefile                 # 常用命令入口（Windows 用 make.ps1 等价实现）
├─ backend/                 # Spring Boot
│  ├─ pom.xml
│  └─ src/main/java/com/qr/
│     ├─ QrApplication.java
│     ├─ controller/        # AuthController, DashboardController, ProductController,
│     │                     # ImportController, MiningController, AlertController, ReportController
│     ├─ service/           # ImportService, QiService, AlertService, DashboardService
│     ├─ repository/        # Spring Data JPA
│     ├─ domain/            # 实体
│     ├─ client/            # AlgoClient（调算法服务的 HTTP 封装）
│     └─ config/            # SecurityConfig, WebConfig, AsyncConfig
├─ algo/                    # FastAPI
│  ├─ requirements.txt
│  ├─ main.py
│  ├─ routers/              # sentiment.py, aspects.py, fake.py, index.py, jobs.py
│  ├─ core/                 # preprocess.py, sentiment.py, aspect.py, fake_rules.py, qi.py
│  ├─ data/                 # aspect_dict.json, stopwords.txt, negation.txt, degree.txt
│  └─ models/               # 训练产物（.pkl / 微调权重），不入 git
├─ web/                     # Vue 3
│  ├─ package.json
│  └─ src/{api,views,components,router,store}
├─ db/
│  ├─ schema.sql            # 建表
│  └─ seed.sql              # 基础字典（品类、规则配置）
├─ data/
│  ├─ raw/                  # 公开数据集（不入 git）
│  └─ seed/                 # 生成的演示数据 CSV
├─ scripts/
│  ├─ build_dataset.py      # yf_amazon → 本系统表结构（抽取/过滤/时间平移/剧本注入）
│  ├─ check_dataset.py      # 四项自检：分布、时间、评分、剧本命中
│  ├─ import_csv.py         # 灌数据（走接口，不直连库）
│  ├─ evaluate.py           # 算法指标评估
│  ├─ bench_qi.py           # 指数批算计时
│  └─ check_data.py         # 数据体检
└─ docs/                    # SRS、设计文档、测试报告
```

---

## 4. 环境自检

```bash
# 需要：JDK 17、Node 18+、Python 3.10+、Docker 24+（或本机 MySQL 8）
java -version && node -v && python --version && docker --version

# 起数据库（只起库，方便开发时反复重启应用）
docker run -d --name qr-mysql -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=qr123456 -e MYSQL_DATABASE=qr \
  mysql:8.0 --character-set-server=utf8mb4

# 建表
mysql -h127.0.0.1 -uroot -pqr123456 qr < db/schema.sql
mysql -h127.0.0.1 -uroot -pqr123456 qr < db/seed.sql
```

三个服务分别启动（开发态）：

```bash
# 算法服务
cd algo && pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# 业务服务
cd backend && ./mvnw spring-boot:run          # Windows: mvnw.cmd spring-boot:run

# 前端
cd web && npm install && npm run dev          # http://localhost:5173，代理 /api 到 8080
```

---

## 5. 数据层

### 5.1 数据来源（三套，各司其职）

| 角色 | 数据集 | 规模与字段 | 获取 |
|---|---|---|---|
| **主数据集** | `yf_amazon`（亚马逊中文评论，ChineseNlpCorpus 收录） | 720 万条评分评论、52 万商品、1 175 个三级类目；`userId / productId / rating(1-5) / timestamp / title / comment` + `products.csv(name, catIds)` | 仓库 `SophonPlus/ChineseNlpCorpus` → `datasets/yf_amazon`（百度网盘） |
| 情感训练 | `online_shopping_10_cats` | 62 774 条，10 品类，`cat / label(0,1) / review` | 同仓库 → `datasets/online_shopping_10_cats`（zip 直下） |
| 跨域测试 | `ChnSentiCorp` | 7 000 余条酒店评论，`label / text` | 同仓库 / HuggingFace `seamew/ChnSentiCorp` |

> **关键判断**：`yf_amazon` 的四列与本系统的输入契约完全对齐，所以它当主数据集，**不需要再合成 product_id、rating、review_time**。10_cats 与 ChnSentiCorp 只有文本+标签，只用于训练和评测情感模型，不进主链路。
>
> 唯一必须做的加工是**时间归一化**（原始评论集中在 2002–2014，且越靠近抓取日越密）：按月加权重排到最近 13 个月，只改绝对时间，不改变同月内的先后顺序。

合规红线：只用公开或平台授权导出的数据；不采集个人信息；入库前对手机号、身份证号脱敏；**时间归一化、合成供应商、剧本商品都要在界面与报告里标注**。

### 5.2 数据准备（`scripts/build_dataset.py`）

> 本节代码已落地在 `D:\Homework\软件工程\Project\scripts\`，可直接运行，实测产出见 5.5。

四步，顺序不能变：

```
1. 抽取    两遍扫 ratings.csv：先按 productId 统计评论量，选出商品子集（≥40 条），
           再分块读明细；过滤 正文<5字 / 完全重复 / rating 或 timestamp 缺失
2. 关联    按 productId 关联 products.csv + categories.csv，补供应商（合成，需标注）
3. 归一化  按时间排序 → 加权分位 → 落到最近 13 个月的月格子（权重 1,1,1,1,1,2,2,2,3,4,6,8,10）
4. 注入    5 个商品埋事件，让五条规则各命中一次（见下）
```

**为什么要"两遍扫描 + 加权分位"**：
- 随机抽 15% 会让每个商品平均只剩 1.4 条，几乎全部进不了 ≥20 的门槛 → 必须先按商品聚合再抽；
- 直接平移（`shift = demo_end - max(ts)`）会留下 12 年跨度，"近 7 天""近 30 天"窗口里几乎没有数据；
- 直接压缩会把 80% 的评论挤进最后两个月，趋势图变成一根陡直的台阶；
- 加权分位兼顾两者：月度呈上升趋势（4.6k → 46k 条），近 90 天的指数窗口有足够样本。

**归一化的硬约束**：最大时间必须 `≤ demo_end`，且最近 7 天要有量——否则 R2「7 日突增」永远触发不了。

**剧本注入**（每条都必须能现场复现，`scenarios.json` 记录埋点）：

| 商品 | 事件 | 目标规则 |
|---|---|---|
| S-01 | 近 30 天评论压成差评，均分 1.3 | R1 指数跌破 70 |
| S-02 | 近 7 天追加 40 条差评 | R2 差评突增 |
| S-03 | 120 条评论挤在 2 小时内（单日 120 条） | R3 刷评·时间聚集 |
| S-04 | 35 条 5 星评论配差评文本 | R4 刷评·评分背离 |
| S-05 | 25 条完全相同的模板好评 | R5 刷评·模板化 |

> S-03 的注入起点必须避开午夜：2 小时窗口跨日会把"单日峰值"拆成两半，自检就会挂。

**实现要点**（完整版见 `Project/scripts/build_dataset.py`）：

```python
# 第一遍：只读 productId 列，统计每商品评论量
counts = pd.read_csv(rp, usecols=[pr])[pr].astype(str).value_counts()
eligible = counts[counts >= 40].sample(frac=1.0, random_state=SEED)   # 打散保留长尾
chosen = set(eligible.index[eligible.cumsum() <= target])

# 第二遍：分块读明细，只留 chosen
for ch in pd.read_csv(rp, chunksize=400_000, low_memory=False):
    ...

# 时间归一化：按时间排序后加权分位落到 13 个月格子
order = ts.rank(method="first").to_numpy() - 1
q = (order + 0.5) / n
b = np.clip(np.searchsorted(np.cumsum(w / w.sum()), q, side="left"), 0, 12)
```

产出：`data/seed/reviews.csv`（19.4 万条，9 列，直接对 SRS 表 7-2 导入契约）、`products.csv`（1 354 商品）、`categories.csv`、`scenarios.json`、`check_report.txt`。

**自检脚本**（`scripts/check_dataset.py`）四项全过才允许导入：

| 检查 | 合格线 |
|---|---|
| 每商品评论数 | 符合长尾，头/尾比 ≥ 10 |
| 时间分布 | 近 7 天有数据；无未来时间；日波动非均匀 |
| 评分分布 | 5 星占比 40%–70%（对得上电商常识，不是全 5 星） |
| 剧本命中 | 5 个事件商品各自触发对应规则，其余商品误报 ≤ 2 |

### 5.3 数据库 DDL

完整脚本放 `db/schema.sql`，核心如下（MySQL 8，utf8mb4，全部 InnoDB）：

```sql
CREATE TABLE category (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(64) NOT NULL,
  parent_id BIGINT NULL,
  KEY idx_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE supplier (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(128) NOT NULL,
  contact VARCHAR(64) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(200) NOT NULL,
  brand VARCHAR(64) NULL,
  category_id BIGINT NOT NULL,
  supplier_id BIGINT NULL,
  launch_time DATETIME NULL,
  status TINYINT NOT NULL DEFAULT 1,     -- 1 在监 0 停售
  KEY idx_cat (category_id),
  CONSTRAINT fk_p_cat FOREIGN KEY (category_id) REFERENCES category(id),
  CONSTRAINT fk_p_sup FOREIGN KEY (supplier_id) REFERENCES supplier(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE import_batch (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_type TINYINT NOT NULL,          -- 1 公开数据集 2 平台导出 3 模拟
  file_name VARCHAR(255) NULL,
  total INT NOT NULL DEFAULT 0,
  success INT NOT NULL DEFAULT 0,
  failed INT NOT NULL DEFAULT 0,
  skipped INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 0,     -- 0 运行 1 完成 2 失败 3 已撤销
  operator VARCHAR(64) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE review (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_id BIGINT NOT NULL,
  content_raw VARCHAR(2000) NOT NULL,
  content_clean VARCHAR(2000) NULL,
  rating TINYINT NULL,
  review_time DATETIME NOT NULL,
  source_type TINYINT NOT NULL,
  batch_id BIGINT NULL,
  user_key VARCHAR(64) NULL,             -- 模拟数据里有；真实数据脱敏后置 NULL
  dup_flag TINYINT NOT NULL DEFAULT 0,
  mask_flag TINYINT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_p_time (product_id, review_time),
  KEY idx_batch (batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE review_analysis (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  review_id BIGINT NOT NULL,
  sentiment TINYINT NOT NULL,            -- 1 好评 0 中评 -1 差评
  confidence DECIMAL(4,3) NOT NULL,
  fake_prob DECIMAL(4,3) NOT NULL DEFAULT 0,
  fake_reason VARCHAR(255) NULL,         -- JSON 数组字符串，便于展示
  model_version VARCHAR(32) NOT NULL,
  analyzed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_review (review_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE review_aspect (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  review_id BIGINT NOT NULL,
  aspect_word VARCHAR(32) NOT NULL,
  feature_code VARCHAR(32) NOT NULL,     -- 标准特性码，如 battery
  dimension_code VARCHAR(32) NOT NULL,   -- 维度码，如 quality
  polarity TINYINT NOT NULL,             -- 1 正 0 中 -1 负
  strength DECIMAL(4,3) NOT NULL,        -- -1 ~ 1
  start_pos INT NULL,
  KEY idx_review (review_id),
  KEY idx_dim (dimension_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE quality_index (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_id BIGINT NOT NULL,
  period_type TINYINT NOT NULL DEFAULT 3,  -- 3 月
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  qi DECIMAL(5,2) NOT NULL,
  grade TINYINT NOT NULL,                  -- 5 优 4 良 3 中 2 差 1 极差
  dim_scores JSON NOT NULL,                -- [{"code":"quality","score":0.237,"n":200}, ...]
  sample_size INT NOT NULL,
  param_version VARCHAR(32) NOT NULL,
  computed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_p_period (product_id, period_type, period_start),
  KEY idx_period (period_start)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE alert (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_id BIGINT NOT NULL,
  rule_code VARCHAR(16) NOT NULL,        -- R1..R5
  level TINYINT NOT NULL,                -- 3 红 2 橙 1 黄
  metric_value DECIMAL(10,4) NULL,
  message VARCHAR(255) NOT NULL,
  status TINYINT NOT NULL DEFAULT 0,     -- 0 待处置 1 已确认 2 已忽略 3 已处理
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  disposed_at DATETIME NULL,
  disposed_by VARCHAR(64) NULL,
  disposal_note VARCHAR(500) NULL,
  KEY idx_status (status, created_at),
  KEY idx_p (product_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE rule_config (
  code VARCHAR(16) PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  threshold_json JSON NOT NULL,
  enabled TINYINT NOT NULL DEFAULT 1,
  updated_by VARCHAR(64) NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE mining_task (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  scope_type TINYINT NOT NULL,           -- 1 商品 2 品类 3 全量
  scope_value VARCHAR(64) NULL,
  params JSON NULL,
  status TINYINT NOT NULL DEFAULT 0,     -- 0 排队 1 运行 2 成功 3 失败 4 取消
  progress INT NOT NULL DEFAULT 0,
  message VARCHAR(500) NULL,
  created_by VARCHAR(64) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sys_user (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL UNIQUE,
  password_hash VARCHAR(100) NOT NULL,   -- BCrypt
  role VARCHAR(16) NOT NULL,             -- ADMIN / ANALYST / VIEWER
  enabled TINYINT NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 6. 算法服务契约

### 6.1 统一约定

- 全部 POST JSON，UTF-8；统一响应包 `{"code":0,"message":"ok","data":{...}}`。
- 单次同步请求文本总量 ≤ 32 KB；超限返回 413。
- 每个响应带 `model_version`，写入数据库，保证结果可追溯。
- 服务启动时检查 `models/` 与 `data/aspect_dict.json`，缺失则 `/v1/health` 返回 `degraded` 并在日志中明确报错（不做静默降级）。

### 6.2 接口清单

| 方法 | 路径 | 输入 | 输出 |
|---|---|---|---|
| POST | `/v1/sentiment` | `{"texts":["..."],"model_version":"auto"}` | `{"model_version":"...","items":[{"label":"pos","confidence":0.93}]}` |
| POST | `/v1/aspects` | `{"texts":["..."]}` | `{"items":[{"aspects":[{"word":"续航","feature_code":"battery","dimension":"quality","polarity":-1,"strength":-0.72,"start":5,"end":7}]}]}` |
| POST | `/v1/fake` | `{"reviews":[{"review_id":1,"content":"...","rating":5,"review_time":"2026-09-01 10:00:00","user_key":"u1"}]}` | `{"items":[{"review_id":1,"fake_prob":0.62,"hits":[{"rule":"template","weight":0.2,"detail":"与 3 条评论相似度>0.8"}]}]}` |
| POST | `/v1/index` | `{"product_id":1001,"period_start":"2026-09-01","period_end":"2026-09-30","param_version":"v1-2026-10"}` | `{"qi":68.5,"grade":3,"sample_size":1000,"param_version":"v1-2026-10","dims":[{"code":"quality","score":0.237,"n":200}]}` |
| GET | `/v1/jobs/{id}` | — | `{"status":"running","progress":42,"message":null}` |
| GET | `/v1/health` | — | `{"status":"ok","sentiment_model":"tfidf-svc-2026.10","aspect_dict":"2026-10-31"}` |

**注意**：`/v1/index` 由算法服务计算，但**入库由业务服务负责**——算法服务无数据库连接。这是刻意的边界，方便单独压测与替换。

### 6.3 情感分析

```python
# 基线：字符级 TF-IDF + 线性模型，2 核机器 1 秒可判 2000 条
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV

vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 3), min_df=3, max_features=200000)
clf = CalibratedClassifierCV(LinearSVC(C=1.0, class_weight="balanced"), cv=3)
```

- 训练集：`online_shopping_10_cats` + `ChnSentiCorp`，二分类标签映射为 pos/neg；中评没有标注，**先做二分类，再用置信度区间 [0.4, 0.6] 划为 neu**（在报告里如实说明这是工程近似）。
- 可选升级：`hfl/chinese-roberta-wwm-ext`，3 epoch，lr 2e-5，batch 32。有显卡才做，**只在基线 macro-F1 < 0.85 时才做**。
- 目标：macro-F1 ≥ 0.85（测试集 1000 条，与训练集同分布但不同商品）。

### 6.4 方面识别（词表 + 规则，不用模型）

`data/aspect_dict.json` 结构：

```json
{
  "version": "2026-10-31",
  "dimensions": [
    {
      "code": "quality", "name": "商品质量", "weight": 0.28,
      "features": [
        {"code": "battery", "name": "续航",
         "synonyms": ["续航", "待机", "掉电", "耗电", "虚标", "用不了多久"]},
        {"code": "connection", "name": "连接稳定性",
         "synonyms": ["断连", "掉线", "失联", "不同步", "连不上"]}
      ]
    },
    {"code": "appearance", "name": "外观设计", "weight": 0.12, "features": [...]},
    {"code": "logistics",  "name": "物流配送", "weight": 0.15, "features": [...]},
    {"code": "service",    "name": "客服服务", "weight": 0.13, "features": [...]},
    {"code": "value",      "name": "性价比",   "weight": 0.17, "features": [...]},
    {"code": "package",    "name": "包装完好", "weight": 0.15, "features": [...]}
  ]
}
```

匹配算法（顺序不能变）：

1. **Aho-Corasick 多模式匹配**扫同义词，得到候选命中与位置。
2. **窗口极性**：以命中词为中心取前后 12 字窗口，用情感模型（或情感词表）判局部极性；窗口内出现否定词（不/没/无/未/别/毫无/谈不上）则极性取反。
3. **程度修饰**：窗口内出现"非常/特别/太/极其"×1.5，"有点/稍微/略"×0.6。
4. **强度**：`strength = clip(polarity_score × degree × (neg ? -1 : 1), -1, 1)`。
5. **去重**：同一特性在一句内多次命中取绝对值最大的一次。

精度优先：若某同义词过于宽泛（如"好"、"快"），要么加限定（"太快"），要么从词表删除。**精确率 < 0.85 时先删词，不要加模型。**

### 6.5 刷评规则（可解释，五条）

```python
RULES = [
    ("burst",     0.30),  # 时间聚集：同商品 24h 内条数 > μ+3σ，且该窗口占比 > 20%
    ("contradict",0.25),  # 评分-文本背离：rating>=4 且 文本情感<-0.3，或 rating<=2 且 >0.3
    ("template",  0.20),  # 模板化：与同商品任一条 SimHash 汉明距离 <= 3，或 3-gram Jaccard > 0.8
    ("short",     0.15),  # 极短：清洗后长度 < 6 且无方面命中
    ("repeat_user",0.10), # 同用户高频：user_key 7 天内同商品 > 3 条，或跨商品 > 10 条
]
fake_prob = min(1.0, sum(w for rule, w in RULES if hit(rule)))
```

- 每条命中都要产出**人能读懂的一句话**（`detail`），存进 `review_analysis.fake_reason`。
- 不设 AUC 目标：没有用户行为与设备信息时，模拟数据上的 AUC 无意义。报告里要写明这个局限。
- `fake_prob` 在指数计算中作为降权因子 `(1 - p)` 使用。

### 6.6 评估脚本

```bash
python scripts/evaluate.py --testset data/eval/test_1000.csv --out report/metrics.json
```

输出必须是可复核的结构：

```json
{
  "sentiment": {"macro_f1": 0.861, "per_class": {"pos": 0.88, "neu": 0.79, "neg": 0.91}, "n": 1000},
  "aspect": {"precision": 0.87, "recall": 0.68, "f1": 0.76, "n": 300},
  "aspect_sentiment": {"accuracy": 0.78, "n": 300},
  "generated_at": "2026-10-31T20:00:00+08:00"
}
```

测试集必须**人工标注、单独留出**（300 条方面标注），不能拿训练集自评。

---

## 7. 业务服务（Spring Boot）

### 7.1 分层

```
controller → service → repository(JPA) → MySQL
                ↓
            AlgoClient (RestTemplate/WebClient) → algo:8001
```

关键点：**所有指标数值由 Java 侧落库，算法服务只算不存**。这样"重算"只是重新调用 + upsert，版本控制简单。

### 7.2 接口（与 SRS 表 8-2 一致，不可改名）

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/api/v1/auth/login` | 登录，返回 JWT | 公开 |
| GET | `/api/v1/dashboard/overview` | 四个指标卡 + 趋势 | VIEWER+ |
| GET | `/api/v1/products/{id}/profile` | 画像聚合（指数、雷达、趋势、情感分布、代表评论） | VIEWER+ |
| GET | `/api/v1/products/{id}/aspects` | 维度下钻：特性列表 + 评论 | VIEWER+ |
| POST | `/api/v1/imports` | 上传 CSV，创建导入任务 | ANALYST |
| POST | `/api/v1/mining/tasks` | 提交挖掘任务 | ANALYST |
| GET | `/api/v1/alerts` | 预警列表（分页、级别、状态、品类） | VIEWER+ |
| POST | `/api/v1/alerts/{id}/dispose` | 处置（status + note） | ADMIN |
| GET | `/api/v1/reports/export` | 导出 CSV/PDF | VIEWER+ |

补充管理接口：`/api/v1/admin/products`、`/api/v1/admin/rules`、`/api/v1/admin/aspect-dict`、`/api/v1/admin/tasks/{id}`。

### 7.3 导入流程

```
上传 CSV → 创建 import_batch(status=0) → 逐行校验（必填、类型、外键）
  ├─ 通过 → 清洗 → 写 review → success++
  └─ 失败 → 写错误行明细（行号 + 原因）→ failed++
每 1000 行提交一次事务，更新 batch 计数
整批结束 → batch.status = 1；失败率 > 50% 则整批回滚并置 status=2
```

- 支持"撤销批次"：按 `batch_id` 删除 review 及其级联数据（demo 用）。
- 导入速度目标 ≥ 2000 条/秒：用 `rewriteBatchedStatements=true` + 批量 500 条。

### 7.4 指数批算（伪代码）

```java
for (Long pid : productIds) {
    List<ReviewWithAnalysis> rs = repo.findAnalyzed(pid, start, end);   // 只取已分析的
    QiResult r = algoClient.index(pid, start, end, "v1-2026-10");       // 也可本地实现，见 §8
    qiRepo.upsert(pid, r);                                              // 唯一键冲突则覆盖（同版本）
}
```

- 分批 500 个商品，异步执行，进度写 `mining_task.progress`。
- 同 `(product, period, param_version)` 重算覆盖；换 `param_version` 则新增一行（保留历史）。

### 7.5 预警扫描（伪代码）

```java
for (QualityIndex qi : latest) {
    for (Rule r : rules) {
        Level lv = r.evaluate(qi);              // null 表示未命中
        if (lv != null && !suppressed(qi.getProductId(), r.code(), 7)) {
            alertRepo.save(new Alert(qi, r.code(), lv, r.metric(), r.message()));
        }
    }
}
```

- 抑制：同商品同规则 7 天内已有预警则不重复生成（`suppressed` 查 `alert` 表）。
- 升级：抑制期内若新级别更高，更新原预警的 `level`，不新增。

---

## 8. 质量指数规范

### 8.1 计算（四步，必须逐字实现）

```python
def dimension_score(reviews, dim, now):
    num = den = 0.0
    for r in reviews:                       # r 已带 aspect 命中与 fake_prob
        c = math.exp(-LN2 / 90 * (now - r.time).days)   # 时间衰减，半衰期 90 天
        w = c * (1 - r.fake_prob)                       # 刷评降权
        num += w * r.strength
        den += w
    s = num / den if den > 0 else 0.0                   # 加权情感均值 ∈ [-1,1]
    S = (s + 1) / 2                                     # 映射到 [0,1]
    n = len(reviews)
    return (n * S + 30 * prior(dim)) / (n + 30)         # 贝叶斯收缩，m=30

QI = 100 * sum(w[dim] * score[dim] for dim in DIMENSIONS)
```

- 权重：`quality 0.28, appearance 0.12, logistics 0.15, service 0.13, value 0.17, package 0.15`。
- 先验 `prior(dim)`：优先取该品类近 90 天中位数；无数据时取 0.55。
- 等级：`≥85 优(5)`、`75–85 良(4)`、`65–75 中(3)`、`55–65 差(2)`、`<55 极差(1)`。
- **可复算**：同一份输入 + 同一 `param_version`，两次结果必须逐位相同。实现上禁止用当前时间做任何影响结果的运算（`now` 取 `period_end`）。

### 8.2 参数版本

`param_version = "v1-2026-10"` 对应固化的一份参数快照（权重、λ、m、词表版本、模型版本）。改任一参数必须升版本号，旧版本结果保留可查。

---

## 9. 预警规则

| 规则 | 含义 | 红色 | 橙色 | 黄色 |
|---|---|---|---|---|
| R1 | 综合指数过低 | QI < 60 | 60 ≤ QI < 70 | — |
| R2 | 单维度得分过低 | < 0.45 | 0.45–0.55 | — |
| R3 | 近 7 天差评率较前 28 天上升 | > 100% | 50%–100% | 30%–50% |
| R4 | 刷评占比过高 | > 50% | 30%–50% | 20%–30% |
| R5 | 某方面情感较上一周期下滑 | > 0.5 | 0.3–0.5 | 0.2–0.3 |

- 阈值存 `rule_config.threshold_json`，界面可改，改动写审计日志。
- 同一商品同时命中多条规则时，取最高级别生成一条预警，`message` 中列出全部命中规则。
- 抑制窗口 7 天，按 `(product_id, rule_code)` 去重。

---

## 10. 前端

| 路由 | 页面 | 要点 |
|---|---|---|
| `/login` | 登录 | 账密 + 验证码（可用固定验证码，演示足够） |
| `/dashboard` | 质量驾驶舱 | 4 指标卡 + 30 天趋势（ECharts line）+ 维度排行（bar）+ 最新预警列表 |
| `/product/{id}` | 商品画像 | 指数卡 + 六维雷达（radar）+ 12 个月趋势 + 情感分布堆叠条 + 差评关键词 + 代表评论（按方面分组） |
| `/mining` | 评论挖掘 | 任务列表 + 新建任务（选范围、参数）+ 进度轮询 |
| `/alerts` | 预警与处置 | 列表（级别色标）+ 详情抽屉 + 处置操作 |
| `/admin` | 系统管理 | 商品/品类/供应商、规则阈值、词表、用户 |

实现要点：

- `src/api/http.js` 统一 axios 实例：baseURL `/api`、JWT 注入、401 跳登录、`code != 0` 弹 message。
- 雷达图维度名必须与后端 `dim_scores` 的 `code` 对应，中文名从字典取。
- 列表分页 20 条，筛选条件同步到 URL query（便于演示时直接给链接）。
- 首屏 ≤ 3 秒：画像接口一次返回聚合结果，不要前端发 5 个请求。

---

## 11. 八周执行计划

每周末都有一个**可演示的增量**，不允许"最后一周才看到东西"。

| 周 | 目标 | 产出 | 验收命令 / 判定 |
|---|---|---|---|
| W1 | 数据与技术骨架落地 | schema.sql、seed 数据、algo 与 backend 骨架、Docker Compose | `python scripts/check_data.py` 输出商品≥1000、评论≥2万、时间跨度≥18 个月 |
| W2 | 情感基线达标 | 数据清洗、TF-IDF+SVM 训练、评估脚本 | `python scripts/evaluate.py` → `sentiment.macro_f1 ≥ 0.85` |
| W3 | 方面 + 刷评 + 弱标注 | 词表 v1、匹配器、5 条规则、300 条人工标注 | 方面 P≥0.85 / R≥0.65；刷评样本命中有 detail |
| W4 | 指数与接口 | 指数批算、`/v1/index`、`/api/v1/*` 主要接口 | `pytest tests/test_qi.py` 全绿；`bench_qi.py` ≤ 5 min/10 万条 |
| W5 | 驾驶舱与画像 | 两个页面 + 聚合接口 + 演示数据 | 浏览器打开驾驶舱，指标非零，画像可下钻 |
| W6 | 预警与处置 | 规则引擎、抑制、处置留痕、联调 | 构造差评突增，7 天内不重复生成 |
| W7 | 测试、性能、部署、录屏 | 测试报告、压测数据、docker compose 一键起、三条主线录屏 | AC-01…AC-11 全通过；P95 达标 |
| W8 | 文档与答辩 | 设计/测试文档、PPT、彩排 | 答辩能解释公式参数与指标口径 |

分工（4 人）：A 算法/数据（W2–W4 主力）、B 后端（W4–W6 主力）、C 前端（W5–W6 主力）、D 项目负责（统筹 + 数据 + 文档）。**每人每周约 12 小时。**

---

## 12. 演示脚本（答辩就照这个走）

**主线一：从数据到指数（5 分钟）**

1. 登录 → 进入 `/admin` 商品管理，展示 1000 个商品与品类树。
2. `/mining` 新建挖掘任务（范围：某品类，周期：上月）→ 进度条走到 100%。
3. 打开 `/product/2031`（无线蓝牙耳机）→ 指数 68.5、等级"中"、雷达图六维、近 6 个月趋势。
4. 点雷达图"商品质量"维度 → 下钻到"续航"特性的评论列表，看到"标称 8 小时，实际 4 小时就没电"。

**主线二：从异常到处置（3 分钟）**

5. 回到 `/dashboard`，指出"待处置预警 9 条"与红色预警。
6. 进入 `/alerts`，筛选"红色"，打开 P-2031 的预警详情：命中 R1（QI<70）与 R5（续航下滑 0.42）。
7. 处置：填写"已通知供应商复测电池容量"，确认 → 状态变为"已确认"，记录处置人与时间。
8. 再次扫描 → 该商品 7 天内不再生成同类预警（演示抑制窗口）。

**主线三：结果可信（3 分钟）**

9. 打开导出，下载该商品月度质量报告（CSV/PDF），指出报告里带 `param_version` 与样本量。
10. 用附录 A 的手算过程核对指数：0.28×0.237 + 0.12×0.86 + … = 68.5。
11. 展示 `report/metrics.json`：情感 macro-F1 0.86、方面 P 0.87 / R 0.68、300 条人工标注的评测口径。

---

## 13. 验收自查表

| 编号 | 操作 | 期望 |
|---|---|---|
| AC-01 | 导入含 10% 错误行的 CSV | 正确行入库；错误行给出行号与原因；批次可撤销 |
| AC-02 | 对含重复与手机号的样本执行治理 | `dup_flag=1`，`mask_flag=1`，原文不含手机号 |
| AC-03 | 新增商品并关联品类/供应商 | 保存成功；删品类时被外键拒绝 |
| AC-04 | 对 1000 条样本执行挖掘 | 有情感、方面、刷评三列结果；指标见 metrics.json |
| AC-05 | 构造时间聚集 + 评分背离样本 | `fake_prob ≥ 0.5` 且 `fake_reason` 可读 |
| AC-06 | 对某商品算月度指数 | 与附录 A 手算一致，误差 ≤ 0.1 |
| AC-07 | 改权重后重算 | 新 `param_version` 生效，旧结果仍可查 |
| AC-08 | 构造差评突增 | 生成对应级别预警；7 天内不重复 |
| AC-09 | 处置一条预警 | 状态、处置人、时间、意见留痕 |
| AC-10 | 打开驾驶舱并下钻 | 卡片、趋势、雷达、评论均加载，下钻 ≤ 1 秒 |
| AC-11 | 组合条件检索 + 导出 | 结果正确；导出行数与页面一致 |

---

## 14. 坑与降级路径

| 坑 | 现象 | 对策 |
|---|---|---|
| `yf_amazon` 的 `comment` 大量为空 | 只有 title（"赞!""喜欢""嗯"），情感模型学到噪声 | 过滤正文 <5 字；title 非空但 comment 空的，用 title 兜底并标记 `text_source=1` |
| 评分极度偏 5 星 | 所有商品指数 85+，拉不开差距 | 指数靠"差评文本量 + 评分文本背离"拉开，不只信均分；正文情感与评分加权 |
| 时间平移后"最近 7 天"为空 | R2 突增规则永不触发 | 平移后强制校验 `max(review_time)` 落在 7 天内；不足则从原数据里挑最新的一段补 |
| 词表过度匹配 | 精确率虚高、召回虚低，误命中"好" | 短词加限定；每维度先只放 6—8 个高置信同义词 |
| 方面召回上不去 | R < 0.65 | 先扩同义词（人工读 100 条差评），仍不行才考虑弱监督模型 |
| 指数在样本少时抖动 | 新商品指数忽高忽低 | 收缩 m=30 已缓解；前端对 n<30 标注"参考值" |
| 批算超时 | 10 万条 > 5 分钟 | 只算新增评论（增量）；`review_aspect` 建 `(dimension_code)` 索引；分批提交 |
| 预警刷屏 | 一次生成上百条 | 抑制窗口 + 同商品合并取最高级 |
| 前端首屏慢 | 画像 5 秒+ | 后端一次聚合；ECharts 大数据降采样（`sampling: 'lttb'`） |
| 环境差异 | 别人机器跑不起来 | 全部走 Docker；`requirements.txt` 锁版本；`.env.example` 齐全 |

**降级顺序**（时间不够时按此顺序砍）：LLM 摘要 → 报表导出 PDF（只留 CSV）→ 关键词提取 → 方面情感强度（只留极性）。**不能砍**：指数计算、预警生成、驾驶舱、画像。

---

## 15. 给下一个 DSH 的施工顺序

1. 先读 §0、§1、§8，把"完成定义"和"指数公式"吃透——这两处错了，后面全白做。
2. 按 §3 建仓库骨架，先跑通 §4 的三条启动命令（哪怕接口全是 mock）。
3. 写 `db/schema.sql` + `scripts/build_dataset.py`，**先有数据再写算法**；下载 `yf_amazon` 是第一步（百度网盘，约 1 GB）。
4. 算法服务按 §6 的契约实现，用 `curl` 逐个验证，再接业务服务。
5. 业务服务先做 `/api/v1/products/{id}/profile`（它串起所有模块），再做驾驶舱。
6. 前端按 §10 的页面顺序做，每完成一页就联调一次。
7. 每周对照 §11 的验收命令打勾，不要积累到最后。
8. 交付前跑一遍 §13 自查表，任何一项不过都不算完成。

**不要做的事**：不要提前做微服务拆分；不要为了指标好看篡改测试集；不要在预警里放模型黑盒判断；不要把 LLM 生成的数字写进报告。
