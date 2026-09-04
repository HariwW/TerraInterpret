# TerraInterpret

**Intelligent Interpretation of Remote Sensing Images · GeoAI Research Workbench**

TerraInterpret 是一个面向遥感智能解译研究的可复现 GeoAI 工作台。它覆盖变化检测、地表覆盖、旋转框目标检测和道路提取四类任务，并提供作业隔离、模型卡、运行溯源、不确定性表达、GeoJSON 导出和科研声明边界。

项目将 2022 年的竞赛原型升级为可运行、可测试、可追溯的遥感解译实验平台，用于端到端流程验证、误差分析和方法迭代。

> 平台同时提供透明 CPU 基线与公开预训练模型。模型卡中的公开数据集指标只说明权重出处；用户数据上的 mIoU、F1、mAP 等指标只允许出现在绑定真值、数据版本和评测协议的独立 evaluation 中。

## V2 已实现

- 一屏式 GeoAI 工作台：研究场景、双时相对比、结果图层、运行观测和 provenance。
- 五个确定性 CPU 基线，以及 LoveDA DeepLabV3+ R18/R50/R101、DOTA YOLO11n/YOLO26n/YOLO26s-OBB 和 Open-CD Changer R18 模型适配器，共 14 张模型卡。
- 环境感知的默认模型：变化检测优先 Changer 或 GeoChange Robust，地表覆盖/道路默认 R50，旋转框默认 YOLO26n；运行时不可用时自动降级到可运行模型，手动指定模型时绝不静默替换。
- 数据目录：校验并持久化本地影像，固定数据版本、资产 SHA-256、角色和像素尺寸，可从指定版本发起作业。
- 作业中心：创建、筛选和回看运行，按状态、任务与模型查询独立 manifest 和产物。
- 流程编排中心：固定数据版本后执行多模型计划、记录逐步状态，在同一真值上评测并生成模型排名。
- 模型注册表：集中展示任务、输入约束、版本、优势、局限、推理参数和指标声明边界。
- 真实标注评测：对变化检测和道路提取的二值掩膜计算 IoU、F1、precision、recall、accuracy 与 specificity，并保存真值/预测哈希和混淆矩阵。
- FastAPI `/api/v1`：健康检查、数据、模型、示例场景、作业、评测与 GeoAdapt 查询。
- 每次运行使用独立 UUID 目录，不再共享全局模型和固定结果文件。
- 输入与产物 SHA-256、模型版本、参数、引擎版本和声明边界自动写入 manifest。
- 结果产物包括原图、叠加图、掩膜、不确定性代理和像素坐标 GeoJSON。
- GeoAdapt Loop：不确定性-多样性主动采样、人工确认/驳回/修订、append-only 标注事件、版本化标签谱系和反馈校准。
- 可选 GeoAgent Copilot：提供本地持久化多轮记忆、历史会话、归档和自然语言工具调用，并通过显式授权启动任务。
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

页面会读取仓库中的 `data_demo.zip`，为变化检测、地表覆盖、旋转框目标检测和道路提取各构建一个示例作业。已有成功示例会直接复用，不会因刷新页面重复计算，也不需要下载旧 Paddle 权重。

安装真实模型的隔离运行环境（约 1–2 GB，推荐 Python 3.12）：

```bash
make models-setup
make dev
```

模型依赖安装在 `.venv-models`，不会改变 Web API 的 `.venv`。YOLO 与 LoveDA 权重在首次运行时下载到 `artifacts/v2/model-cache`。默认档会自动选择当前环境可运行的平衡模型，模型注册表用“当前默认”标识；R101 和 YOLO26s 作为更重的手动高精度选项。Apple Silicon 可运行 YOLO 和 LoveDA；Open-CD Changer 依赖 MMCV 编译算子，当前在模型注册表中明确显示为不可用，建议在 Linux + CUDA worker 上启用。

## 开发与验证

```bash
make test
make lint
```

当前测试覆盖 API、数据版本与数据作业链、四类示例任务、上传校验、作业筛选与隔离、产物哈希、真实标注评测、GeoJSON 媒体类型、provenance、主动采样、不可变标注事件、版本链和反馈校准，以及禁止在无真值推理中伪造精度指标。

