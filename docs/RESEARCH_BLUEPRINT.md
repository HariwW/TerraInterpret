# I2RSI V2 研究蓝图

> Research Blueprint: Trustworthy Human-in-the-loop Multisensor Spatiotemporal GeoFM Adaptation under Label Scarcity and Geographic Shift

- 状态：研究设计稿（不是实验结论）
- 版本：2026-08-31
- 适用对象：研究计划、可复现实验与系统迭代

## 1. 一页定位

I2RSI V2 不再把“能上传图片并输出彩色结果”当作研究贡献。它的定位是一个**可复现的 GeoAI 研究工作台**，围绕一个可证伪的问题组织数据、模型、实验、人工修订与证据：

> 在标注稀缺、区域迁移和传感器缺失同时存在时，传感器感知的参数高效 GeoFM 适配、校准不确定性和主动人机协同，能否比任务专用模型或朴素微调，以更少标注获得更稳定、可审计的遥感解译结果？

项目方法主题：

- 中文：**面向低标注与跨区域部署的可信多传感器时空 GeoFM 人机协同解译**
- English: **Trustworthy Human-in-the-loop Multisensor Spatiotemporal GeoFM Adaptation under Label Scarcity and Geographic Shift**

平台只是实验仪器。项目可主张的价值必须来自预注册问题、严格对照、外部区域测试、误差与限制分析以及可复现实验包；界面现代化本身不是论文创新。

## 2. 为什么值得研究

近期工作给出的信号并不是“基础模型已经解决遥感解译”，而是研究机会仍集中在评测、公平适配和真实部署：

