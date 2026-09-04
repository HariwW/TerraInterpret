from __future__ import annotations

from .models import DemoScenario, InferenceParameterSpec, ModelCard, TaskType


def _threshold_parameter(
    label: str,
    description: str,
    default: float,
) -> InferenceParameterSpec:
    return InferenceParameterSpec(
        key="threshold",
        label=label,
        description=description,
        default=default,
        minimum=0.05,
        maximum=0.95,
        step=0.01,
    )


MODEL_CARDS = [
    ModelCard(
        id="geochange-lite-v2",
        name="GeoChange Lite",
        task=TaskType.CHANGE_DETECTION,
        family="deterministic research baseline",
        version="2.0.0",
        stage="demo baseline",
        description="可复现的双时相差异基线，输出变化掩膜、置信度代理和像素坐标矢量。",
        strengths=["无需权重即可复现", "输出完整 provenance", "适合作为深度模型对照组"],
        limitations=["未进行影像配准", "对季节、光照与云影变化敏感", "置信度不是概率校准值"],
        expected_inputs=["两幅已配准 RGB PNG/JPEG", "相同空间范围与近似分辨率"],
        reference_metrics={},
        metric_scope="当前页面仅报告本次输入的描述性统计，不冒充测试集精度。",
        inference_parameters=[
            _threshold_parameter("变化筛选强度", "越高越保守，输出的变化区域通常越少。", 0.62)
        ],
    ),
    ModelCard(
        id="geochange-robust-v3",
        name="GeoChange Robust",
        task=TaskType.CHANGE_DETECTION,
        family="registration-aware deterministic baseline",
        version="3.0.0",
        stage="enhanced baseline",
        description=(
            "先估计小范围平移，再进行逐通道辐射归一化，并融合颜色、亮度和边缘差异的双时相变化检测基线。"
        ),
        strengths=["无需外部权重", "抑制轻微错位与整体亮度漂移", "CPU 可复现且输出完整 provenance"],
        limitations=[
            "只能修正小范围平移，不能替代正射校正",
            "未学习建筑语义",
            "复杂季节变化仍需人工复核",
        ],
        expected_inputs=["两幅已配准 RGB PNG/JPEG", "相同空间范围、尺寸与近似分辨率"],
        reference_metrics={},
        metric_scope="增强项属于确定性图像算法，不声明公开测试集精度；请绑定本地真值生成 F1/IoU。",
        backend="builtin-robust-change",
        runtime="builtin",
        recommended_device="CPU",
        inference_parameters=[
            _threshold_parameter(
                "变化筛选强度", "越高越保守；默认值兼顾小目标保留和伪变化抑制。", 0.58
            )
        ],
    ),
    ModelCard(
        id="landcover-lite-v2",
        name="LandCover Lite",
        task=TaskType.LAND_COVER,
        family="spectral heuristic baseline",
        version="2.0.0",
        stage="demo baseline",
        description="基于可解释颜色与纹理规则的地表覆盖分区，用作 GeoFM 微调前的基线。",
        strengths=["类别规则透明", "CPU 友好", "提供逐像素不确定性代理"],
        limitations=["RGB 不能替代多光谱数据", "跨区域阈值需要重新校准"],
        expected_inputs=["RGB PNG/JPEG"],
        reference_metrics={},
        metric_scope="未在公开测试集上评估，不展示 mIoU 等精度声明。",
    ),
    ModelCard(
        id="geodetect-lite-v2",
        name="GeoDetect Lite",
        task=TaskType.OBJECT_DETECTION,
        family="saliency proposal baseline",
        version="2.0.0",
        stage="demo baseline",
        description="从局部纹理显著性生成候选框，验证检测 API、矢量导出与交互链路。",
        strengths=["候选框可解释", "保留原始宽高比", "GeoJSON 输出"],
        limitations=["不是训练后的目标检测器", "类别标签仅为 candidate"],
        expected_inputs=["RGB PNG/JPEG"],
        reference_metrics={},
        metric_scope="候选框分数是显著性归一化值，不是目标类别概率。",
    ),
    ModelCard(
        id="roadgraph-lite-v2",
        name="RoadGraph Lite",
        task=TaskType.ROAD_EXTRACTION,
        family="appearance baseline",
        version="2.0.0",
        stage="demo baseline",
        description="道路外观先验基线，输出连通区域代理、覆盖率和不确定性图。",
        strengths=["输出结构化掩膜", "参数可追踪", "适合接入人机协同修订"],
        limitations=["林荫与阴影道路容易漏检", "尚未执行拓扑重建"],
        expected_inputs=["RGB PNG/JPEG"],
        reference_metrics={},
        metric_scope="覆盖率是本次影像统计，不是 IoU 或 F1。",
        inference_parameters=[
            _threshold_parameter("道路筛选强度", "越高越保守，输出的道路候选通常越少。", 0.62)
        ],
    ),
    ModelCard(
        id="changer-r18-levircd",
        name="Open-CD Changer R18",
        task=TaskType.CHANGE_DETECTION,
        family="Changer / ResNet-18",
        version="Open-CD 1.1",
        stage="public pretrained",
        description="在 LEVIR-CD 上训练的建筑变化检测模型，输出变化掩膜与像素坐标矢量。",
        strengths=["真实双时相深度模型", "面向高分辨率建筑变化", "官方公开配置与权重"],
        limitations=[
            "要求严格配准的双时相 RGB 影像",
            "Apple Silicon 缺少兼容的 MMCV 算子构建",
            "跨地区使用前应做域外评测",
        ],
        expected_inputs=["两幅已配准 RGB PNG/JPEG", "相同尺寸与空间范围"],
        reference_metrics={
            "dataset": "LEVIR-CD test",
            "precision": 92.86,
            "recall": 90.78,
            "f1": 91.81,
            "iou": 84.86,
        },
        metric_scope=(
            "指标来自 Open-CD 官方模型表的 LEVIR-CD 测试结果，"
            "仅作权重出处说明，不代表用户数据精度。"
        ),
        backend="opencd",
        runtime="isolated-pytorch-worker",
        weight_source="Open-CD Changer R18 LEVIR-CD official checkpoint",
        license="Apache-2.0 (Open-CD code; dataset/weights terms also apply)",
        recommended_device="Linux + CUDA",
        inference_parameters=[
            _threshold_parameter(
                "变化像素最低置信度",
                "仅保留预测为变化且模型置信度达到门槛的像素。",
                0.50,
            )
        ],
    ),
    ModelCard(
        id="deeplabv3plus-r18-loveda",
        name="DeepLabV3+ R18 · LoveDA",
        task=TaskType.LAND_COVER,
        family="DeepLabV3+ / ResNet-18",
        version="MMSegmentation 1.2",
        stage="public pretrained",
        description=(
            "LoveDA 七类遥感语义分割模型，覆盖背景、建筑、道路、水体、裸地、森林和农业用地。"
        ),
        strengths=["公开权重与可复现配置", "七类逐像素输出", "CPU 可运行"],
        limitations=["仅使用 RGB", "类别体系固定为 LoveDA", "跨传感器与跨城市需独立评测"],
        expected_inputs=["RGB PNG/JPEG", "城市场景或乡村场景遥感影像"],
        reference_metrics={"dataset": "LoveDA validation", "mIoU": 50.28},
        metric_scope="mIoU 来自 MMSegmentation 官方 LoveDA 模型表；平台运行页只展示本次预测统计。",
        backend="mmseg-loveda",
        runtime="isolated-pytorch-worker",
        weight_source="MMSegmentation DeepLabV3+ R18 LoveDA official checkpoint",
        license="Apache-2.0 (MMSegmentation code; dataset/weights terms also apply)",
        recommended_device="CPU (portable) / CUDA",
        inference_parameters=[
            _threshold_parameter(
                "最低像素置信度",
                "低于门槛的像素标记为不确定，不再强制归入某一地类。",
                0.45,
            )
        ],
    ),
    ModelCard(
        id="deeplabv3plus-r50-loveda",
        name="DeepLabV3+ R50 · LoveDA",
        task=TaskType.LAND_COVER,
        family="DeepLabV3+ / ResNet-50",
        version="MMSegmentation 1.2",
        stage="public pretrained",
        description="LoveDA 七类遥感语义分割模型；R50 在精度、显存占用和推理速度之间提供平衡。",
        strengths=["更强的 ResNet-50 表征", "官方公开配置与权重", "七类逐像素置信度输出"],
        limitations=["CPU 推理明显慢于 R18", "仅使用 RGB", "跨传感器与跨城市需独立评测"],
        expected_inputs=["RGB PNG/JPEG", "城市场景或乡村场景遥感影像"],
        reference_metrics={"dataset": "LoveDA validation", "mIoU": 50.99},
        metric_scope="mIoU 来自 MMSegmentation 官方 LoveDA 模型表；不代表用户数据精度。",
        backend="mmseg-loveda-r50",
        runtime="isolated-pytorch-worker",
        weight_source="MMSegmentation DeepLabV3+ R50 LoveDA official checkpoint",
        license="Apache-2.0 (MMSegmentation code; dataset/weights terms also apply)",
        recommended_device="CUDA / CPU",
        inference_parameters=[
            _threshold_parameter("最低像素置信度", "低于门槛的像素标记为不确定。", 0.45)
        ],
    ),
    ModelCard(
        id="deeplabv3plus-r101-loveda",
        name="DeepLabV3+ R101 · LoveDA",
        task=TaskType.LAND_COVER,
        family="DeepLabV3+ / ResNet-101",
        version="MMSegmentation 1.2",
        stage="public pretrained",
        description="LoveDA 七类语义分割的高容量版本，适合有 CUDA 资源时做高精度对照。",
        strengths=[
            "当前 LoveDA DeepLabV3+ 三档中官方 mIoU 最高",
            "更深层语义表征",
            "公开权重可复现",
        ],
        limitations=["计算与内存开销最大", "CPU 不适合作为交互默认", "跨域性能必须重新评测"],
        expected_inputs=["RGB PNG/JPEG", "LoveDA 相近俯视尺度"],
        reference_metrics={"dataset": "LoveDA validation", "mIoU": 51.47},
        metric_scope="mIoU 来自 MMSegmentation 官方 LoveDA 模型表；不代表用户数据精度。",
        backend="mmseg-loveda-r101",
        runtime="isolated-pytorch-worker",
        weight_source="MMSegmentation DeepLabV3+ R101 LoveDA official checkpoint",
        license="Apache-2.0 (MMSegmentation code; dataset/weights terms also apply)",
        recommended_device="CUDA",
        inference_parameters=[
            _threshold_parameter("最低像素置信度", "低于门槛的像素标记为不确定。", 0.45)
        ],
    ),
    ModelCard(
        id="deeplabv3plus-r18-loveda-road",
        name="DeepLabV3+ R18 · LoveDA Road",
        task=TaskType.ROAD_EXTRACTION,
        family="DeepLabV3+ / ResNet-18",
        version="MMSegmentation 1.2",
        stage="public pretrained",
        description="复用 LoveDA 七类权重并抽取 road 类，形成道路二值掩膜、覆盖率与复核候选。",
        strengths=["真实语义分割权重", "与地表覆盖模型共享缓存", "可接入现有二值评测"],
        limitations=["并非道路中心线或拓扑网络", "窄路与遮挡区域可能断裂", "跨地区需独立评测"],
        expected_inputs=["RGB PNG/JPEG", "LoveDA 相近俯视尺度"],
        reference_metrics={"source_model_dataset": "LoveDA validation", "source_model_mIoU": 50.28},
        metric_scope="50.28 是七类源模型 mIoU，不是道路类 IoU；道路精度必须上传真值后评测。",
        backend="mmseg-loveda-road",
        runtime="isolated-pytorch-worker",
        weight_source="MMSegmentation DeepLabV3+ R18 LoveDA official checkpoint",
        license="Apache-2.0 (MMSegmentation code; dataset/weights terms also apply)",
        recommended_device="CPU (portable) / CUDA",
        inference_parameters=[
            _threshold_parameter(
                "道路像素最低置信度",
                "仅保留预测为道路且模型置信度达到门槛的像素。",
                0.45,
            )
        ],
    ),
    ModelCard(
        id="deeplabv3plus-r50-loveda-road",
        name="DeepLabV3+ R50 · LoveDA Road",
        task=TaskType.ROAD_EXTRACTION,
        family="DeepLabV3+ / ResNet-50",
        version="MMSegmentation 1.2",
        stage="public pretrained",
        description="复用 R50 LoveDA 七类权重并抽取 road 类，作为更强的默认道路像素分割模型。",
        strengths=["更强的 R50 语义特征", "与地表覆盖 R50 共享权重缓存", "可直接接入二值真值评测"],
        limitations=["不是道路中心线或拓扑网络", "窄路和遮挡区域仍可能断裂", "CPU 推理慢于 R18"],
        expected_inputs=["RGB PNG/JPEG", "LoveDA 相近俯视尺度"],
        reference_metrics={"source_model_dataset": "LoveDA validation", "source_model_mIoU": 50.99},
        metric_scope="50.99 是七类源模型 mIoU，不是道路类 IoU；道路精度须上传真值后评测。",
        backend="mmseg-loveda-r50-road",
        runtime="isolated-pytorch-worker",
        weight_source="MMSegmentation DeepLabV3+ R50 LoveDA official checkpoint",
        license="Apache-2.0 (MMSegmentation code; dataset/weights terms also apply)",
        recommended_device="CUDA / CPU",
        inference_parameters=[
            _threshold_parameter("道路像素最低置信度", "仅保留达到门槛的道路像素。", 0.45)
        ],
    ),
    ModelCard(
        id="yolo11n-obb-dota",
        name="YOLO11n-OBB · DOTA",
        task=TaskType.OBJECT_DETECTION,
        family="YOLO11 oriented bounding boxes",
        version="Ultralytics YOLO11",
        stage="public pretrained",
        description=(
            "面向航拍影像的旋转框检测模型，可识别飞机、船舶、储罐、车辆、球场等 DOTA 类别。"
        ),
        strengths=["旋转框贴合遥感目标方向", "轻量级 nano 权重", "支持 CPU 与 Apple MPS"],
        limitations=[
            "仅覆盖 DOTA 类别体系",
            "大幅影像当前会缩放推理",
            "AGPL-3.0 商业使用需评估许可",
        ],
        expected_inputs=["RGB PNG/JPEG", "航拍或高分辨率卫星影像"],
        reference_metrics={"dataset": "DOTA-v1 validation"},
        metric_scope="模型卡只记录官方训练/验证数据集；mAP 必须通过绑定真值的 evaluation 生成。",
        backend="ultralytics-obb",
        runtime="isolated-pytorch-worker",
        weight_source="Ultralytics yolo11n-obb.pt",
        license="AGPL-3.0 (enterprise license available from Ultralytics)",
        recommended_device="Apple MPS / CUDA / CPU",
        inference_parameters=[
            _threshold_parameter(
                "检测置信度阈值",
                "只保留检测分数达到门槛的旋转框；降低会产生更多候选。",
                0.25,
            )
        ],
    ),
    ModelCard(
        id="yolo26n-obb-dota",
        name="YOLO26n-OBB · DOTA",
        task=TaskType.OBJECT_DETECTION,
        family="YOLO26 oriented bounding boxes",
        version="Ultralytics YOLO26",
        stage="public pretrained",
        description="面向航拍影像的当前代轻量旋转框检测器，作为交互运行的默认检测模型。",
        strengths=[
            "DOTA-v1 官方预训练",
            "nano 规格适合交互推理",
            "旋转框与类别置信度直接导出 GeoJSON",
        ],
        limitations=[
            "仅覆盖 DOTA 类别体系",
            "大幅影像当前会缩放推理",
            "AGPL-3.0 商业使用需评估许可",
        ],
        expected_inputs=["RGB PNG/JPEG", "航拍或高分辨率卫星影像"],
        reference_metrics={"dataset": "DOTA-v1 test", "mAP50_95_e2e": 52.4},
        metric_scope=(
            "指标来自 Ultralytics 官方模型表；用户数据 mAP "
            "必须通过绑定旋转框真值的评测生成。"
        ),
        backend="ultralytics-yolo26n-obb",
        runtime="isolated-pytorch-worker",
        weight_source="Ultralytics yolo26n-obb.pt",
        license="AGPL-3.0 (enterprise license available from Ultralytics)",
        recommended_device="Apple MPS / CUDA / CPU",
        inference_parameters=[
            _threshold_parameter("检测置信度阈值", "只保留检测分数达到门槛的旋转框。", 0.25)
        ],
    ),
    ModelCard(
        id="yolo26s-obb-dota",
        name="YOLO26s-OBB · DOTA",
        task=TaskType.OBJECT_DETECTION,
        family="YOLO26 oriented bounding boxes",
        version="Ultralytics YOLO26",
        stage="public pretrained",
        description="YOLO26 OBB 的 small 规格，为 GPU/MPS 环境提供精度更高的旋转框检测选项。",
        strengths=[
            "官方 DOTA-v1 测试指标高于 nano 规格",
            "旋转目标定位更贴合",
            "输出可审计类别和分数",
        ],
        limitations=[
            "速度与内存开销高于 nano",
            "仅覆盖 DOTA 类别体系",
            "AGPL-3.0 商业使用需评估许可",
        ],
        expected_inputs=["RGB PNG/JPEG", "航拍或高分辨率卫星影像"],
        reference_metrics={"dataset": "DOTA-v1 test", "mAP50_95_e2e": 54.8},
        metric_scope=(
            "指标来自 Ultralytics 官方模型表；用户数据 mAP "
            "必须通过绑定旋转框真值的评测生成。"
        ),
        backend="ultralytics-yolo26s-obb",
        runtime="isolated-pytorch-worker",
        weight_source="Ultralytics yolo26s-obb.pt",
        license="AGPL-3.0 (enterprise license available from Ultralytics)",
        recommended_device="Apple MPS / CUDA",
        inference_parameters=[
            _threshold_parameter("检测置信度阈值", "只保留检测分数达到门槛的旋转框。", 0.25)
        ],
    ),
]

