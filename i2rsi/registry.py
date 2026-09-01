from __future__ import annotations

from .models import DemoScenario, ModelCard, TaskType

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
    ),
]

MODEL_BY_ID = {card.id: card for card in MODEL_CARDS}


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
        subtitle="双时相 · 可解释差异基线",
        task=TaskType.CHANGE_DETECTION,
        primary_asset="cd-before",
        secondary_asset="cd-after",
        model_id="geochange-lite-v2",
    ),
    DemoScenario(
        id="land-cover-mapping",
        title="地表覆盖制图",
        subtitle="单时相 · 四类可解释分区",
        task=TaskType.LAND_COVER,
        primary_asset="land-cover",
        model_id="landcover-lite-v2",
    ),
    DemoScenario(
        id="aircraft-proposals",
        title="机场目标候选区",
        subtitle="局部纹理 · 矢量候选框",
        task=TaskType.OBJECT_DETECTION,
        primary_asset="aircraft",
        model_id="geodetect-lite-v2",
    ),
    DemoScenario(
        id="road-network",
        title="道路网络提取",
        subtitle="外观先验 · 人机协同基线",
        task=TaskType.ROAD_EXTRACTION,
        primary_asset="road",
        model_id="roadgraph-lite-v2",
    ),
]

SCENARIO_BY_ID = {scenario.id: scenario for scenario in DEMO_SCENARIOS}