| 一手证据 | 对本项目的含义 |
| --- | --- |
| [GEO-Bench](https://proceedings.neurips.cc/paper_files/paper/2023/hash/a0644215d9cff6646fa334dfa5d29c5a-Abstract-Datasets_and_Benchmarks.html) 用多任务协议评估地球观测表征 | 不能用单一数据集或单一最优数值证明“通用” |
| [PANGAEA](https://arxiv.org/abs/2412.04204) 指出 GeoFM 在不同任务、分辨率和标注预算下并不稳定胜过监督基线 | U-Net/ViT 等强监督基线必须保留；“GeoFM 必然更好”是待检验假设 |
| [Prithvi-EO-2.0](https://arxiv.org/abs/2412.02732) 显式建模多时相、位置和日期，[CROMA](https://proceedings.neurips.cc/paper_files/paper/2023/hash/11822e84689e631615199db3b75cd0e4-Abstract.html) 联合雷达与光学 | 时空元数据和传感器组合应作为实验因子，而不是被 RGB 截图抹掉 |
| [TerraMind](https://openaccess.thecvf.com/content/ICCV2025/papers/Jakubik_TerraMind_Large-Scale_Generative_Multimodality_for_Earth_Observation_ICCV_2025_paper.pdf) 探索多模态生成式 EO 基础模型 | “缺失模态”应通过受控遮蔽和独立消融检验，不能靠生成结果的视觉观感下结论 |
| [M3LEO](https://proceedings.neurips.cc/paper_files/paper/2024/file/bd194b579f60879e04ca9ce8a4ea5da1-Paper-Datasets_and_Benchmarks_Track.pdf) 显示跨区域表征分布偏移，[AllClear](https://proceedings.neurips.cc/paper_files/paper/2024/file/60095e1d7ebb292dbba93c4d8f7b2463-Paper-Datasets_and_Benchmarks_Track.pdf) 提供大规模多传感器时序场景 | 随机切片划分不足以代表跨区域部署；云、季节和模态缺失必须进入压力测试 |
| [Active Learning Meets Foundation Models](https://openaccess.thecvf.com/content/ICCV2025/papers/Burges_Active_Learning_Meets_Foundation_Models_Fast_Remote_Sensing_Data_Annotation_ICCV_2025_paper.pdf) 将不确定性与多样性用于遥感主动标注 | “减少人工成本”必须用随机采样对照、真实操作时间和学习曲线验证 |
| [Conformal Semantic Image Segmentation](https://openaccess.thecvf.com/content/CVPR2024W/SAIAD/papers/Mossina_Conformal_Semantic_Image_Segmentation_Post-hoc_Quantification_of_Predictive_Uncertainty_CVPRW_2024_paper.pdf) 给出分割预测的后处理不确定性方案 | softmax 不是可信概率；校准集、覆盖率和适用假设必须显式记录 |
| [EarthDial](https://openaccess.thecvf.com/content/CVPR2025/html/Soni_EarthDial_Turning_Multi-sensory_Earth_Observations_to_Interactive_Dialogues_CVPR_2025_paper.html) 与 [GEOBench-VLM](https://openaccess.thecvf.com/content/ICCV2025/html/Danish_GEOBench-VLM_Benchmarking_Vision-Language_Models_for_Geospatial_Tasks_ICCV_2025_paper.html) 展示多传感器对话潜力与明显评测缺口 | 自然语言解释只作可选接口；没有定位证据和任务评测时，不宣称“理解”或“推理” |

## 3. 研究范围

### 3.1 主任务与辅助任务

1. **主任务：城市变化解译。** 双时相/多时相建筑与土地覆盖变化分割，重点检验跨城市、跨季节和不同观测条件。
2. **辅助任务：多传感器地表覆盖分割。** 使用 Sentinel-1、Sentinel-2 与 DEM 检验融合、缺失模态和低标注迁移；用于判断方法是否只对变化检测有效。
3. **应用示范：香港城市变化。** 以香港公开 Sentinel 数据和可合法使用的正射影像/地理数据建立外部案例。香港地政总署提供的正射影像具有明确坐标和分辨率说明，但购买、开放下载和再分发条件不同，必须逐资产记录许可；参见[地政总署开放地理空间数据](https://www.landsd.gov.hk/en/spatial-data/open-data.html)和[数码正射影像说明](https://www.landsd.gov.hk/en/survey-mapping/mapping/aerial-photo-photogrammetric-products/digital-orthophoto.html)。

旧平台的目标检测、道路提取和四分类可以继续作为适配器/交互演示，但在完成同等严格的独立评测前，不进入论文主结论。

### 3.2 明确不做

- 不从零预训练十亿参数模型；优先使用可公开复现的模型和参数高效适配。
- 不把 2022 年旧权重、网页写死的 OAcc/mIoU/F1/mAP 或单次输入的置信度当作 V2 精度。
- 不把随机切片测试称为跨区域泛化。
- 不把像素坐标 GeoJSON 称为地理坐标结果。
- 不把视觉效果、演示流畅度或语言描述当作算法正确性证据。
- 不在没有同协议复现的情况下使用 “SOTA”“显著优于” 或 “实时”。

## 4. 研究问题与可证伪假设

### RQ1：低标注适配

在固定的 1%、5%、10%、25%、100% 嵌套标注预算下，GeoFM 的线性探测、LoRA/Adapter 与全量微调，相比同容量任务专用模型和从头训练模型，何时具有更好的标签效率和外域表现？

- **H1a：** 在 1%–25% 标注预算下，最佳预注册 PEFT 方案的外域 macro-F1/mIoU 高于强监督基线。
- **H1b：** 这种优势不必在 100% 标注预算或所有传感器上成立；若置信区间跨零，则报告“证据不足”，而不是挑选最佳 seed。
- **反证条件：** 在至少两个外部区域上，PEFT 的主要指标均未提高，或提高来自参数量、分辨率、预训练数据泄漏/重叠或额外调参预算。

### RQ2：缺失模态与区域迁移

传感器感知适配和训练期 modality dropout 能否提高 S1/S2/DEM 任一模态不可用时的最坏情形性能，并降低跨区域退化？

- **H2：** 与朴素 early fusion 相比，传感器感知适配在完整模态精度不显著下降的前提下，提高缺失模态组合的 worst-group mIoU，并降低 `full → missing` 性能降幅。
- **反证条件：** 收益只出现在随机划分、单一区域或模型见过的缺失模式；完整模态下降超过预注册容忍值。

### RQ3：多时序变化理解

显式时间/位置编码和多时相聚合是否比双图拼接更能区分真实城市变化与季节、阴影、云和配准误差？

- **H3：** 时空编码在空间留出的变化 F1、boundary F1 和 hard-negative false-positive rate 上优于双图拼接。
- **反证条件：** 结果只在同城随机划分上改善，或配准/云掩膜预处理已经解释全部增益。

### RQ4：可信输出与选择性预测

后处理校准、OOD 检测和 conformal prediction 能否使“不确定”具有可检验含义，并把人工核验集中到高风险区域？

- **H4：** 独立校准集上的温度缩放/适当 conformal 方案降低 ECE/Brier/AURC，并在预注册风险水平上达到经验覆盖率目标。
- **反证条件：** 校准仅对域内有效，外域覆盖率失效，或以大到不可用的预测集/高拒识率换取覆盖率。
- **限制：** 遥感像素存在强空间相关性；任何有限样本保证都必须说明交换性单位是像素、tile 还是空间 block，不能直接把通用 conformal 结论外推到任意地理分布。

### RQ5：人机协同效率

“不确定性 + 表征多样性”的主动采样，是否比随机采样和仅不确定性采样，以更少专家成本达到相同外域性能？

- **H5：** 在相同累计标注分钟数或点击数下，组合采样获得更高的学习曲线面积（AULC），或更早达到预注册目标 F1。
- **反证条件：** 只按样本数计算但实际操作更慢、专家间一致性差、冷启动阶段劣于随机且总体未追回，或用户研究样本量不足。

## 5. 实验对象与数据治理

### 5.1 数据层级

| 层级 | 候选数据 | 用途 | 使用前门槛 |
| --- | --- | --- | --- |
| A：通用协议 | [GEO-Bench](https://proceedings.neurips.cc/paper_files/paper/2023/hash/a0644215d9cff6646fa334dfa5d29c5a-Abstract-Datasets_and_Benchmarks.html)、[PANGAEA](https://github.com/VMarsocci/pangaea-bench) | 复用标准任务与适配协议 | 固定代码/数据版本，核对预训练数据重叠 |
| B：多传感器压力测试 | [M3LEO](https://proceedings.neurips.cc/paper_files/paper/2024/file/bd194b579f60879e04ca9ce8a4ea5da1-Paper-Datasets_and_Benchmarks_Track.pdf)、[AllClear](https://github.com/Zhou-Hangyu/allclear) 或 PANGAEA 中兼容任务 | S1/S2/辅助数据、跨区与缺失模态 | 先做可行性采样；不要为了“大数据”偏离任务 |
| C：城市变化基准 | [LEVIR-CD](https://justchenhao.github.io/LEVIR/)、[WHU Building Dataset](https://gpcv.whu.edu.cn/data/)、[SpaceNet 7](https://openaccess.thecvf.com/content/CVPR2021/html/Van_Etten_The_Multi-Temporal_Urban_Development_SpaceNet_Dataset_CVPR_2021_paper.html) | 双时相/多时相变化与外部复现 | 遵循官方划分或发布新空间划分；记录影像许可 |
| D：香港外部案例 | [Copernicus Data Space](https://dataspace.copernicus.eu/)、香港地政总署/CSDI 合法资产 | 从公开 benchmark 到本地城市案例的外推 | 数据许可、摄影日期、CRS、云量、标注协议和再分发规则齐全 |

任何数据在进入训练前都必须生成 dataset card，至少记录：来源 URL、版本/检索日期、许可、传感器、波段顺序、空间分辨率、CRS、时间范围、区域范围、云/NoData、标注者与质检、切片规则、哈希、已知偏差、允许用途和禁止用途。该要求与 [Datasheets for Datasets](https://www.microsoft.com/en-us/research/publication/datasheets-for-datasets/) 的透明度原则一致。

### 5.2 划分与防泄漏协议

1. **空间 block 是主划分。** 同一原始场景、相邻 tile、同一建筑或重叠 footprint 不得跨 train/val/test。
2. **跨区域测试是主结论。** 至少使用 leave-one-region/city-out；随机划分只作为“乐观对照”，不放在摘要主表。
3. **时间泄漏受控。** 同一区域相邻日期不得同时进入训练和测试；所有归一化统计仅从训练集计算。
4. **校准集独立。** 温度缩放、阈值、conformal quantile 和拒识阈值不能在测试集选择。
5. **标签预算嵌套。** 1% ⊂ 5% ⊂ 10% ⊂ 25% ⊂ 100%，按空间 block 与类别分层抽取；每个 seed 使用可追踪清单。
6. **香港案例冻结。** 先冻结方法和主要超参数，再揭示测试标注；若用香港标签适配，则另设未触碰的香港测试区。
7. **预训练重叠审计。** 无法排除 GeoFM 见过测试地理区域时，结论表述为“下游适配表现”，不表述为严格 unseen geography 泛化。

### 5.3 标注与伦理

- 两名标注者独立标注一个预注册子集；报告 IoU/F1 或适当的一致性指标，冲突由第三方仲裁并保留事件日志。
- 香港案例不标注个人、车辆身份或敏感设施细节；公开结果采用必要的空间聚合与许可审查。
- 不重新分发许可不允许公开的原始影像；公开切片索引、处理代码、派生统计时也需遵守来源条款。
- 记录主动学习给标注者展示的信息，避免模型建议无声污染“独立真值”。最终测试标注原则上盲于模型输出。

## 6. 模型与公平对照

### 6.1 预注册模型组

| 组 | 最低要求 | 作用 |
| --- | --- | --- |
| B0 透明 CPU 基线 | 当前 V2 的确定性差异/规则方法 | 验证端到端产物与 provenance；**不作为深度模型精度基线** |
| B1 强监督基线 | U-Net/SegFormer 或同等公开实现；变化任务增加一个经典 Siamese/Transformer 基线 | 防止把预训练收益与架构/训练预算收益混淆 |
| B2 GeoFM | 至少一个与数据传感器匹配的开放权重，如 Prithvi-EO-2.0、CROMA 或 TerraMind | 检验预训练表征；不得把不支持的波段静默映射成 RGB |
| A1 线性探测 | 冻结 encoder，只训练标准化 head | 最低成本迁移基线 |
| A2 PEFT | LoRA/Adapter；预注册层、rank、可训练参数量 | 核心低标注方案 |
| A3 全量微调 | 同 decoder、输入、增强和训练预算 | 精度上限及成本对照 |

公平性要求：同一比较必须固定输入信息、训练/调参预算、增强、decoder 容量、早停规则和数据划分；同时报告总参数、可训练参数、训练 GPU-hours、峰值显存和推理吞吐。不能用更高分辨率或更多未标注目标域数据后仍称“同等条件”。

### 6.2 候选方法，而非既成贡献

工作名称可暂定为 **GeoAdapt Loop**，由四个可独立消融的部件构成：

1. 传感器/波段/分辨率/日期/位置 token 或 adapter；
2. 共享时空 encoder + 轻量任务 head；
3. 训练期 modality dropout 与显式 missingness mask；
4. 校准不确定性驱动的 uncertainty-diversity 主动采样和可追踪人工修订。

只有当每个部件在预注册外域实验中产生稳定增益，才可在论文中称为方法贡献；否则应作为负结果或工程组件报告。

### 6.1 当前实现边界（V2.1）

已实现可运行的闭环骨架：候选区域 uncertainty-diversity 排序、人工确认/驳回/几何修订、append-only `AnnotationEvent`、递增数据版本、SHA-256 标签谱系，以及以人工复核结果拟合 logistic proxy calibrator 并反哺下一轮采样。该实现用于验证闭环、审计和实验契约。

尚未实现 GeoFM 权重适配、LoRA/Adapter、传感器 token、训练期 modality dropout 和外域实验。当前 calibrator 只校准透明 CPU 基线的 proxy score，不属于 GeoFM 参数高效微调，也不能作为 H1--H4 的实验结论。

## 7. 实验矩阵

### 7.1 核心因子

- 标签预算：`1 / 5 / 10 / 25 / 100%`
- 输入模态：`S1`、`S2`、`DEM`、`S1+S2`、`S2+DEM`、`S1+S2+DEM`
- 缺失模式：训练期完整、随机 modality dropout、部署期单模态/双模态缺失
- 适配策略：`linear probe / LoRA(or Adapter) / full fine-tune`
- 划分：`random diagnostic / spatial holdout / cross-region holdout`
- 时间建模：`pair concatenate / temporal pooling / explicit temporal-position encoding`
- 校准：`raw / temperature scaling / conformal variant`
- 主动采样：`random / uncertainty / diversity / uncertainty+diversity`
- 重复：至少 `3 seeds`；最终主表优先 `5 seeds`（算力不足时明确披露）

完整笛卡尔积成本过高，采用两阶段实验：先在固定 10% 预算和 3 个 seed 上筛选主效应，再只对预注册候选做全预算确认。筛选集和最终测试集必须分离。

### 7.2 可执行实验表

| ID | 问题 | 对照与变量 | 主指标 | 通过门槛 |
| --- | --- | --- | --- | --- |
| E0 | 数据/评测链路是否可信 | 官方划分 vs 空间重划分；重叠、CRS、时相和类别审计 | 泄漏数、无效 tile、类分布、可复现哈希 | 测试重叠为 0；dataset card 完整 |
| E1 | GeoFM 是否标签高效 | B1/B2 × 5 个预算 × 3+ seeds | 外域 macro-F1/mIoU、AULC | H1 的效应量与 95% CI 按预注册规则判定 |
| E2 | PEFT 是否值得 | linear/LoRA/full FT；固定 encoder/head/预算 | 指标、可训练参数、GPU-hours、峰值显存 | 给出 Pareto 前沿，不只报最高分 |
| E3 | 缺失模态是否鲁棒 | early fusion vs missingness-aware；6 种输入与部署缺失 | worst-group mIoU、相对退化、完整模态 mIoU | 同时报告鲁棒性收益与完整模态代价 |
| E4 | 时间编码是否识别真变化 | 拼接/池化/显式时间编码；云影、季节、错位 hard negatives | change F1/IoU、boundary F1、FP rate | 外域与 hard-negative 均改善才支持 H3 |
| E5 | 不确定性能否兑现 | raw/temp/conformal；域内与域外 | ECE、Brier/NLL、AURC、coverage/set size | 覆盖率和实用性同时达标；单列外域失效 |
| E6 | 主动学习是否省人工 | 4 种采样；固定初始集、预算和 retrain 频率 | AULC、达到目标 F1 的分钟/点击、专家一致性 | 相对 random 的 CI 与实际时间均改善 |
| E7 | 香港案例能否外推 | 冻结模型、有限适配、未触碰空间测试区 | 任务指标、校准、区域/场景分层误差 | 不与公开 benchmark 混合排名；完整失败案例 |
| E8 | 系统能否复现 | 冷启动重复运行、不同机器/容器、失败恢复 | 哈希一致性、状态一致性、p50/p95、资源 | 同版本确定性链路产物一致；非确定项有容差 |

## 8. 指标、统计与报告规则

### 8.1 任务指标

- 二值变化：change-class precision、recall、F1、IoU；类别不平衡时以 change F1/IoU 为主，OA 只作补充。
- 多类分割：per-class IoU/F1、macro-F1、mIoU；同时报告 support，不以背景类掩盖失败。
- 边界/对象：boundary F1；建筑实例任务可增加 object-level precision/recall。SpaceNet 7 的跟踪结论只在实现其官方协议时使用 SCOT。
- 主动学习：以累计**真实标注时间/点击数**为横轴的学习曲线和 AULC；样本数仅作次要指标。

### 8.2 可信与 OOD 指标

- 校准：ECE + reliability diagram，并至少配套一个 proper scoring rule（Brier 或 NLL）。ECE 分箱规则预先固定。
- 选择性预测：risk-coverage curve 与 AURC；报告拒识后保留覆盖率。
- Conformal：经验 coverage、平均 prediction-set size/uncertain-pixel share，分区域/类别报告。
- OOD：AUROC、AUPR、FPR@95TPR，并分别报告语义新颖、传感器变化和区域变化；“OOD 分数”不等同任务错误概率。

### 8.3 统计规则

1. 每个训练设置至少 3 个独立 seed，公开每个 seed，而非只公开均值。
2. 95% 置信区间以**空间 block/场景**为重采样单位，避免把相关像素当作独立样本造成伪精确。
3. 同时报告绝对差、相对差和效应量；若做大量比较，预注册主比较并对探索性比较做 FDR 控制。
4. 超参数由 validation 选择，test 只在最终冻结后运行；所有失败/中止 run 也进入日志。
5. 对人机实验报告参与者背景、顺序随机化、任务熟悉效应和配对分析；样本量不足时只称 pilot。
6. 复现实验记录软件镜像、git commit、数据/权重哈希、硬件、seed、训练时间和成本。研究报告按 [NeurIPS Paper Checklist](https://blog.neurips.cc/2021/03/26/introducing-the-neurips-2021-paper-checklist/) 自检。

## 9. Claim boundary：什么可以说，什么不能说

| 展示/结果层级 | 允许表述 | 必要证据 | 禁止越界 |
| --- | --- | --- | --- |
| 单次无真值推理 | 预测覆盖面积、候选数、运行时间、模型 score/uncertainty proxy | run manifest、输入/模型/参数哈希 | “本图准确率 95%”“置信度就是正确概率” |
| 有真值数据集评测 | “在数据集 D、划分 S、版本 V 上，指标为 …” | 冻结测试集、评测代码、逐 seed 结果 | 把数据集结果写成每次推理的固有属性 |
| 跨区域泛化 | “训练地区 A/B，未调参测试地区 C” | 空间隔离、预训练重叠审计、外域 CI | 随机 tile 划分后称 geographic generalization |
| 缺失模态鲁棒 | “在预注册缺失模式下 worst-group 改善” | 完整/缺失模态配对消融 | 仅展示一个成功缺失样例 |
| 校准/统计保证 | “在指定校准/测试分布及假设下经验 coverage …” | 独立校准集、假设、coverage 与 set size | 对任意新区域承诺无条件概率保证 |
| 人工效率 | “在 N 名参与者和任务 T 的 pilot 中节省 …” | 随机/配对用户研究、时间/点击日志 | 仅凭界面流程宣称减少 50% 成本 |
| SOTA | “同数据、同划分、同指标且复现/官方可比” | 可复核表格、代码和置信区间 | 与论文不同输入/划分直接比较 |
| VLM/解释 | “生成了与定位证据关联的辅助描述” | grounding、事实核验与失败率 | “模型理解了城市变化原因”或把生成文字当证据 |

所有 UI 指标都必须显示作用域标签：`RUN STATISTIC`、`EVALUATION (GT)`、`REFERENCE (external)` 或 `PROXY`。默认不显示外部论文数值；如显示，必须包含来源、数据集、划分、输入和版本。

## 10. 三阶段路线与验收门

### Phase I：可信基线与研究底座（0–8 周）

目标：从“可运行演示”变为“不会伪造结论的实验仪器”。

- 完成 STAC 1.1 资产目录、COG/GeoJSON 产物、地理 CRS/transform 保真与 OGC 风格异步 job contract。
- 建立 dataset/model/run/evaluation card，冻结 E0/E1 的数据版本与空间划分。
- 实现透明 CPU 基线、至少一个强监督基线、可重跑评测 CLI 和研究工作台。
- 将 inference 与 evaluation 彻底分开；移除硬编码精度。
- 输出：公开 demo、架构文档、数据审计、baseline report、复现实验脚本和失败案例集。

**Gate 1：** 从空环境可一条命令重建至少一个数据子集、训练/推理、评测和报告；任一数值可追溯到 run、代码、数据与权重哈希。

### Phase II：核心方法与系统消融（2–6 个月）

目标：回答 RQ1–RQ4，而不是追求大而全。

- 接入至少两个传感器匹配的 GeoFM，完成 linear/PEFT/full-FT 公平对照。
- 运行标签预算、空间迁移、模态缺失、时空编码和不确定性实验。
- 开发 GeoAdapt Loop 的最小部件并做逐项消融；负结果保留。
- 输出：完整主表、逐 seed 结果、误差分类、资源 Pareto、技术报告/预印本初稿。

**Gate 2：** 至少一个核心假设在两个外部区域上获得方向一致的证据，且收益不能由泄漏、额外输入或训练预算解释；否则收缩/修改研究命题。

### Phase III：人机协同、香港案例与投稿包（6–12 个月）

目标：把方法证据、真实使用和开放复现连成闭环。

- 预注册 E6 用户 pilot，记录点击、时间、修订前后指标和标注者一致性。
- 冻结方法后完成香港外部案例；展示不确定性、人工修订和数据 provenance。
- 完成外部复现（另一机器/协作者）、容器镜像、匿名代码、模型卡、数据卡、演示视频和论文附录。
- 论文叙事保持“一项方法贡献 + 一项可信评测贡献 + 一个可复现系统载体”。

**Gate 3：** 技术报告中的每条定量陈述都能链接到版本化 artifact；论文摘要中的每条 claim 都能在主实验矩阵中找到对应对照和反证条件。

## 11. 项目交付物

一个可信的研究项目应提供完整证据链，而不是只包含界面截图：

1. 方法说明：问题、缺口、方法假设、初步结果/负结果和下一步；
2. 6–8 页 technical report/preprint：协议、主表、消融、统计、误差与限制；
3. 可公开运行的 repo：固定环境、测试、benchmark CLI、配置和结果 schema；
4. 3–5 分钟双语 demo：香港 AOI → 数据来源 → 运行 → 不确定性 → 人工修订 → 有真值评测 → manifest；
5. contribution map：明确研究、工程、数据与文档的贡献边界；
6. dataset cards、model cards、实验索引和 failure gallery；
7. 复现徽章式自检：新环境运行记录、硬件/成本和已知非确定性。

这些材料用于提升研究可信度；核心标准是问题是否重要、假设是否清晰、证据是否严谨、贡献是否真实可归因。

## 12. 风险与止损

| 风险 | 早期信号 | 止损方案 |
| --- | --- | --- |
| 算力不足 | full FT 无法完成多 seed | 先用 tiny/base 模型；以 linear/PEFT 和 Pareto 为主；缩小数据但不动测试协议 |
| GeoFM 不胜基线 | E1 多域均无收益 | 将贡献转向“何时失效”的系统研究；不挑单一成功数据集 |
| 多任务失焦 | 每个任务只有浅结果 | 主任务锁定城市变化，辅助任务只验证可迁移性 |
| 香港真值不足 | 标注量/许可无法支持统计结论 | 明确降级为外部 case study；主要结论留在公开 benchmark |
| 主动学习收益不稳定 | 冷启动劣于 random | 加入 diversity/cold-start 对照，报告 crossover；无收益则作为负结果 |
| conformal 外域失效 | coverage 在新区域下降 | 分区域校准、风险监测与 abstention；限制保证范围，不修改测试后阈值 |
| 平台吞噬研究时间 | UI 工作超过算法/实验 | 只实现支撑证据链的工作台功能，冻结装饰性需求 |
| 数据/权重许可不清 | 不能公开输入或 checkpoint | 使用可公开替代数据；只发布脚本/索引；在 model/dataset card 标明限制 |

## 13. 每个主实验的预注册最小模板

```yaml
experiment_id: E1-label-efficiency-v1
research_question: RQ1
primary_hypothesis: H1a
code_commit: "<git-sha>"
datasets:
  - id: "<dataset@version>"
    split_manifest_sha256: "<sha256>"
    license: "<spdx-or-text>"
models:
  baseline: "<model-card-id>"
  candidate: "<model-card-id>"
label_budgets: [1, 5, 10, 25, 100]
seeds: [17, 29, 43]
primary_metric: external_macro_f1
secondary_metrics: [miou, ece, aurc, trainable_params, gpu_hours]
selection_rule: "validation macro-F1; test opened once after freeze"
ci_unit: spatial_block
success_rule: "candidate-baseline 95% CI > 0 on >=2 external regions"
failure_rule: "otherwise unsupported; report all effects"
hardware: "<device, memory, software image>"
```

架构如何承载这些约束，见 [ARCHITECTURE.md](./ARCHITECTURE.md)。
