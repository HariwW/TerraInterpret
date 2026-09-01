# TerraInterpret

**Intelligent Interpretation of Remote Sensing Images · GeoAI Research Workbench**

TerraInterpret（I2RSI V2）是一个面向遥感智能解译研究的可复现 GeoAI 工作台。它在保留变化检测、地表覆盖、目标候选和道路提取四类任务的基础上，重建了作业隔离、模型卡、运行溯源、不确定性表达、GeoJSON 导出和科研声明边界。

项目将 2022 年的竞赛原型升级为可运行、可测试、可追溯的遥感解译实验平台，用于端到端流程验证、误差分析和方法迭代。

> 当前内置引擎是透明、确定性的 CPU 演示基线，用于验证端到端链路，不是训练后的深度模型，也不代表论文精度。mIoU、F1、mAP 等指标只允许出现在绑定真值、数据版本和评测协议的独立 evaluation 中。

## V2 已实现

- 一屏式 GeoAI 工作台：研究场景、双时相对比、结果图层、运行观测和 provenance。
- 四类可运行 CPU 基线：变化检测、地表覆盖、目标候选、道路提取。
- FastAPI `/api/v1`：健康检查、模型注册、示例场景、作业创建与查询。
- 每次运行使用独立 UUID 目录，不再共享全局模型和固定结果文件。
- 输入与产物 SHA-256、模型版本、参数、引擎版本和声明边界自动写入 manifest。
- 结果产物包括原图、叠加图、掩膜、不确定性代理和像素坐标 GeoJSON。
- GeoAdapt Loop：不确定性-多样性主动采样、人工确认/驳回/修订、append-only 标注事件、版本化标签谱系和反馈校准。
- PNG/JPEG 解码预检、上传大小与像素数限制、双时相尺寸检查和安全响应头。
- Docker、GitHub Actions、pytest 合约测试和 Ruff 静态检查。

## 快速启动

要求 Python 3.11–3.13。首次运行：

```bash
git clone https://github.com/HariwW/TerraInterpret.git
cd TerraInterpret
make setup
make dev
```

打开：

- 工作台：<http://127.0.0.1:8080/>
- OpenAPI：<http://127.0.0.1:8080/docs>

也可以直接指定端口：

```bash
.venv/bin/i2rsi --port 8765
```

页面会读取仓库中的 `data_demo.zip` 并自动运行第一个双时相示例，不需要下载旧 Paddle 权重。

## 开发与验证

```bash
make test
make lint
```

当前测试覆盖 API、四类示例任务、上传校验、作业隔离、产物哈希、GeoJSON 媒体类型、provenance、主动采样、不可变标注事件、版本链和反馈校准，以及禁止在无真值推理中伪造精度指标。

Docker 运行：

```bash
docker build -t i2rsi:v2 .
docker run --rm -p 8080:8080 i2rsi:v2
```

## API 示例

```bash
curl http://127.0.0.1:8080/api/v1/health
curl http://127.0.0.1:8080/api/v1/models
curl -X POST "http://127.0.0.1:8080/api/v1/demo-runs/urban-change?threshold=0.62"
curl http://127.0.0.1:8080/api/v1/geoadapt/state
curl "http://127.0.0.1:8080/api/v1/geoadapt/reviews?limit=10"
```

## GeoAdapt Loop

V2.1 提供一个无需 GPU 即可验证的闭环最小实现：

1. 每个成功 run 的候选几何进入 review queue；系统联合不确定性与特征空间多样性计算采样优先级。
2. 人工可以确认、驳回或提交修订几何；每次操作写入新的 append-only `AnnotationEvent`，不覆盖历史。
3. 事件按任务生成递增的数据版本，并通过 parent event、SHA-256 和来源 run 保留完整标签谱系。
4. 当同一模型至少积累 4 个且同时包含正/负的复核样本后，可拟合确定性的 logistic proxy calibrator。
5. 新 calibrator 重新计算待复核候选的不确定性并影响下一轮主动采样，形成可测试的反馈闭环。

工作台的“确认候选 / 驳回候选 / 生成适配轮次”按钮可以完成上述流程。对应 API：