Docker 运行：

```bash
docker build -t i2rsi:v2 .
docker run --rm -p 8080:8080 i2rsi:v2
```

包含 GeoAgent OpenAI provider 的镜像：

```bash
docker build --build-arg I2RSI_EXTRAS=agent-openai -t terrainterpret:agent .
docker run --rm -p 8080:8080 -e OPENAI_API_KEY terrainterpret:agent
```

## API 示例

```bash
curl http://127.0.0.1:8080/api/v1/health
curl http://127.0.0.1:8080/api/v1/models
curl http://127.0.0.1:8080/api/v1/datasets
curl "http://127.0.0.1:8080/api/v1/jobs?status=succeeded&task=road_extraction"
curl http://127.0.0.1:8080/api/v1/evaluations
curl http://127.0.0.1:8080/api/v1/workflows
curl -X POST "http://127.0.0.1:8080/api/v1/demo-runs/urban-change?threshold=0.62"

# 确保四类任务各有一个可复用的成功示例
curl -X POST http://127.0.0.1:8080/api/v1/demo-runs/bootstrap
curl http://127.0.0.1:8080/api/v1/geoadapt/state
curl "http://127.0.0.1:8080/api/v1/geoadapt/reviews?limit=10"
```

## GeoAgent 融合

V2.2 将 [opengeos/GeoAgent](https://github.com/opengeos/GeoAgent) 作为可选的自然语言编排层。TerraInterpret 仍负责数据目录、模型卡、解译作业、评测产物和 GeoAdapt 状态；GeoAgent 只调用经过筛选的项目级工具，不获得任意 Python、文件系统或删除权限。当前只读工具可查询数据版本、筛选运行、检查模型卡与评测报告，并仅在任务、指标套件和真值哈希一致时给出直接指标比较。

使用 OpenAI provider：

```bash
.venv/bin/python -m pip install -e ".[agent-openai]"
export OPENAI_API_KEY="..."
export I2RSI_AGENT_PROVIDER="openai"
make dev
```

使用本地 Ollama：

```bash
.venv/bin/python -m pip install -e ".[agent-ollama]"
export I2RSI_AGENT_PROVIDER="ollama"
export OLLAMA_MODEL="qwen3.5:4b"
make dev
```

可选变量：`I2RSI_AGENT_MODEL` 固定模型，`I2RSI_AGENT_ENABLED=0` 完全关闭 Agent。启动后点击顶部的 **GeoAgent** 按钮，或访问：

```bash
curl http://127.0.0.1:8080/api/v1/agent/status
curl http://127.0.0.1:8080/api/v1/agent/conversations
curl -X POST http://127.0.0.1:8080/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"总结最近一次解译运行"}'
```

首次成功回复会自动创建会话并返回 `conversation_id`。后续请求携带相同 ID 即可继续上下文：

```bash
curl -X POST http://127.0.0.1:8080/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"conversation_id":"<conversation-id>","message":"继续分析它的复核候选"}'
```

对话以原子 JSON 记录保存在 `artifacts/v2/agent-conversations`。提示上下文只注入最近 16 条消息且最多 12,000 字符，完整历史仍可通过会话 API 和页面侧栏查看。归档不会删除记录。

使用 DeepSeek 官方 OpenAI 兼容接口：

```bash
.venv/bin/python -m pip install -e ".[agent-openai]"
export DEEPSEEK_API_KEY="..."
export I2RSI_AGENT_PROVIDER="deepseek"
export I2RSI_AGENT_MODEL="deepseek-v4-flash"
make dev
```

DeepSeek 的默认地址是 `https://api.deepseek.com`；如需代理，可使用 `DEEPSEEK_BASE_URL` 覆盖。密钥只从进程环境读取，不写入配置、工作流或 provenance。

默认仅开放读取能力。`run_demo_interpretation` 和 `run_dataset_workflow` 被标记为需要确认；只有请求显式携带 `"allow_actions": true` 时才可能执行。精度声明边界仍由 TerraInterpret 系统提示和工具返回共同约束。

## 文件夹数据集

数据目录支持在浏览器中直接选择一个包含 PNG/JPEG 影像的文件夹。平台会过滤非影像文件、保留每张影像的相对路径，逐文件校验格式、大小和像素上限，并根据“相对路径 + 文件 SHA-256”生成与浏览器枚举顺序无关的内容版本。默认限制为单文件 32 MB、每个目录 1000 张影像、总计 512 MB，可分别通过 `I2RSI_MAX_UPLOAD_MB`、`I2RSI_MAX_DATASET_FILES` 和 `I2RSI_MAX_DATASET_MB` 调整。

也可以直接调用 API；重复路径、绝对路径和包含 `..` 的路径会被拒绝：

```bash
curl -X POST http://127.0.0.1:8080/api/v1/datasets/folder \
  -F 'name=城区地表覆盖切片' \
  -F 'task_hint=land_cover' \
  -F 'files=@tiles/train/tile-001.png;filename=tiles/train/tile-001.png' \
  -F 'files=@tiles/val/tile-002.jpg;filename=tiles/val/tile-002.jpg'
```

文件夹数据集会显式记录为 `layout=folder`。当前单景作业与单样本多模型编排不会擅自选取其中第一张影像运行；批量作业能力需要使用独立的 batch workflow，避免产生数据语义错误的实验记录。

## 流程编排

编排以版本化数据集为输入，以独立解译作业为执行单元：

1. 验证数据版本、任务提示、双时相约束和模型运行状态。
2. 对每个选定模型分别创建 job，保留模型、输入和产物哈希。
3. 单个模型失败不会覆盖其他结果，工作流记录部分成功状态和错误。
4. 变化检测或道路提取完成后进入 `awaiting_ground_truth`，不在无真值时计算精度。
5. 上传同一真值后，为每个成功作业生成独立 evaluation，并按 F1/IoU 汇总可比较排名。

也可以直接调用 API：

```bash
curl -X POST http://127.0.0.1:8080/api/v1/workflows \
  -H 'Content-Type: application/json' \
  -d '{"name":"道路模型比较","dataset_id":"<dataset-id>","task":"road_extraction","model_ids":["deeplabv3plus-r18-loveda-road","roadgraph-lite-v2"],"model_parameters":{"deeplabv3plus-r18-loveda-road":{"threshold":0.45},"roadgraph-lite-v2":{"threshold":0.62}}}'

curl -X POST http://127.0.0.1:8080/api/v1/workflows/<workflow-id>/execute
```

空的 `model_ids` 表示选择该任务下所有已就绪模型。二值任务完成推理后，可在编排中心统一上传真值，或调用 `/api/v1/workflows/<workflow-id>/evaluations`。

推理参数由模型卡声明，不再使用所有任务共享的固定阈值。YOLO 的默认检测置信度为 `0.25`；LoveDA 使用最低像素置信度并把低于门槛的像素标记为不确定；透明变化/道路基线使用各自的筛选强度。固定配置模型不会显示或记录无效阈值，多模型工作流通过 `model_parameters` 为每个模型独立保存参数。

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
artifacts/v2/catalog/<dataset-id>/
  assets/
    <folder-relative-path>  # 文件夹数据集
  dataset.json
artifacts/v2/evaluations/<evaluation-id>/
  ground_truth.png
  report.json
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
  catalog.py          # 本地数据目录、内容版本与资产校验
  evaluation.py       # 绑定真实标注的二值分割评测
  workflow.py         # 持久化多模型计划、状态机、评测与排名
  service.py          # 作业隔离、状态和 manifest
  engine.py           # 透明 CPU baseline
  model_runtime.py    # 按 model_id 路由的隔离模型适配器
  model_worker.py     # PyTorch/OpenMMLab/Ultralytics worker
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
- 当前评测仅覆盖二值变化检测与道路提取；多类地表覆盖和目标检测需要独立标签协议与 metric suite。
- GeoTIFF/COG、STAC、多传感器 GeoFM 与真实训练后端属于下一阶段研究实现。
