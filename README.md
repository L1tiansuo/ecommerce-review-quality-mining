# 质衡 · 电商商品评论数据挖掘与产品质量管理系统

完整可修改源码，含Vue仪表盘、Spring Boot业务服务、FastAPI算法、MySQL部署、带注释代码、训练模型、脱敏演示数据与测试脚本。解压后保留本目录结构。

## 先运行

推荐Docker方式（安装Docker Desktop并启动后，在项目根目录执行）：

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

浏览器打开 **http://localhost:8080**。首次镜像构建需要联网；首次空库会自动建表并导入125,720条评论、1,120件商品及13个月的预计算结果，需要等待后台初始化。可用`docker compose logs -f backend`查看状态。后续启动使用数据库卷，不重复导入。

### 国内网络下的构建准备（已在本机验证）

直连 Docker Hub、Maven Central、PyPI 会慢到不可用，本仓库已按下面三处做了本地化，克隆到新机器时可照做：

1. **镜像加速**：`%USERPROFILE%\.docker\daemon.json` 增加
   ```json
   { "registry-mirrors": ["https://docker.1ms.run", "https://docker.m.daocloud.io"] }
   ```
   实测 `docker.1ms.run` 拉 node:20-alpine（约 130 MB）耗时 46 秒；`docker.m.daocloud.io` 会在大层上卡死，故排在第二位。
2. **Maven 走阿里云**：`backend/docker/settings.xml` 把 central 镜像到 `https://maven.aliyun.com/repository/public`，`backend/Dockerfile` 里 `COPY docker/settings.xml /root/.m2/settings.xml`。直连 Maven Central 时单文件 3–20 KB/s，换镜像后 100–200 KB/s，构建从「一小时也算不完」降到 97 秒。
3. **pip 走阿里云**：`algo/Dockerfile` 的 `pip install` 加 `--index-url https://mirrors.aliyun.com/pypi/simple`。直连 PyPI 约 26–46 KB/s，换镜像后 225 KB/s，依赖安装 396 秒。

四容器启动后 `docker compose ps` 应全部 healthy/running，MySQL 版实测：1,120 商品、125,720 评论、平均 QI 56.94、预警 1,118 条，与 H2 版一致；接口 p50 为 dashboard 398 ms、商品列表 17 ms、画像 29 ms、预警列表 14 ms。

| 账号 | 角色 | 初始口令 |
|---|---|---|
| admin | 管理员：配置、处置、全部操作 | QrDemo2026! |
| analyst | 分析师：导入、挖掘、查询 | QrDemo2026! |
| viewer | 只读：查询、导出 | QrDemo2026! |

演示验证码 **2026**。可在首次部署前修改`.env`中的ADMIN_PASSWORD。已初始化数据库不会因环境变量变动重置口令。JWT会话30分钟。

无Docker的Windows开发模式：安装Java17+、Node18+、Python3.10+后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

该入口使用H2本地文件数据库，首次安装Python依赖需要联网，随后打开 **http://127.0.0.1:8088**。预构建业务jar在`release/backend.jar`，前端构建结果在`web/dist`。停止使用`stop-local.ps1`。H2模式服务于本机开发，正式验收请使用Compose中的MySQL。当前测试环境对数据库文件锁有限制，端到端验证采用H2内存模式，文件持久化和MySQL部署应在常规宿主环境复核。

## 怎么操作

1. **质量驾驶舱**：查看在监商品、平均QI、本周预警、待处置数量；选择品类，查看月度趋势与最新预警。
2. **商品质量分析**：按名称或品类检索，打开画像；查看六维雷达、历史版本、情感分布；点击维度按钮下钻评论，组合筛选情感与刷评风险，打开分析明细查看命中原因。
3. **评论挖掘**：先在系统管理建商品，再上传CSV。批次展示成功、失败与重复标记；错误明细有行号和原因；撤销后受影响指数清除，需要重算。创建单商品、品类或全量任务，进度自动刷新，支持取消与失败重试。
4. **预警与处置**：执行扫描，按级别、状态、品类筛选；管理员填写意见并确认、忽略或标记处理；处理人和时间留痕。
5. **系统管理**：维护主数据、用户、规则阈值、词表和权重版本，查看审计与服务健康。开发者配置使用可编辑JSON，保存前校验。
6. 使用页面导出按钮下载CSV；预警页可导出PDF台账。评论导出沿用当前组合条件。

建议演示商品：900000001（指数下降）、900000002（差评突增）、900000003（时间聚集）、900000004（五星与差评背离）、900000005（模板评论）。五者均为明确标注的模拟教学商品。

## 导入格式

UTF-8 CSV，单批最多50,000行/50MB：

```csv
product_id,content_raw,rating,review_time,source_type
900000001,包装破损且质量很差,1,2026-11-09 12:00:00,3
```

时间不得晚于当前时间；正文5至2000字符；评分1至5或留空；来源1公开数据、2平台导出、3模拟。真实用户编号不入库。手机号、身份证、邮箱入库前脱敏。

## 源码与继续开发

| 目录 | 内容 |
|---|---|
| backend | Java业务源码、配置、Maven构建、Dockerfile |
| algo | Python算法、词表、模型、FastAPI接口 |
| web | Vue界面源码、样式、API封装、图表、构建结果 |
| db | 数据库表结构 |
| scripts | 数据准备、预计算、训练、评测、导入、压测、端到端验证 |
| tests | 指数算例、算法与接口自动化测试 |
| data/seed | 脱敏评论子集、商品、场景清单、分析结果、指数 |
| data/eval | 留出测试集及待人工标注样本 |
| docs | 设计、冲突取舍、实测结果、界面预览、原始需求副本 |
| release | 已编译后端jar，便于无Maven环境启动 |

原始840MB数据集不重复打包。重新处理自己的原始数据：

```powershell
pip install -r requirements-dev.txt
python scripts/build_dataset.py --raw "C:\你的路径\yf_amazon"
python scripts/check_dataset.py
python scripts/precompute.py
python -m pytest tests -q
```

源码修改后：`cd backend; mvn package`，将jar复制到`release/backend.jar`；`cd web; npm ci; npm run build`；算法修改后重启算法服务。Docker方式执行`docker compose up --build -d`。需要重载seed时请先备份数据，使用全新的数据库卷，避免覆盖已有处置记录。

详细说明见`docs/设计与开发指南.md`、`docs/需求冲突与验收映射.md`和`docs/测试报告.md`。

## 验收状态必须区分

功能自动化、构建与本机响应测量的结果见随包JSON报告。情感二分类与三分类是不同指标：本次二分类宏F1约0.943；测试集无中性金标，三分类验收仍不成立。方面识别的精确率、召回率及方面情感准确率需300条人工标注，尚不能标为达标。Docker/MySQL四服务启动、规定2核4GB环境、50用户并发、万评论单商品性能均需目标环境复核。

本版没有BERT微调、人工金标、自动归档、应用内定时调度、断点自动恢复、演示录屏。提供核心业务链路、可运行代码及对应扩展入口。不能把本包视为全部非功能需求均已完成验收的成品证明。

## 数据与依赖

主数据由用户提供的yf_amazon加工，仅用于本地教学研究，原始语料不公开再分发。时间已归一化，供应商与剧本商品为模拟数据。训练数据来自 [ChineseNlpCorpus](https://github.com/SophonPlus/ChineseNlpCorpus)，原始训练语料不附包，附训练脚本与模型。依赖遵守各自许可证，依赖版本见pom.xml、package-lock.json与requirements文件。