```bash
curl -X POST http://127.0.0.1:8080/api/v1/geoadapt/reviews/<candidate-id>/annotations \
  -H 'Content-Type: application/json' \
  -d '{"decision":"accept","reviewer":"local-user"}'

curl -X POST http://127.0.0.1:8080/api/v1/geoadapt/adaptations \
  -H 'Content-Type: application/json' \
  -d '{"task":"object_detection","model_id":"geodetect-lite-v2","min_samples":4}'
```

当前适配后端是 `proxy-logistic-calibration-v1`，只校准透明基线产生的候选分数。它不是 GeoFM/LoRA 权重训练。`AdaptationBackend` 已作为接入契约保留；真实 PEFT 需要另行配置传感器匹配的 GeoFM 权重、训练数据、标注划分和 GPU 环境。

每个运行的目录结构如下：

```text
artifacts/v2/jobs/<run-id>/
  inputs/
  outputs/
    original.png
    overlay.png
    mask.png
    uncertainty.png
    features.geojson
  manifest.json
artifacts/v2/geoadapt/
  review_candidates.json
  annotation_events/<event-id>.json
  adaptation_rounds/<round-id>.json
```

`artifacts/` 是本地运行数据，默认不提交到 Git。

## 方法方向

建议的核心研究问题是：

> 在低标注、地理分布偏移和传感器缺失条件下，传感器感知的参数高效 GeoFM 适配，能否以更低标注成本获得更稳定、可校准和可审计的遥感解译结果？

详细内容：

- [研究蓝图](docs/RESEARCH_BLUEPRINT.md)：可证伪假设、数据治理、实验矩阵、指标和阶段性交付物。
- [系统架构](docs/ARCHITECTURE.md)：V2/legacy 边界、目标领域模型、STAC/COG 路线和发布门槛。

方法实现应遵循以下顺序：真实监督基线 → 空间隔离评测 → GeoFM/PEFT → 缺失模态鲁棒性 → 校准与人机协同。当前页面中的透明规则基线只用于产品和可复现性 smoke test。

## 项目结构

```text
i2rsi/
  app.py              # FastAPI 与 HTTP 契约
  service.py          # 作业隔离、状态和 manifest
  engine.py           # 可替换的透明 CPU baseline
  geoadapt.py         # 主动采样、版本化人工修订与反馈校准闭环
  models.py           # 领域 DTO
  registry.py         # 模型卡和演示场景
  static/             # 研究工作台前端
tests/                # API、隔离、安全与科研声明测试
docs/                 # 架构和研究设计
functions/            # 旧 PaddleRS 算法，仅作 legacy 参照
webpage/              # 旧版页面，仅作 legacy 参照
process.py            # 旧 Flask 应用，不应作为 V2 启动入口
```

## Legacy 说明

仓库仍保留原始 Flask/PaddleRS 实现，用于历史追溯与后续黄金输出迁移，但不建议直接运行：

- 旧模型权重目录没有随仓库提交。
- 原环境绑定 Python 3.8、Paddle 2.3 和 Windows 批处理。
- 旧服务使用进程全局状态和固定输出文件，不支持并发隔离。
- 旧模型上传、任意 URL 下载和目录删除接口不应暴露到公网。
- 旧页面中的 OAcc、mIoU、F1、mAP 和 loss 是静态展示值，不属于 V2 研究证据。

迁移原则是将旧模型放入受限的独立 worker/容器，并通过 V2 engine contract 接入，而不是让新 API 直接导入 `process.py`。

## 当前边界

- V2 seed 只接收普通 RGB PNG/JPEG；输出 GeoJSON 使用像素坐标，不是地理坐标。
- 当前本地作业索引和后台任务适合单机研究演示，不具备多租户和持久队列语义。
- GeoAdapt Loop 当前完成的是 proxy calibration 闭环；GeoFM 的 LoRA/Adapter 训练和多传感器 modality dropout 尚未实现。
- 公开部署前仍需认证、授权、租户隔离、配额、任务超时和对象存储权限控制。
- GeoTIFF/COG、STAC、多传感器 GeoFM、训练与真值评测属于下一阶段研究实现。