MODEL_BY_ID = {card.id: card for card in MODEL_CARDS}

DEFAULT_MODEL_PRIORITY: dict[TaskType, tuple[str, ...]] = {
    TaskType.CHANGE_DETECTION: (
        "changer-r18-levircd",
        "geochange-robust-v3",
        "geochange-lite-v2",
    ),
    TaskType.LAND_COVER: (
        "deeplabv3plus-r50-loveda",
        "deeplabv3plus-r18-loveda",
        "landcover-lite-v2",
    ),
    TaskType.OBJECT_DETECTION: (
        "yolo26n-obb-dota",
        "yolo11n-obb-dota",
        "geodetect-lite-v2",
    ),
    TaskType.ROAD_EXTRACTION: (
        "deeplabv3plus-r50-loveda-road",
        "deeplabv3plus-r18-loveda-road",
        "roadgraph-lite-v2",
    ),
}

MODEL_WEIGHT_FILENAMES: dict[str, str] = {
    "changer-r18-levircd": "changer-r18-levircd.pth",
    "deeplabv3plus-r18-loveda": "deeplabv3plus-r18-loveda-ce0fa0ca.pth",
    "deeplabv3plus-r18-loveda-road": "deeplabv3plus-r18-loveda-ce0fa0ca.pth",
    "deeplabv3plus-r50-loveda": "deeplabv3plus-r50-loveda-f0720392.pth",
    "deeplabv3plus-r50-loveda-road": "deeplabv3plus-r50-loveda-f0720392.pth",
    "deeplabv3plus-r101-loveda": "deeplabv3plus-r101-loveda-4c1f297e.pth",
    "yolo11n-obb-dota": "yolo11n-obb.pt",
    "yolo26n-obb-dota": "yolo26n-obb.pt",
    "yolo26s-obb-dota": "yolo26s-obb.pt",
}


DEMO_ASSETS: dict[str, tuple[str, str]] = {
    "cd-before": ("CD/test_1_A.png", "image/png"),
    "cd-after": ("CD/test_1_B.png", "image/png"),
    "land-cover": ("OC/T018147.jpg", "image/jpeg"),
    "aircraft": ("OD/aircraft_14.jpg", "image/jpeg"),
    "road": ("OE/img-1.png", "image/png"),
}


DEMO_SCENARIOS = [
    DemoScenario(
        id="urban-change",
        title="城市扩张变化识别",
        subtitle="双时相 · 配准与辐射稳健变化检测",
        task=TaskType.CHANGE_DETECTION,
        primary_asset="cd-before",
        secondary_asset="cd-after",
        model_id="geochange-robust-v3",
    ),
    DemoScenario(
        id="land-cover-mapping",
        title="地表覆盖制图",
        subtitle="单时相 · LoveDA 七类语义分割",
        task=TaskType.LAND_COVER,
        primary_asset="land-cover",
        model_id="deeplabv3plus-r50-loveda",
    ),
    DemoScenario(
        id="aircraft-proposals",
        title="机场目标候选区",
        subtitle="DOTA · YOLO26 旋转框检测",
        task=TaskType.OBJECT_DETECTION,
        primary_asset="aircraft",
        model_id="yolo26n-obb-dota",
    ),
    DemoScenario(
        id="road-network",
        title="道路网络提取",
        subtitle="LoveDA · 道路像素提取",
        task=TaskType.ROAD_EXTRACTION,
        primary_asset="road",
        model_id="deeplabv3plus-r50-loveda-road",
    ),
]

SCENARIO_BY_ID = {scenario.id: scenario for scenario in DEMO_SCENARIOS}
