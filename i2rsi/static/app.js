const state = {
  health: null,
  models: [],
  scenarios: [],
  currentScenario: null,
  scenarioJobs: new Map(),
  scenarioBuildJobs: new Map(),
  scenarioBuildErrors: new Map(),
  currentJob: null,
  currentReview: null,
  currentModule: "workbench",
  datasets: [],
  jobs: [],
  evaluations: [],
  workflows: [],
  currentMode: "compare",
  isRunning: false,
  agentStatus: null,
  agentBusy: false,
  agentConversations: [],
  currentAgentConversationId: null,
  toastTimer: null,
};

const elements = {
  workspaceEyebrow: document.querySelector("#workspaceEyebrow"),
  workspaceTitle: document.querySelector("#workspaceTitle"),
  systemHealth: document.querySelector("#systemHealth"),
  scenarioList: document.querySelector("#scenarioList"),
  scenarioCount: document.querySelector("#scenarioCount"),
  caseTitle: document.querySelector("#caseTitle"),
  caseSubtitle: document.querySelector("#caseSubtitle"),
  taskContext: document.querySelector("#taskContext"),
  dataContext: document.querySelector("#dataContext"),
  thresholdControl: document.querySelector("#thresholdControl"),
  thresholdLabel: document.querySelector("#thresholdLabel"),
  thresholdHelp: document.querySelector("#thresholdHelp"),
  thresholdInput: document.querySelector("#thresholdInput"),
  thresholdOutput: document.querySelector("#thresholdOutput"),
  runButton: document.querySelector("#runButton"),
  runButtonLabel: document.querySelector("#runButtonLabel"),
  mapStage: document.querySelector("#mapStage"),
  baseImage: document.querySelector("#baseImage"),
  overlayImage: document.querySelector("#overlayImage"),
  singleLayerImage: document.querySelector("#singleLayerImage"),
  revealLayer: document.querySelector("#revealLayer"),
  compareHandle: document.querySelector("#compareHandle"),
  compareSlider: document.querySelector("#compareSlider"),
  overlayOpacity: document.querySelector("#overlayOpacity"),
  pointerCoordinates: document.querySelector("#pointerCoordinates"),
  stageLoader: document.querySelector("#stageLoader"),
  emptyState: document.querySelector("#emptyState"),
  jobStatus: document.querySelector("#jobStatus"),
  runId: document.querySelector("#runId"),
  copyRunId: document.querySelector("#copyRunId"),
  metricGrid: document.querySelector("#metricGrid"),
  histogram: document.querySelector("#histogram"),
  legendList: document.querySelector("#legendList"),
  modelName: document.querySelector("#modelName"),
  modelDescription: document.querySelector("#modelDescription"),
  modelStage: document.querySelector("#modelStage"),
  modelLimitations: document.querySelector("#modelLimitations"),
  provenanceStatus: document.querySelector("#provenanceStatus"),
  provenanceGrid: document.querySelector("#provenanceGrid"),
  reviewCount: document.querySelector("#reviewCount"),
  reviewSummary: document.querySelector("#reviewSummary"),
  acceptReview: document.querySelector("#acceptReview"),
  rejectReview: document.querySelector("#rejectReview"),
  runAdaptation: document.querySelector("#runAdaptation"),
  recentList: document.querySelector("#recentList"),
  downloadArtifact: document.querySelector("#downloadArtifact"),
  downloadFeatures: document.querySelector("#downloadFeatures"),
  timelineRun: document.querySelector("#timelineRun"),
  timelineArtifacts: document.querySelector("#timelineArtifacts"),
  timelineReview: document.querySelector("#timelineReview"),
  experimentDialog: document.querySelector("#experimentDialog"),
  experimentForm: document.querySelector("#experimentForm"),
  taskSelect: document.querySelector("#taskSelect"),
  modelSelect: document.querySelector("#modelSelect"),
  primaryFile: document.querySelector("#primaryFile"),
  secondaryFile: document.querySelector("#secondaryFile"),
  primaryFileName: document.querySelector("#primaryFileName"),
  secondaryFileName: document.querySelector("#secondaryFileName"),
  secondaryDropZone: document.querySelector("#secondaryDropZone"),
  dialogThresholdControl: document.querySelector("#dialogThresholdControl"),
  dialogThresholdLabel: document.querySelector("#dialogThresholdLabel"),
  dialogThresholdHelp: document.querySelector("#dialogThresholdHelp"),
  dialogThreshold: document.querySelector("#dialogThreshold"),
  dialogThresholdOutput: document.querySelector("#dialogThresholdOutput"),
  submitExperiment: document.querySelector("#submitExperiment"),
  datasetForm: document.querySelector("#datasetForm"),
  registerDataset: document.querySelector("#registerDataset"),
  datasetUploadMode: document.querySelector("#datasetUploadMode"),
  datasetSceneInputs: document.querySelector("#datasetSceneInputs"),
  datasetFolderInputs: document.querySelector("#datasetFolderInputs"),
  datasetFolder: document.querySelector("#datasetFolder"),
  datasetFolderSummary: document.querySelector("#datasetFolderSummary"),
  dataSummary: document.querySelector("#dataSummary"),
  datasetCatalog: document.querySelector("#datasetCatalog"),
  jobStatusFilter: document.querySelector("#jobStatusFilter"),
  jobTaskFilter: document.querySelector("#jobTaskFilter"),
  jobModelFilter: document.querySelector("#jobModelFilter"),
  jobCatalog: document.querySelector("#jobCatalog"),
  modelCatalog: document.querySelector("#modelCatalog"),
  modelCountBadge: document.querySelector("#modelCountBadge"),
  workflowForm: document.querySelector("#workflowForm"),
  workflowName: document.querySelector("#workflowName"),
  workflowDataset: document.querySelector("#workflowDataset"),
  workflowTask: document.querySelector("#workflowTask"),
  workflowModels: document.querySelector("#workflowModels"),
  workflowParameters: document.querySelector("#workflowParameters"),
  runWorkflow: document.querySelector("#runWorkflow"),
  workflowCatalog: document.querySelector("#workflowCatalog"),
  workflowCountBadge: document.querySelector("#workflowCountBadge"),
  evaluationForm: document.querySelector("#evaluationForm"),
  evaluationJob: document.querySelector("#evaluationJob"),
  createEvaluation: document.querySelector("#createEvaluation"),
  evaluationList: document.querySelector("#evaluationList"),
  evaluationDetail: document.querySelector("#evaluationDetail"),
  openAgentButton: document.querySelector("#openAgentButton"),
  agentDialog: document.querySelector("#agentDialog"),
  closeAgent: document.querySelector("#closeAgent"),
  agentStatus: document.querySelector("#agentStatus"),
  newAgentConversation: document.querySelector("#newAgentConversation"),
  agentHistoryList: document.querySelector("#agentHistoryList"),
  agentConversationTitle: document.querySelector("#agentConversationTitle"),
  agentMemoryStatus: document.querySelector("#agentMemoryStatus"),
  agentMessages: document.querySelector("#agentMessages"),
  agentForm: document.querySelector("#agentForm"),
  agentInput: document.querySelector("#agentInput"),
  agentAllowActions: document.querySelector("#agentAllowActions"),
  sendAgentMessage: document.querySelector("#sendAgentMessage"),
  aboutDialog: document.querySelector("#aboutDialog"),
  toast: document.querySelector("#toast"),
};

const taskLabels = {
  change_detection: "Change detection",
  land_cover: "Land-cover mapping",
  object_detection: "Oriented object detection",
  road_extraction: "Road extraction",
};

const modelCategoryLabels = {
  change_detection: "变化检测",
  land_cover: "地表覆盖",
  object_detection: "旋转框目标检测",
  road_extraction: "道路提取",
};

const statusLabels = {
  queued: "等待调度",
  running: "正在运行",
  succeeded: "运行成功",
  failed: "运行失败",
};

const workflowStatusLabels = {
  planned: "计划已生成",
  queued: "等待调度",
  running: "正在编排",
  awaiting_ground_truth: "等待真值",
  succeeded: "编排完成",
  partially_succeeded: "部分完成",
  failed: "编排失败",
};

const metricDefinitions = {
  change_detection: [
    ["预测变化", "predicted_change_pct", "%", "本次预测面积占比"],
    ["置信度代理", "mean_confidence_proxy", "", "不是测试集精度"],
    ["不确定性代理", "mean_uncertainty_proxy", "", "用于安排人工复核"],
    ["端到端耗时", "runtime_ms", " ms", "本机 CPU 基线"],
  ],
  land_cover: [
    ["建成区预测", "built_up_pct", "%", "本次像素占比"],
    ["植被预测", "vegetation_pct", "%", "本次像素占比"],
    ["置信度代理", "mean_confidence_proxy", "", "不是 mIoU / F1"],
    ["端到端耗时", "runtime_ms", " ms", "本机 CPU 基线"],
  ],
  object_detection: [
    ["候选目标", "candidate_count", "", "待人工复核"],
    ["显著性均值", "mean_saliency_score", "", "不是类别概率"],
    ["复核数量", "review_required", "", "候选区域"],
    ["端到端耗时", "runtime_ms", " ms", "本机 CPU 基线"],
  ],
  road_extraction: [
    ["道路候选", "predicted_road_pct", "%", "本次预测面积占比"],
    ["置信度代理", "mean_confidence_proxy", "", "不是测试集精度"],
    ["候选区域", "candidate_region_count", "", "待连通性复核"],
    ["端到端耗时", "runtime_ms", " ms", "本机 CPU 基线"],
  ],
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { Accept: "application/json", ...(options.headers || {}) },
    ...options,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "object" ? payload.detail : payload;
    throw new Error(detail || `请求失败 (${response.status})`);
  }
  return payload;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function modelById(modelId) {
  return state.models.find((model) => model.id === modelId);
}

function thresholdSpec(modelId) {
  return modelById(modelId)?.inference_parameters?.find((item) => item.key === "threshold") || null;
}

function configureThresholdControl({container, label, help, input, output}, modelId) {
  const spec = thresholdSpec(modelId);
  container.hidden = !spec;
  input.disabled = !spec;
  if (!spec) return;
  label.textContent = spec.label;
  help.textContent = spec.description;
  input.min = String(spec.minimum);
  input.max = String(spec.maximum);
  input.step = String(spec.step);
  input.value = String(spec.default);
  output.textContent = Number(spec.default).toFixed(2);
}

function updateScenarioParameter() {
  configureThresholdControl(
    {
      container: elements.thresholdControl,
      label: elements.thresholdLabel,
      help: elements.thresholdHelp,
      input: elements.thresholdInput,
      output: elements.thresholdOutput,
    },
    state.currentScenario?.model_id,
  );
}

function updateDialogParameter() {
  configureThresholdControl(
    {
      container: elements.dialogThresholdControl,
      label: elements.dialogThresholdLabel,
      help: elements.dialogThresholdHelp,
      input: elements.dialogThreshold,
      output: elements.dialogThresholdOutput,
    },
    elements.modelSelect.value,
  );
}

function showToast(message, isError = false) {
  clearTimeout(state.toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("is-error", isError);
  elements.toast.classList.add("is-visible");
  state.toastTimer = window.setTimeout(() => elements.toast.classList.remove("is-visible"), 3600);
}

function setHealth(health) {
  state.health = health;
  elements.systemHealth.classList.remove("is-offline");
  elements.systemHealth.querySelector("span:last-child").textContent =
    `本地引擎在线 · v${health.version}`;
}

function setOffline(message) {
  elements.systemHealth.classList.add("is-offline");
  elements.systemHealth.querySelector("span:last-child").textContent = message;
}

function renderScenarios() {
  elements.scenarioCount.textContent = state.scenarios.length;
  elements.scenarioList.replaceChildren();
  state.scenarios.forEach((scenario, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "scenario-card";
    button.dataset.scenarioId = scenario.id;
    button.setAttribute("aria-pressed", String(state.currentScenario?.id === scenario.id));
    button.innerHTML = `
      <span class="scenario-number">${String(index + 1).padStart(2, "0")}</span>
      <span class="scenario-copy"><strong>${escapeHtml(scenario.title)}</strong><small>${escapeHtml(scenario.subtitle)}</small></span>
      <span class="scenario-build-status" data-scenario-build>待构建</span>`;
    button.addEventListener("click", () => selectScenario(scenario));
    elements.scenarioList.append(button);
  });
  syncScenarioSelection();
  updateScenarioBuildStatuses();
}

function syncScenarioSelection() {
  document.querySelectorAll(".scenario-card").forEach((card) => {
    const active = card.dataset.scenarioId === state.currentScenario?.id;
    card.classList.toggle("is-active", active);
    card.setAttribute("aria-pressed", String(active));
  });
}

function updateScenarioBuildStatuses() {
  document.querySelectorAll(".scenario-card").forEach((card) => {
    const status = card.querySelector("[data-scenario-build]");
    const scenarioId = card.dataset.scenarioId;
    let stateName = "pending";
    let label = "待构建";
    if (state.scenarioJobs.has(scenarioId)) {
      stateName = "ready";
      label = "已就绪";
    } else if (state.scenarioBuildJobs.has(scenarioId)) {
      const job = state.scenarioBuildJobs.get(scenarioId);
      stateName = job.status === "running" ? "running" : "queued";
      label = job.status === "running" ? "构建中" : "等待中";
    } else if (state.scenarioBuildErrors.has(scenarioId)) {
      stateName = "failed";
      label = "失败";
    }
    status.className = `scenario-build-status is-${stateName}`;
    status.textContent = label;
  });
}

function selectScenario(scenario) {
  state.currentScenario = scenario;
  elements.caseTitle.textContent = scenario.title;
  elements.caseSubtitle.textContent = scenario.subtitle;
  elements.taskContext.textContent = taskLabels[scenario.task] || scenario.task;
  elements.dataContext.textContent = scenario.id === "urban-change" ? "WHU change pair" : "Bundled RGB demo";
  updateScenarioParameter();
  syncScenarioSelection();
  renderModelCard(scenario.model_id);
  elements.baseImage.src = `/api/v1/demo-assets/${scenario.primary_asset}`;
  elements.overlayImage.removeAttribute("src");
  elements.singleLayerImage.removeAttribute("src");
  const completedJob = state.scenarioJobs.get(scenario.id);
  if (completedJob) {
    state.currentJob = completedJob;
    elements.mapStage.classList.remove("is-loading");
    renderJob(completedJob, {notify: false});
    syncScenarioRunButton();
    return;
  }
  state.currentJob = null;
  resetObservation();
  const buildingJob = state.scenarioBuildJobs.get(scenario.id);
  if (buildingJob) {
    showScenarioBuilding(scenario, buildingJob);
    return;
  }
  elements.mapStage.classList.remove("is-loading");
  const error = state.scenarioBuildErrors.get(scenario.id);
  showViewerEmpty(
    error ? "示例构建失败" : "当前场景尚未运行",
    error || "点击“运行示例”开始解译",
  );
  setViewMode("compare");
  syncScenarioRunButton();
}

function showViewerEmpty(title, detail) {
  elements.emptyState.querySelector("strong").textContent = title;
  elements.emptyState.querySelector("span").textContent = detail;
  elements.emptyState.hidden = false;
}

function showScenarioBuilding(scenario, job) {
  state.currentJob = job;
  elements.emptyState.hidden = true;
  elements.mapStage.classList.add("is-loading");
  elements.stageLoader.querySelector("strong").textContent = job.status === "running"
    ? `正在构建「${scenario.title}」示例`
    : `等待构建「${scenario.title}」示例`;
  elements.stageLoader.querySelector("small").textContent = "示例作业按顺序执行，完成后自动展示";
  updateJobStatus(job);
  setViewMode("compare");
  syncScenarioRunButton();
}

function syncScenarioRunButton() {
  const building = state.scenarioBuildJobs.get(state.currentScenario?.id);
  elements.runButtonLabel.textContent = state.isRunning
    ? "正在运行"
    : ["queued", "running"].includes(building?.status)
      ? "正在构建"
      : state.scenarioJobs.has(state.currentScenario?.id)
        ? "重新运行"
        : "运行示例";
  elements.runButton.disabled = state.isRunning
    || ["queued", "running"].includes(building?.status);
}

function renderModelCard(modelId) {
  const card = state.models.find((item) => item.id === modelId);
  if (!card) return;
  elements.modelName.textContent = card.name;
  elements.modelDescription.textContent = card.description;
  const runtime = card.runtime_status;
  elements.modelStage.textContent = runtime
    ? `${card.is_default ? "当前环境默认 · " : ""}${card.stage} · ${runtime.ready ? `可运行 / ${runtime.device}` : "未就绪"}`
    : card.stage;
  elements.modelLimitations.replaceChildren();
  card.limitations.forEach((limitation) => {
    const item = document.createElement("li");
    item.textContent = limitation;
    elements.modelLimitations.append(item);
  });
}

function resetObservation() {
  elements.jobStatus.className = "status-pill status-queued";
  elements.jobStatus.textContent = "等待运行";
  elements.runId.textContent = "—";
  elements.copyRunId.disabled = true;
  elements.provenanceStatus.textContent = "待生成";
  elements.provenanceStatus.classList.remove("is-verified");
  elements.reviewCount.textContent = "0";
  elements.reviewSummary.textContent = "实验完成后，将根据不确定性与模型限制生成复核建议。";
  elements.downloadArtifact.href = "#";
  elements.downloadArtifact.setAttribute("aria-disabled", "true");
  elements.downloadFeatures.href = "#";
  elements.downloadFeatures.setAttribute("aria-disabled", "true");
  elements.timelineRun.classList.remove("is-complete");
  elements.timelineArtifacts.classList.remove("is-complete");
  elements.timelineReview.classList.remove("is-complete");
  renderMetrics(null, state.currentScenario?.task || "change_detection");
  renderHistogram([]);
  elements.legendList.innerHTML = '<p class="muted">运行后生成图例</p>';
  elements.provenanceGrid.innerHTML = `
    <div><dt>输入摘要</dt><dd>—</dd></div><div><dt>引擎版本</dt><dd>—</dd></div>
    <div><dt>模型版本</dt><dd>—</dd></div><div><dt>参数</dt><dd>—</dd></div>`;
}

function setRunning(running, label = "正在构建可复现实验") {
  state.isRunning = running;
  elements.submitExperiment.disabled = running;
  elements.mapStage.classList.toggle("is-loading", running);
  document.querySelectorAll(".scenario-card").forEach((button) => {
    button.disabled = running;
  });
  elements.stageLoader.querySelector("strong").textContent = label;
  if (running) {
    elements.emptyState.hidden = true;
    elements.timelineRun.classList.add("is-complete");
  }
  syncScenarioRunButton();
}

async function runCurrentScenario() {
  const existingBuild = state.scenarioBuildJobs.get(state.currentScenario?.id);
  if (
    !state.currentScenario
    || state.isRunning
    || ["queued", "running"].includes(existingBuild?.status)
  ) return;
  const scenarioId = state.currentScenario.id;
  resetObservation();
  setRunning(true);
  elements.jobStatus.className = "status-pill status-running";
  elements.jobStatus.textContent = "正在运行";
  const spec = thresholdSpec(state.currentScenario.model_id);
  const query = spec ? `?threshold=${Number(elements.thresholdInput.value)}` : "";
  try {
    const manifest = await api(
      `/api/v1/demo-runs/${encodeURIComponent(state.currentScenario.id)}${query}`,
      { method: "POST" },
    );
    state.currentJob = manifest;
    elements.runId.textContent = manifest.id;
    elements.copyRunId.disabled = false;
    await waitForJob(manifest.id, {scenarioId});
  } catch (error) {
    handleRunError(error);
  }
}

async function waitForJob(jobId, {scenarioId = null} = {}) {
  const started = Date.now();
  while (Date.now() - started < 60000) {
    const job = await api(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
    state.currentJob = job;
    updateJobStatus(job);
    if (job.status === "succeeded") {
      if (scenarioId) {
        state.scenarioJobs.set(scenarioId, job);
        state.scenarioBuildJobs.delete(scenarioId);
        state.scenarioBuildErrors.delete(scenarioId);
        updateScenarioBuildStatuses();
      }
      renderJob(job);
      setRunning(false);
      await refreshRecentJobs();
      return;
    }
    if (job.status === "failed") {
      throw new Error(job.error || "解译任务失败");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 500));
  }
  throw new Error("任务等待超时，请在最近运行中检查状态");
}

function scenarioIdFromJob(job) {
  const source = job.inputs
    ?.map((item) => item.source)
    .find((value) => value?.startsWith("bundled-demo:"));
  return source?.replace("bundled-demo:", "") || null;
}

async function trackScenarioExample(scenario, initialJob) {
  let job = initialJob;
  if (job.status === "succeeded") {
    state.scenarioJobs.set(scenario.id, job);
    state.scenarioBuildJobs.delete(scenario.id);
    updateScenarioBuildStatuses();
    if (state.currentScenario?.id === scenario.id) {
      state.currentJob = job;
      renderJob(job, {notify: false});
      syncScenarioRunButton();
    }
    return;
  }

  state.scenarioBuildJobs.set(scenario.id, job);
  updateScenarioBuildStatuses();
  if (state.currentScenario?.id === scenario.id) showScenarioBuilding(scenario, job);
  const started = Date.now();
  while (["queued", "running"].includes(job.status) && Date.now() - started < 120000) {
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    job = await api(`/api/v1/jobs/${encodeURIComponent(job.id)}`);
    state.scenarioBuildJobs.set(scenario.id, job);
    updateScenarioBuildStatuses();
    if (state.currentScenario?.id === scenario.id) showScenarioBuilding(scenario, job);
  }

  state.scenarioBuildJobs.delete(scenario.id);
  if (job.status === "succeeded") {
    state.scenarioJobs.set(scenario.id, job);
    state.scenarioBuildErrors.delete(scenario.id);
    if (state.currentScenario?.id === scenario.id) {
      state.currentJob = job;
      renderJob(job, {notify: false});
      syncScenarioRunButton();
    }
  } else {
    const message = job.error || "示例作业等待超时，请手动重新运行";
    state.scenarioBuildErrors.set(scenario.id, message);
    if (state.currentScenario?.id === scenario.id) {
      state.currentJob = job;
      elements.mapStage.classList.remove("is-loading");
      showViewerEmpty("示例构建失败", message);
      updateJobStatus({...job, status: "failed"});
      syncScenarioRunButton();
    }
  }
  updateScenarioBuildStatuses();
}

async function bootstrapScenarioExamples() {
  const jobs = await api("/api/v1/demo-runs/bootstrap", {method: "POST"});
  const jobsByScenario = new Map(
    jobs.map((job) => [scenarioIdFromJob(job), job]).filter(([scenarioId]) => scenarioId),
  );
  await Promise.all(
    state.scenarios
      .filter((scenario) => jobsByScenario.has(scenario.id))
      .map((scenario) => trackScenarioExample(scenario, jobsByScenario.get(scenario.id))),
  );
}

function handleRunError(error) {
  setRunning(false);
  showViewerEmpty("解译运行失败", "请检查提示信息后重新运行");
  elements.jobStatus.className = "status-pill status-failed";
  elements.jobStatus.textContent = "运行失败";
  showToast(error instanceof Error ? error.message : "运行失败", true);
}

function updateJobStatus(job) {
  const validStatus = ["queued", "running", "succeeded", "failed"].includes(job.status)
    ? job.status
    : "queued";
  elements.jobStatus.className = `status-pill status-${validStatus}`;
  elements.jobStatus.textContent = statusLabels[validStatus];
  elements.runId.textContent = job.id;
  elements.copyRunId.disabled = false;
}

function artifactMap(job) {
  return Object.fromEntries(job.artifacts.map((artifact) => [artifact.kind, artifact]));
}

function renderJob(job, {notify = true} = {}) {
  updateJobStatus(job);
  elements.mapStage.classList.remove("is-loading");
  elements.emptyState.hidden = true;
  const artifacts = artifactMap(job);
  elements.baseImage.src = artifacts.original?.url || "";
  elements.overlayImage.src = artifacts.overlay?.url || "";
  elements.overlayImage.style.opacity = String(Number(elements.overlayOpacity.value) / 100);
  elements.singleLayerImage.src = artifacts.overlay?.url || "";
  elements.timelineArtifacts.classList.add("is-complete");
  elements.timelineReview.classList.add("is-complete");
  renderMetrics(job.metrics, job.task);
  renderHistogram(job.histogram);
  renderLegend(job.legend);
  renderProvenance(job);
  renderReview(job);
  renderModelCard(job.model_id);
  const preferred = artifacts.overlay;
  if (preferred) {
    elements.downloadArtifact.href = preferred.url;
    elements.downloadArtifact.removeAttribute("aria-disabled");
  }
  if (artifacts.features) {
    elements.downloadFeatures.href = artifacts.features.url;
    elements.downloadFeatures.removeAttribute("aria-disabled");
  }
  setViewMode(state.currentMode);
  if (notify) showToast(`实验 ${job.id.slice(0, 8)} 已完成，全部产物已登记`);
}

function renderMetrics(metrics, task) {
  const definitions = metricDefinitions[task] || metricDefinitions.change_detection;
  elements.metricGrid.replaceChildren();
  definitions.forEach(([label, key, suffix, note]) => {
    const article = document.createElement("article");
    const value = metrics?.[key];
    const shown = value === undefined || value === null ? "—" : `${value}${suffix}`;
    article.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(shown)}</strong><small>${escapeHtml(note)}</small>`;
    elements.metricGrid.append(article);
  });
}

function renderHistogram(values) {
  const bars = [...elements.histogram.querySelectorAll("i")];
  const maximum = Math.max(...values, 1);
  bars.forEach((bar, index) => {
    const value = values[index] || 0;
    bar.style.height = `${Math.max(2, Math.round((value / maximum) * 100))}%`;
    bar.title = `${index / 10}–${(index + 1) / 10}: ${value.toLocaleString()} px`;
  });
}

function renderLegend(legend) {
  elements.legendList.replaceChildren();
  if (!legend.length) {
    elements.legendList.innerHTML = '<p class="muted">无图例信息</p>';
    return;
  }
  legend.forEach((entry) => {
    const row = document.createElement("div");
    row.className = "legend-item";
    const share = Number(entry.share || 0);
    row.innerHTML = `<i></i><span>${escapeHtml(entry.label)}</span><code>${(share * 100).toFixed(1)}%</code>`;
    row.querySelector("i").style.setProperty("--legend-colour", entry.colour);
    elements.legendList.append(row);
  });
}

function renderProvenance(job) {
  const provenance = job.provenance || {};
  const inputDigest = provenance.input_sha256?.[0]?.slice(0, 14) || "—";
  const parameterText = Object.entries(provenance.parameters || {})
    .map(([key, value]) => `${key}=${value}`)
    .join(" · ") || "模型无可调推理参数";
  elements.provenanceStatus.textContent = "✓ manifest 已登记";
  elements.provenanceStatus.classList.add("is-verified");
  elements.provenanceGrid.innerHTML = `
    <div><dt>输入 SHA-256</dt><dd title="${escapeHtml(provenance.input_sha256?.[0] || "")}">${escapeHtml(inputDigest)}…</dd></div>
    <div><dt>引擎版本</dt><dd>${escapeHtml(`${provenance.engine || "—"}@${provenance.engine_version || "—"}`)}</dd></div>
    <div><dt>模型版本</dt><dd>${escapeHtml(job.model_id)}</dd></div>
    <div><dt>参数</dt><dd>${escapeHtml(parameterText)}</dd></div>`;
}

function renderReview(job) {
  state.currentReview = null;
  elements.reviewCount.textContent = "…";
  elements.reviewSummary.textContent = "正在按不确定性与多样性计算复核优先级。";
  elements.acceptReview.disabled = true;
  elements.rejectReview.disabled = true;
  elements.runAdaptation.disabled = false;
  loadReviewQueue(job).catch((error) => {
    elements.reviewCount.textContent = "0";
    elements.reviewSummary.textContent = `复核队列不可用：${error.message}`;
  });
}

async function loadReviewQueue(job) {
  const reviews = await api(
    `/api/v1/geoadapt/reviews?job_id=${encodeURIComponent(job.id)}&limit=100`,
  );
  state.currentReview = reviews[0] || null;
  elements.reviewCount.textContent = String(reviews.length);
  elements.acceptReview.disabled = !state.currentReview;
  elements.rejectReview.disabled = !state.currentReview;
  if (!state.currentReview) {
    elements.reviewSummary.textContent = "该运行的候选区域已全部复核，可生成适配轮次。";
    return;
  }
  const candidate = state.currentReview;
  elements.reviewSummary.textContent =
    `优先候选 ${candidate.id.slice(0, 8)} · ${candidate.suggested_label} · ` +
    `不确定性 ${candidate.uncertainty_score.toFixed(3)} · ` +
    `采样分数 ${candidate.acquisition_score.toFixed(3)}`;
}

async function submitReviewDecision(decision) {
  if (!state.currentReview || !state.currentJob) return;
  const candidateId = state.currentReview.id;
  elements.acceptReview.disabled = true;
  elements.rejectReview.disabled = true;
  try {
    const event = await api(
      `/api/v1/geoadapt/reviews/${encodeURIComponent(candidateId)}/annotations`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, reviewer: "workbench-user" }),
      },
    );
    showToast(`标注 ${event.dataset_version} 已写入不可变事件链`);
    await loadReviewQueue(state.currentJob);
  } catch (error) {
    showToast(`复核失败：${error.message}`);
    elements.acceptReview.disabled = false;
    elements.rejectReview.disabled = false;
  }
}

async function runAdaptationRound() {
  if (!state.currentJob) return;
  elements.runAdaptation.disabled = true;
  try {
    const result = await api("/api/v1/geoadapt/adaptations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task: state.currentJob.task,
        model_id: state.currentJob.model_id,
        min_samples: 4,
      }),
    });
    showToast(
      `适配轮次完成：${result.sample_count} 个样本，Brier ${result.brier_before.toFixed(3)} → ${result.brier_after.toFixed(3)}`,
    );
    await loadReviewQueue(state.currentJob);
  } catch (error) {
    showToast(`暂不能适配：${error.message}`);
  } finally {
    elements.runAdaptation.disabled = false;
  }
}

function setViewMode(mode) {
  state.currentMode = mode;
  elements.mapStage.classList.toggle("is-compare", mode === "compare");
  document.querySelectorAll("[data-view-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewMode === mode);
  });
  const jobArtifacts = state.currentJob?.status === "succeeded" ? artifactMap(state.currentJob) : {};
  const compare = mode === "compare";
  elements.revealLayer.hidden = !compare;
  elements.compareHandle.hidden = !compare;
  elements.compareSlider.hidden = !compare;
  elements.singleLayerImage.hidden = compare;
  document.querySelector(".map-label-before").hidden = !compare;
  document.querySelector(".map-label-after").hidden = !compare;
  if (!compare) {
    const artifact = jobArtifacts[mode] || jobArtifacts.overlay;
    elements.singleLayerImage.src = artifact?.url || "";
  }
  const downloadable = compare ? jobArtifacts.overlay : jobArtifacts[mode] || jobArtifacts.overlay;
  if (downloadable) elements.downloadArtifact.href = downloadable.url;
}

function updateCompare(value) {
  const percentage = Number(value);
  elements.revealLayer.style.clipPath = `inset(0 ${100 - percentage}% 0 0)`;
  elements.compareHandle.style.left = `${percentage}%`;
}

function updateCompareFromPointer(event) {
  if (state.currentMode !== "compare") return;
  const bounds = elements.compareSlider.getBoundingClientRect();
  if (!bounds.width) return;
  const percentage = Math.max(
    0,
    Math.min(100, ((event.clientX - bounds.left) / bounds.width) * 100),
  );
  elements.compareSlider.value = String(percentage);
  updateCompare(percentage);
}

async function refreshRecentJobs() {
  try {
    const jobs = await api("/api/v1/jobs?limit=4");
    elements.recentList.replaceChildren();
    if (!jobs.length) {
      elements.recentList.innerHTML = '<p class="muted">暂无历史运行</p>';
      return;
    }
    jobs.forEach((job) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "recent-item";
      const when = new Date(job.created_at);
      button.innerHTML = `
        <i></i><span class="recent-item-copy"><strong>${escapeHtml(job.id.slice(0, 12))}</strong><small>${escapeHtml(taskLabels[job.task] || job.task)} · ${escapeHtml(statusLabels[job.status] || job.status)}</small></span>
        <time datetime="${escapeHtml(job.created_at)}">${when.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</time>`;
      button.querySelector("i").style.background = job.status === "succeeded" ? "var(--green)" : job.status === "failed" ? "var(--pink)" : "var(--amber)";
      button.addEventListener("click", () => {
        state.currentJob = job;
        if (job.status === "succeeded") renderJob(job);
        else updateJobStatus(job);
      });
      elements.recentList.append(button);
    });
  } catch (error) {
    console.warn("Unable to refresh jobs", error);
  }
}

function updateModelOptions() {
  const task = elements.taskSelect.value;
  const options = modelOptionsForTask(task);
  elements.modelSelect.replaceChildren();
  options.forEach((model) => {
    const option = document.createElement("option");
    option.value = model.id;
    const ready = model.runtime_status?.ready !== false;
    option.disabled = !ready;
    option.textContent = `${model.name}${model.is_default ? " · 默认" : ""} · ${model.stage}${ready ? "" : " · 未就绪"}`;
    elements.modelSelect.append(option);
  });
  const needsSecond = task === "change_detection";
  elements.secondaryDropZone.classList.toggle("is-hidden", !needsSecond);
  elements.secondaryFile.required = needsSecond;
  updateDialogParameter();
}

async function submitUpload(event) {
  event.preventDefault();
  if (state.isRunning) return;
  const formData = new FormData(elements.experimentForm);
  if (elements.taskSelect.value !== "change_detection") formData.delete("secondary");
  setRunning(true, "正在校验上传影像");
  elements.submitExperiment.textContent = "正在创建…";
  try {
    const job = await api("/api/v1/jobs", { method: "POST", body: formData, headers: {} });
    state.currentJob = job;
    elements.experimentDialog.close();
    elements.caseTitle.textContent = "自定义解译实验";
    elements.caseSubtitle.textContent = taskLabels[job.task] || job.task;
    elements.taskContext.textContent = taskLabels[job.task] || job.task;
    elements.dataContext.textContent = "Local upload";
    renderModelCard(job.model_id);
    await waitForJob(job.id);
  } catch (error) {
    handleRunError(error);
  } finally {
    elements.submitExperiment.textContent = "校验并运行";
  }
}

const moduleTitles = {
  workbench: ["GeoAI Research Workbench", "遥感智能解译实验台"],
  data: ["Versioned Data Catalog", "数据目录与版本"],
  jobs: ["Reproducible Run Ledger", "解译作业中心"],
  workflows: ["Auditable Orchestration", "流程编排中心"],
  models: ["Transparent Model Registry", "模型注册表"],
  evaluation: ["Ground-truth Evaluation", "可信评测中心"],
};

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function formatDate(value) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function showModule(name) {
  const module = document.querySelector(`[data-module="${name}"]`);
  if (!module) return;
  state.currentModule = name;
  document.querySelectorAll("[data-module]").forEach((item) => {
    item.hidden = item !== module;
  });
  document.querySelectorAll("[data-nav]").forEach((button) => {
    const active = button.dataset.nav === name;
    button.classList.toggle("is-active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  const [eyebrow, title] = moduleTitles[name];
  elements.workspaceEyebrow.textContent = eyebrow;
  elements.workspaceTitle.textContent = title;
  if (name === "data") await refreshDatasets();
  if (name === "jobs") await refreshJobCatalog();
  if (name === "workflows") {
    await refreshDatasets();
    await refreshWorkflows();
  }
  if (name === "models") renderModelCatalog();
  if (name === "evaluation") await refreshEvaluations();
}

function modelOptionsForTask(task) {
  return state.models
    .filter((model) => !task || model.task === task)
    .sort((first, second) => Number(Boolean(second.is_default)) - Number(Boolean(first.is_default)));
}

function renderDataSummary(summary) {
  const values = [
    [summary.registered_datasets, "版本化记录"],
    [summary.registered_assets, "SHA-256 校验"],
    [formatBytes(summary.bytes_total), "项目 artifact 目录"],
    [summary.bundled_demo_scenarios, "只读演示数据"],
  ];
  [...elements.dataSummary.children].forEach((card, index) => {
    card.querySelector("strong").textContent = values[index][0];
    card.querySelector("small").textContent = values[index][1];
  });
}

function updateWorkflowModelOptions() {
  const task = elements.workflowTask.value;
  elements.workflowModels.replaceChildren();
  modelOptionsForTask(task)
    .forEach((model) => {
      const option = document.createElement("option");
      option.value = model.id;
      const ready = model.runtime_status?.ready !== false;
      option.disabled = !ready;
      option.textContent = `${model.name}${model.is_default ? " · 默认" : ""}${ready ? ` · ${model.runtime_status?.device || model.runtime}` : " · 未就绪"}`;
      elements.workflowModels.append(option);
    });
  renderWorkflowParameters();
}

function selectedWorkflowModels() {
  const selectedIds = [...elements.workflowModels.selectedOptions]
    .filter((option) => !option.disabled)
    .map((option) => option.value);
  const effectiveIds = selectedIds.length
    ? selectedIds
    : [...elements.workflowModels.options]
      .filter((option) => !option.disabled)
      .map((option) => option.value);
  return effectiveIds.map(modelById).filter(Boolean);
}

function renderWorkflowParameters() {
  const previous = new Map(
    [...elements.workflowParameters.querySelectorAll("input[data-model-id]")]
      .map((input) => [`${input.dataset.modelId}:${input.dataset.parameterKey}`, input.value]),
  );
  elements.workflowParameters.replaceChildren();
  const configurable = selectedWorkflowModels()
    .flatMap((model) => model.inference_parameters.map((spec) => ({model, spec})));
  if (!configurable.length) {
    const note = document.createElement("small");
    note.textContent = "所选模型没有需要手动设置的推理参数，将按固定配置运行。";
    elements.workflowParameters.append(note);
    return;
  }
  configurable.forEach(({model, spec}) => {
    const row = document.createElement("div");
    row.className = "model-parameter-row";
    const copy = document.createElement("div");
    copy.className = "model-parameter-copy";
    const title = document.createElement("strong");
    title.textContent = `${model.name} · ${spec.label}`;
    const help = document.createElement("small");
    help.textContent = spec.description;
    copy.append(title, help);
    const input = document.createElement("input");
    input.type = "number";
    input.min = String(spec.minimum);
    input.max = String(spec.maximum);
    input.step = String(spec.step);
    input.value = previous.get(`${model.id}:${spec.key}`) || String(spec.default);
    input.dataset.modelId = model.id;
    input.dataset.parameterKey = spec.key;
    input.setAttribute("aria-label", `${model.name} ${spec.label}`);
    row.append(copy, input);
    elements.workflowParameters.append(row);
  });
}

function populateWorkflowDatasets() {
  const previous = elements.workflowDataset.value;
  elements.workflowDataset.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = state.datasets.length ? "请选择数据版本" : "请先登记数据集";
  elements.workflowDataset.append(placeholder);
  state.datasets.forEach((dataset) => {
    const option = document.createElement("option");
    option.value = dataset.id;
    option.textContent = `${dataset.name} · ${dataset.version}`;
    elements.workflowDataset.append(option);
  });
  if (state.datasets.some((dataset) => dataset.id === previous)) {
    elements.workflowDataset.value = previous;
  }
}

function syncWorkflowDatasetTask() {
  const dataset = state.datasets.find((item) => item.id === elements.workflowDataset.value);
  if (dataset?.task_hint) elements.workflowTask.value = dataset.task_hint;
  updateWorkflowModelOptions();
}

function renderDatasetCatalog() {
  elements.datasetCatalog.replaceChildren();
  if (!state.datasets.length) {
    elements.datasetCatalog.innerHTML = '<p class="muted">暂无已登记数据集。左侧上传后会生成不可变内容版本。</p>';
    return;
  }
  state.datasets.forEach((dataset) => {
    const article = document.createElement("article");
    article.className = "catalog-item dataset-item";
    const isFolder = dataset.layout === "folder";
    const assets = isFolder
      ? `${dataset.sample_count || dataset.assets.length} 张影像 · 保留目录结构`
      : dataset.assets.map((asset) => `${asset.role} · ${asset.width_px}×${asset.height_px}`).join(" / ");
    article.innerHTML = `
      <div class="catalog-item-head"><div><strong>${escapeHtml(dataset.name)}</strong><code>${escapeHtml(dataset.version)}</code></div><span>${escapeHtml(taskLabels[dataset.task_hint] || "未指定任务")}</span></div>
      <p>${escapeHtml(dataset.description || "无补充说明")}</p>
      <div class="catalog-meta"><span>${escapeHtml(assets)}</span><span>${formatBytes(dataset.assets.reduce((sum, item) => sum + item.bytes, 0))}</span><span>${formatDate(dataset.created_at)}</span></div>`;
    const controls = document.createElement("div");
    controls.className = "catalog-actions";
    if (isFolder) {
      const note = document.createElement("small");
      note.className = "dataset-layout-note";
      note.textContent = "文件夹版本已登记；单景运行和现有多模型编排不会误用批量数据。";
      controls.append(note);
      article.append(controls);
      elements.datasetCatalog.append(article);
      return;
    }
    const select = document.createElement("select");
    const models = modelOptionsForTask(dataset.task_hint);
    models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model.id;
      option.dataset.task = model.task;
      const ready = model.runtime_status?.ready !== false;
      option.disabled = !ready;
      option.textContent = `${model.name}${model.is_default ? " · 默认" : ""} · ${taskLabels[model.task]}${ready ? "" : " · 未就绪"}`;
      select.append(option);
    });
    const run = document.createElement("button");
    run.type = "button";
    run.className = "button button-quiet";
    run.textContent = "从此版本运行";
    run.addEventListener("click", () => runRegisteredDataset(dataset, select, run));
    controls.append(select, run);
    if (dataset.task_hint) {
      const orchestrate = document.createElement("button");
      orchestrate.type = "button";
      orchestrate.className = "button button-quiet";
      orchestrate.textContent = "多模型编排";
      orchestrate.addEventListener("click", async () => {
        await showModule("workflows");
        elements.workflowDataset.value = dataset.id;
        syncWorkflowDatasetTask();
      });
      controls.append(orchestrate);
    }
    article.append(controls);
    elements.datasetCatalog.append(article);
  });
}

async function refreshDatasets() {
  try {
    const [summary, datasets] = await Promise.all([
      api("/api/v1/data/summary"),
      api("/api/v1/datasets?limit=100"),
    ]);
    state.datasets = datasets;
    renderDataSummary(summary);
    renderDatasetCatalog();
    populateWorkflowDatasets();
  } catch (error) {
    showToast(`数据目录读取失败：${error.message}`, true);
  }
}

function workflowStatusClass(status) {
  if (status === "succeeded") return "status-succeeded";
  if (status === "failed" || status === "partially_succeeded") return "status-failed";
  if (status === "planned") return "status-queued";
  return "status-running";
}

async function submitWorkflowGroundTruth(workflow, file, button) {
  if (!file) return;
  button.disabled = true;
  button.textContent = "正在评测…";
  const form = new FormData();
  form.append("ground_truth", file);
  form.append("positive_threshold", "127");
  try {
    const updated = await api(`/api/v1/workflows/${encodeURIComponent(workflow.id)}/evaluations`, {
      method: "POST",
      body: form,
      headers: {},
    });
    showToast(`工作流 ${updated.id.slice(0, 8)} 已完成同真值评测`);
    await refreshWorkflows();
    await refreshEvaluations();
  } catch (error) {
    showToast(`工作流评测失败：${error.message}`, true);
    button.disabled = false;
    button.textContent = "绑定并评测";
  }
}

function renderWorkflowCatalog() {
  elements.workflowCountBadge.textContent = `${state.workflows.length} workflows`;
  elements.workflowCatalog.replaceChildren();
  if (!state.workflows.length) {
    elements.workflowCatalog.innerHTML = '<p class="muted">暂无编排记录。选择固定数据版本后创建计划。</p>';
    return;
  }
  state.workflows.forEach((workflow) => {
    const article = document.createElement("article");
    article.className = "catalog-item workflow-item";
    const steps = workflow.steps.map((step) => `
      <li class="workflow-step is-${escapeHtml(step.status)}"><i></i><span><strong>${escapeHtml(step.label)}</strong><small>${escapeHtml(step.model_id || step.error || step.status)}</small></span></li>`).join("");
    const ranking = workflow.summary?.ranking || [];
    const parameterSummary = Object.entries(workflow.model_parameters || {})
      .flatMap(([modelId, values]) => Object.entries(values).map(
        ([key, value]) => `${modelId}: ${key}=${value}`,
      ))
      .join(" · ");
    article.innerHTML = `
      <div class="catalog-item-head"><div><strong>${escapeHtml(workflow.name)}</strong><code>${escapeHtml(workflow.id.slice(0, 12))}</code></div><span class="status-pill ${workflowStatusClass(workflow.status)}">${escapeHtml(workflowStatusLabels[workflow.status] || workflow.status)}</span></div>
      <p>${escapeHtml(taskLabels[workflow.task])} · ${escapeHtml(workflow.dataset_version)} · ${workflow.model_ids.length} models</p>
      ${parameterSummary ? `<small class="workflow-parameter-summary">${escapeHtml(parameterSummary)}</small>` : ""}
      <ol class="workflow-steps">${steps}</ol>
      ${ranking.length ? `<div class="workflow-ranking"><strong>同真值排名</strong>${ranking.map((item) => `<span>#${item.rank} ${escapeHtml(item.model_id)} · F1 ${item.f1 ?? "N/A"} · IoU ${item.iou ?? "N/A"}</span>`).join("")}</div>` : ""}`;
    const actions = document.createElement("div");
    actions.className = "catalog-actions";
    if (workflow.job_ids.length) {
      const view = document.createElement("button");
      view.type = "button";
      view.className = "button button-quiet";
      view.textContent = "查看首个作业";
      view.addEventListener("click", async () => {
        state.currentJob = await api(`/api/v1/jobs/${encodeURIComponent(workflow.job_ids[0])}`);
        await showModule("workbench");
        if (state.currentJob.status === "succeeded") renderJob(state.currentJob);
      });
      actions.append(view);
    }
    if (workflow.status === "awaiting_ground_truth") {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = "image/png,image/jpeg";
      input.setAttribute("aria-label", `为工作流 ${workflow.id.slice(0, 8)} 选择真值`);
      const evaluate = document.createElement("button");
      evaluate.type = "button";
      evaluate.className = "button button-primary";
      evaluate.textContent = "绑定并评测";
      evaluate.disabled = true;
      input.addEventListener("change", () => { evaluate.disabled = !input.files[0]; });
      evaluate.addEventListener("click", () => submitWorkflowGroundTruth(workflow, input.files[0], evaluate));
      actions.append(input, evaluate);
    }
    article.append(actions);
    elements.workflowCatalog.append(article);
  });
}

async function refreshWorkflows() {
  try {
    state.workflows = await api("/api/v1/workflows?limit=100");
    renderWorkflowCatalog();
  } catch (error) {
    showToast(`编排记录读取失败：${error.message}`, true);
  }
}

async function waitForWorkflow(workflowId) {
  for (let attempt = 0; attempt < 900; attempt += 1) {
    const workflow = await api(`/api/v1/workflows/${encodeURIComponent(workflowId)}`);
    if (!["queued", "running"].includes(workflow.status)) return workflow;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("工作流等待超时，请在编排中心查看后台状态");
}

async function submitWorkflow(event) {
  event.preventDefault();
  const modelIds = [...elements.workflowModels.selectedOptions]
    .filter((option) => !option.disabled)
    .map((option) => option.value);
  const modelParameters = {};
  elements.workflowParameters.querySelectorAll("input[data-model-id]").forEach((input) => {
    modelParameters[input.dataset.modelId] ||= {};
    modelParameters[input.dataset.modelId][input.dataset.parameterKey] = Number(input.value);
  });
  elements.runWorkflow.disabled = true;
  elements.runWorkflow.textContent = "正在执行…";
  try {
    const plan = await api("/api/v1/workflows", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: elements.workflowName.value,
        dataset_id: elements.workflowDataset.value,
        task: elements.workflowTask.value,
        model_ids: modelIds,
        model_parameters: modelParameters,
      }),
    });
    await api(`/api/v1/workflows/${encodeURIComponent(plan.id)}/execute`, {method: "POST"});
    const completed = await waitForWorkflow(plan.id);
    showToast(`${completed.name}：${workflowStatusLabels[completed.status] || completed.status}`);
    await refreshWorkflows();
    await refreshRecentJobs();
  } catch (error) {
    showToast(`编排失败：${error.message}`, true);
  } finally {
    elements.runWorkflow.disabled = false;
    elements.runWorkflow.textContent = "创建并执行";
  }
}

async function submitDataset(event) {
  event.preventDefault();
  const isFolder = elements.datasetUploadMode.value === "folder";
  elements.registerDataset.disabled = true;
  elements.registerDataset.textContent = isFolder ? "正在上传并校验…" : "正在校验…";
  const formData = new FormData(elements.datasetForm);
  if (!formData.get("task_hint")) formData.delete("task_hint");
  let endpoint = "/api/v1/datasets";
  if (isFolder) {
    endpoint = "/api/v1/datasets/folder";
    formData.delete("primary");
    formData.delete("secondary");
    const images = folderImageFiles();
    if (!images.length) {
      showToast("请选择至少包含一张 PNG 或 JPEG 影像的文件夹", true);
      elements.registerDataset.disabled = false;
      elements.registerDataset.textContent = "校验并登记";
      return;
    }
    images.forEach((file) => {
      formData.append("files", file, file.webkitRelativePath || file.name);
    });
  } else if (!formData.get("secondary")?.size) {
    formData.delete("secondary");
  }
  try {
    const dataset = await api(endpoint, { method: "POST", body: formData, headers: {} });
    elements.datasetForm.reset();
    syncDatasetUploadMode();
    const sampleCopy = dataset.layout === "folder" ? `，共 ${dataset.sample_count} 张影像` : "";
    showToast(`数据集 ${dataset.name} 已登记为 ${dataset.version}${sampleCopy}`);
    await refreshDatasets();
  } catch (error) {
    showToast(`登记失败：${error.message}`, true);
  } finally {
    elements.registerDataset.disabled = false;
    elements.registerDataset.textContent = "校验并登记";
  }
}

function folderImageFiles() {
  return [...(elements.datasetFolder.files || [])].filter((file) => (
    ["image/png", "image/jpeg"].includes(file.type)
    || /\.(png|jpe?g)$/i.test(file.name)
  ));
}

function renderDatasetFolderSummary() {
  const selected = [...(elements.datasetFolder.files || [])];
  const images = folderImageFiles();
  if (!selected.length) {
    elements.datasetFolderSummary.textContent = "请选择包含 PNG / JPEG 影像的文件夹。";
    return;
  }
  const totalBytes = images.reduce((sum, file) => sum + file.size, 0);
  const ignored = selected.length - images.length;
  elements.datasetFolderSummary.textContent = [
    `${images.length} 张影像`,
    formatBytes(totalBytes),
    ignored ? `${ignored} 个非影像文件不会上传` : "目录结构将被保留",
  ].join(" · ");
}

function syncDatasetUploadMode() {
  const isFolder = elements.datasetUploadMode.value === "folder";
  elements.datasetSceneInputs.hidden = isFolder;
  elements.datasetFolderInputs.hidden = !isFolder;
  const primary = elements.datasetSceneInputs.querySelector('input[name="primary"]');
  primary.required = !isFolder;
  elements.datasetFolder.required = isFolder;
  renderDatasetFolderSummary();
}

async function runRegisteredDataset(dataset, select, button) {
  const option = select.selectedOptions[0];
  if (!option) return;
  button.disabled = true;
  button.textContent = "正在创建…";
  try {
    const spec = thresholdSpec(option.value);
    const request = { task: option.dataset.task, model_id: option.value };
    if (spec) request.threshold = spec.default;
    const job = await api(`/api/v1/datasets/${encodeURIComponent(dataset.id)}/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    state.currentJob = job;
    elements.caseTitle.textContent = dataset.name;
    elements.caseSubtitle.textContent = `${dataset.version} · ${taskLabels[job.task]}`;
    elements.taskContext.textContent = taskLabels[job.task];
    elements.dataContext.textContent = dataset.version;
    renderModelCard(job.model_id);
    await showModule("workbench");
    setRunning(true, "正在运行已登记数据版本");
    await waitForJob(job.id);
  } catch (error) {
    handleRunError(error);
  } finally {
    button.disabled = false;
    button.textContent = "从此版本运行";
  }
}

function populateModelFilters() {
  elements.jobModelFilter.innerHTML = '<option value="">全部模型</option>';
  state.models.forEach((model) => {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = model.name;
    elements.jobModelFilter.append(option);
  });
}

function jobSource(job) {
  const source = job.inputs?.[0]?.source || "unknown";
  if (source.startsWith("dataset:")) return source.split("@")[0].replace("dataset:", "dataset ").slice(0, 20);
  if (source.startsWith("bundled-demo:")) return source.replace("bundled-demo:", "demo · ");
  return source;
}

function renderJobCatalog() {
  elements.jobCatalog.replaceChildren();
  if (!state.jobs.length) {
    elements.jobCatalog.innerHTML = '<tr><td colspan="6" class="muted">当前筛选下暂无运行记录</td></tr>';
    return;
  }
  state.jobs.forEach((job) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><code>${escapeHtml(job.id.slice(0, 12))}</code></td>
      <td><strong>${escapeHtml(taskLabels[job.task] || job.task)}</strong><small>${escapeHtml(job.model_id)}</small></td>
      <td>${escapeHtml(jobSource(job))}</td>
      <td><span class="status-pill status-${escapeHtml(job.status)}">${escapeHtml(statusLabels[job.status] || job.status)}</span></td>
      <td><time datetime="${escapeHtml(job.created_at)}">${formatDate(job.created_at)}</time></td>`;
    const actions = document.createElement("td");
    const view = document.createElement("button");
    view.className = "text-button";
    view.type = "button";
    view.textContent = "查看";
    view.addEventListener("click", async () => {
      state.currentJob = await api(`/api/v1/jobs/${encodeURIComponent(job.id)}`);
      await showModule("workbench");
      if (state.currentJob.status === "succeeded") renderJob(state.currentJob);
      else updateJobStatus(state.currentJob);
    });
    actions.append(view);
    row.append(actions);
    elements.jobCatalog.append(row);
  });
}

async function refreshJobCatalog() {
  const params = new URLSearchParams({ limit: "100" });
  if (elements.jobStatusFilter.value) params.set("status", elements.jobStatusFilter.value);
  if (elements.jobTaskFilter.value) params.set("task", elements.jobTaskFilter.value);
  if (elements.jobModelFilter.value) params.set("model_id", elements.jobModelFilter.value);
  try {
    state.jobs = await api(`/api/v1/jobs?${params}`);
    renderJobCatalog();
  } catch (error) {
    showToast(`作业列表读取失败：${error.message}`, true);
  }
}

function renderModelCatalog() {
  elements.modelCountBadge.textContent = `${state.models.length} models`;
  elements.modelCatalog.replaceChildren();
  const taskOrder = ["change_detection", "land_cover", "object_detection", "road_extraction"];
  taskOrder.forEach((task, index) => {
    const models = modelOptionsForTask(task);
    if (!models.length) return;
    const readyCount = models.filter((model) => model.runtime_status?.ready).length;
    const group = document.createElement("section");
    group.className = "model-group";
    group.dataset.task = task;
    group.setAttribute("aria-labelledby", `modelGroupTitle${index}`);
    const heading = document.createElement("div");
    heading.className = "model-group-heading";
    heading.innerHTML = `
      <div><span class="section-kicker">TASK ${String(index + 1).padStart(2, "0")}</span><h3 id="modelGroupTitle${index}">${escapeHtml(modelCategoryLabels[task] || taskLabels[task] || task)}</h3></div>
      <span>${models.length} 个模型 · ${readyCount} 个可运行</span>`;
    const grid = document.createElement("div");
    grid.className = "model-group-grid";
    models.forEach((model) => {
      const card = document.createElement("article");
      card.className = "panel model-card-full";
      const runtime = model.runtime_status || {};
      const runtimeLabel = runtime.ready
        ? `${model.is_default ? "当前默认 · " : ""}可运行 · ${runtime.device}`
        : "运行时未就绪";
      const runtimeClass = runtime.ready ? "status-running" : "status-failed";
      const parameterDescription = model.inference_parameters.length
        ? model.inference_parameters.map((item) => `${item.label}（默认 ${item.default}）：${item.description}`).join("；")
        : "固定推理配置，无需设置通用阈值。";
      card.innerHTML = `
        <div class="catalog-item-head"><div><span class="section-kicker">${escapeHtml(model.family)}</span><h2>${escapeHtml(model.name)}</h2></div><span class="status-pill ${runtimeClass}">${escapeHtml(runtimeLabel)}</span></div>
        <code>${escapeHtml(model.id)} · v${escapeHtml(model.version)}</code>
        <p>${escapeHtml(model.description)}</p>
        <dl><div><dt>输入</dt><dd>${escapeHtml(model.expected_inputs.join("；"))}</dd></div><div><dt>阶段</dt><dd>${escapeHtml(model.stage)}</dd></div><div><dt>许可</dt><dd>${escapeHtml(model.license || "—")}</dd></div></dl>
        <div class="model-card-columns"><div><strong>优势</strong><ul>${model.strengths.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div><div><strong>局限</strong><ul>${model.limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div></div>
        <div class="metric-scope"><strong>推理参数</strong><span>${escapeHtml(parameterDescription)}</span></div>
        ${runtime.reason ? `<div class="metric-scope"><strong>运行状态</strong><span>${escapeHtml(runtime.reason)} ${escapeHtml(runtime.setup_hint || "")}</span></div>` : ""}
        <div class="metric-scope"><strong>指标边界</strong><span>${escapeHtml(model.metric_scope)}</span></div>`;
      grid.append(card);
    });
    group.append(heading, grid);
    elements.modelCatalog.append(group);
  });
}

function renderEvaluationDetail(report) {
  const metricValue = (value) => value === null || value === undefined ? "N/A" : Number(value).toFixed(4);
  elements.evaluationDetail.innerHTML = `
    <span class="section-kicker">SELECTED REPORT</span>
    <div class="catalog-item-head"><h2>${escapeHtml(report.task === "change_detection" ? "变化检测评测" : "道路提取评测")}</h2><code>${escapeHtml(report.id.slice(0, 12))}</code></div>
    <div class="evaluation-metrics">${Object.entries(report.metrics).map(([key, value]) => `<article><span>${escapeHtml(key.toUpperCase())}</span><strong>${metricValue(value)}</strong></article>`).join("")}</div>
    <dl class="report-ledger">
      <div><dt>混淆矩阵</dt><dd>TP ${report.confusion.tp.toLocaleString()} · FP ${report.confusion.fp.toLocaleString()} · FN ${report.confusion.fn.toLocaleString()} · TN ${report.confusion.tn.toLocaleString()}</dd></div>
      <div><dt>预测 SHA-256</dt><dd><code title="${escapeHtml(report.prediction_sha256)}">${escapeHtml(report.prediction_sha256.slice(0, 20))}…</code></dd></div>
      <div><dt>真值 SHA-256</dt><dd><code title="${escapeHtml(report.ground_truth_sha256)}">${escapeHtml(report.ground_truth_sha256.slice(0, 20))}…</code></dd></div>
      <div><dt>指标套件</dt><dd>${escapeHtml(report.metric_suite)} · threshold ${report.positive_threshold}</dd></div>
    </dl>
    <p class="metric-scope">${escapeHtml(report.claim_scope)}</p>`;
}

function renderEvaluationList() {
  elements.evaluationList.replaceChildren();
  if (!state.evaluations.length) {
    elements.evaluationList.innerHTML = '<p class="muted">暂无评测报告。先运行变化检测或道路提取，再上传同尺寸真值掩膜。</p>';
    return;
  }
  state.evaluations.forEach((report) => {
    const button = document.createElement("button");
    button.className = "evaluation-item";
    button.type = "button";
    const iou = report.metrics.iou === null ? "N/A" : Number(report.metrics.iou).toFixed(3);
    const f1 = report.metrics.f1 === null ? "N/A" : Number(report.metrics.f1).toFixed(3);
    button.innerHTML = `<span><strong>${escapeHtml(taskLabels[report.task])}</strong><small>run ${escapeHtml(report.job_id.slice(0, 10))} · ${formatDate(report.created_at)}</small></span><span><b>IoU ${iou}</b><small>F1 ${f1}</small></span>`;
    button.addEventListener("click", () => renderEvaluationDetail(report));
    elements.evaluationList.append(button);
  });
}

async function refreshEvaluations() {
  try {
    const [reports, jobs] = await Promise.all([
      api("/api/v1/evaluations?limit=100"),
      api("/api/v1/jobs?status=succeeded&limit=100"),
    ]);
    state.evaluations = reports;
    const eligible = jobs.filter((job) => ["change_detection", "road_extraction"].includes(job.task));
    elements.evaluationJob.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = eligible.length ? "请选择成功作业" : "暂无可评测作业";
    elements.evaluationJob.append(placeholder);
    eligible.forEach((job) => {
      const option = document.createElement("option");
      option.value = job.id;
      option.textContent = `${job.id.slice(0, 10)} · ${taskLabels[job.task]} · ${job.model_id}`;
      elements.evaluationJob.append(option);
    });
    renderEvaluationList();
    if (reports[0]) renderEvaluationDetail(reports[0]);
  } catch (error) {
    showToast(`评测记录读取失败：${error.message}`, true);
  }
}

async function submitEvaluation(event) {
  event.preventDefault();
  elements.createEvaluation.disabled = true;
  elements.createEvaluation.textContent = "正在计算…";
  try {
    const report = await api("/api/v1/evaluations", {
      method: "POST",
      body: new FormData(elements.evaluationForm),
      headers: {},
    });
    const iou = report.metrics.iou === null ? "N/A" : report.metrics.iou.toFixed(4);
    showToast(`评测报告 ${report.id.slice(0, 8)} 已保存，IoU ${iou}`);
    elements.evaluationForm.reset();
    await refreshEvaluations();
    renderEvaluationDetail(report);
  } catch (error) {
    showToast(`评测失败：${error.message}`, true);
  } finally {
    elements.createEvaluation.disabled = false;
    elements.createEvaluation.textContent = "计算并保存";
  }
}

function renderAgentWelcome() {
  elements.agentMessages.replaceChildren();
  appendAgentMessage(
    "assistant",
    "可以查询数据版本、模型卡、工作流、评测和复核候选。首轮回复成功后，这段对话会保存在本地项目 artifact 目录。",
  );
}

function renderAgentConversation(conversation) {
  elements.agentConversationTitle.textContent = conversation.title;
  elements.agentMemoryStatus.textContent = conversation.messages.length
    ? `最近 ${Math.min(conversation.messages.length, 16)} 条消息参与上下文`
    : "新对话尚无历史";
  elements.agentMessages.replaceChildren();
  if (!conversation.messages.length) {
    renderAgentWelcome();
    return;
  }
  conversation.messages.forEach((message) => {
    const tools = [
      ...message.executed_tools,
      ...message.cancelled_tools.map((name) => `${name} · 已拦截`),
    ];
    appendAgentMessage(message.role, message.content, tools);
  });
}

function startNewAgentConversation() {
  state.currentAgentConversationId = null;
  elements.agentConversationTitle.textContent = "新对话";
  elements.agentMemoryStatus.textContent = "首轮回复后自动保存";
  renderAgentWelcome();
  renderAgentHistory();
  elements.agentInput.focus();
}

async function loadAgentConversation(conversationId) {
  const conversation = await api(
    `/api/v1/agent/conversations/${encodeURIComponent(conversationId)}`,
  );
  state.currentAgentConversationId = conversation.id;
  renderAgentConversation(conversation);
  renderAgentHistory();
}

async function archiveAgentConversation(conversationId) {
  await api(`/api/v1/agent/conversations/${encodeURIComponent(conversationId)}`, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({archived: true}),
  });
  if (state.currentAgentConversationId === conversationId) startNewAgentConversation();
  await refreshAgentConversations(false);
  showToast("对话已归档");
}

function renderAgentHistory() {
  elements.agentHistoryList.replaceChildren();
  if (!state.agentConversations.length) {
    elements.agentHistoryList.innerHTML = '<p class="muted">暂无历史对话</p>';
    return;
  }
  state.agentConversations.forEach((conversation) => {
    const item = document.createElement("article");
    item.className = "agent-history-item";
    item.classList.toggle("is-active", conversation.id === state.currentAgentConversationId);
    const open = document.createElement("button");
    open.type = "button";
    open.className = "agent-history-open";
    const title = document.createElement("strong");
    title.textContent = conversation.title;
    const meta = document.createElement("small");
    meta.textContent = `${conversation.message_count} 条 · ${formatDate(conversation.updated_at)}`;
    open.append(title, meta);
    open.addEventListener("click", () => loadAgentConversation(conversation.id));
    const archive = document.createElement("button");
    archive.type = "button";
    archive.className = "agent-history-archive";
    archive.setAttribute("aria-label", `归档对话 ${conversation.title}`);
    archive.title = "归档";
    archive.textContent = "×";
    archive.addEventListener("click", () => archiveAgentConversation(conversation.id));
    item.append(open, archive);
    elements.agentHistoryList.append(item);
  });
}

async function refreshAgentConversations(loadLatest = true) {
  try {
    state.agentConversations = await api("/api/v1/agent/conversations?limit=50");
    renderAgentHistory();
    const currentExists = state.agentConversations.some(
      (item) => item.id === state.currentAgentConversationId,
    );
    if (state.currentAgentConversationId && !currentExists) startNewAgentConversation();
    if (loadLatest && !state.currentAgentConversationId && state.agentConversations[0]) {
      await loadAgentConversation(state.agentConversations[0].id);
    }
  } catch (error) {
    showToast(`历史对话读取失败：${error.message}`, true);
  }
}

function appendAgentMessage(role, text, tools = []) {
  const article = document.createElement("article");
  article.className = `agent-message ${role}`;
  const heading = document.createElement("strong");
  heading.textContent = role === "user" ? "你" : "TerraInterpret Copilot";
  const content = document.createElement("p");
  content.textContent = text;
  article.append(heading, content);
  if (tools.length) {
    const toolRow = document.createElement("div");
    toolRow.className = "agent-tools";
    tools.forEach((toolName) => {
      const badge = document.createElement("code");
      badge.textContent = toolName;
      toolRow.append(badge);
    });
    article.append(toolRow);
  }
  elements.agentMessages.append(article);
  elements.agentMessages.scrollTop = elements.agentMessages.scrollHeight;
}

function renderAgentStatus(status) {
  state.agentStatus = status;
  elements.agentStatus.classList.toggle("is-ready", status.ready);
  elements.agentStatus.classList.toggle("is-unavailable", !status.ready);
  const provider = status.model ? `${status.provider} · ${status.model}` : status.provider;
  elements.agentStatus.querySelector("span").textContent = status.ready
    ? `GeoAgent ${status.package_version || ""} 已安装 · ${provider} · 首次请求校验模型连接`
    : status.setup_hint || "GeoAgent 当前不可用";
  elements.agentInput.disabled = !status.ready;
  elements.sendAgentMessage.disabled = !status.ready;
}

async function refreshAgentStatus() {
  try {
    renderAgentStatus(await api("/api/v1/agent/status"));
  } catch (error) {
    renderAgentStatus({
      ready: false,
      setup_hint: error instanceof Error ? error.message : "无法读取 GeoAgent 状态",
    });
  }
}

async function submitAgentMessage(event) {
  event.preventDefault();
  if (state.agentBusy || !state.agentStatus?.ready) return;
  const message = elements.agentInput.value.trim();
  if (!message) return;
  const allowActions = elements.agentAllowActions.checked;
  appendAgentMessage("user", message);
  elements.agentInput.value = "";
  state.agentBusy = true;
  elements.sendAgentMessage.disabled = true;
  elements.sendAgentMessage.textContent = "思考中…";
  try {
    const result = await api("/api/v1/agent/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        conversation_id: state.currentAgentConversationId,
        allow_actions: allowActions,
        current_job_id: state.currentJob?.id || null,
      }),
    });
    const tools = [...result.executed_tools, ...result.cancelled_tools.map((name) => `${name} · 已拦截`)];
    appendAgentMessage("assistant", result.answer || "请求已完成。", tools);
    state.currentAgentConversationId = result.conversation_id;
    await refreshAgentConversations(false);
    await loadAgentConversation(result.conversation_id);
    if (allowActions && result.executed_tools.includes("run_demo_interpretation")) {
      await refreshRecentJobs();
    }
    if (allowActions && result.executed_tools.includes("run_dataset_workflow")) {
      await refreshWorkflows();
      await refreshRecentJobs();
    }
  } catch (error) {
    appendAgentMessage(
      "assistant",
      error instanceof Error ? error.message : "GeoAgent 请求失败",
    );
  } finally {
    state.agentBusy = false;
    elements.agentAllowActions.checked = false;
    elements.sendAgentMessage.disabled = !state.agentStatus?.ready;
    elements.sendAgentMessage.textContent = "发送";
    elements.agentInput.focus();
  }
}

function bindEvents() {
  let compareDragging = false;
  const openExperimentDialog = () => {
    updateModelOptions();
    elements.experimentDialog.showModal();
  };
  elements.thresholdInput.addEventListener("input", () => {
    elements.thresholdOutput.textContent = Number(elements.thresholdInput.value).toFixed(2);
  });
  elements.runButton.addEventListener("click", runCurrentScenario);
  elements.compareSlider.addEventListener("input", () => updateCompare(elements.compareSlider.value));
  elements.mapStage.addEventListener("pointerdown", (event) => {
    if (state.currentMode !== "compare" || event.button !== 0) return;
    compareDragging = true;
    elements.mapStage.setPointerCapture?.(event.pointerId);
    elements.compareSlider.focus({ preventScroll: true });
    updateCompareFromPointer(event);
    event.preventDefault();
  }, true);
  elements.mapStage.addEventListener("pointermove", (event) => {
    if (compareDragging) updateCompareFromPointer(event);
  });
  const finishCompareDrag = (event) => {
    if (!compareDragging) return;
    updateCompareFromPointer(event);
    compareDragging = false;
    if (elements.mapStage.hasPointerCapture?.(event.pointerId)) {
      elements.mapStage.releasePointerCapture(event.pointerId);
    }
  };
  elements.mapStage.addEventListener("pointerup", finishCompareDrag);
  elements.mapStage.addEventListener("pointercancel", () => {
    compareDragging = false;
  });
  elements.overlayOpacity.addEventListener("input", () => {
    const opacity = String(Number(elements.overlayOpacity.value) / 100);
    elements.overlayImage.style.opacity = opacity;
    elements.singleLayerImage.style.opacity = opacity;
  });
  document.querySelectorAll("[data-view-mode]").forEach((button) => {
    button.addEventListener("click", () => setViewMode(button.dataset.viewMode));
  });
  elements.mapStage.addEventListener("pointermove", (event) => {
    const rect = elements.mapStage.getBoundingClientRect();
    const width = Number(state.currentJob?.metrics?.width_px || rect.width);
    const height = Number(state.currentJob?.metrics?.height_px || rect.height);
    const x = Math.max(0, Math.min(width, ((event.clientX - rect.left) / rect.width) * width));
    const y = Math.max(0, Math.min(height, ((event.clientY - rect.top) / rect.height) * height));
    elements.pointerCoordinates.textContent = `x ${Math.round(x)} · y ${Math.round(y)}`;
  });
  elements.copyRunId.addEventListener("click", async () => {
    if (!state.currentJob) return;
    await navigator.clipboard.writeText(state.currentJob.id);
    showToast("Run ID 已复制");
  });
  document.querySelector("#inspectUncertainty").addEventListener("click", () => setViewMode("uncertainty"));
  elements.acceptReview.addEventListener("click", () => submitReviewDecision("accept"));
  elements.rejectReview.addEventListener("click", () => submitReviewDecision("reject"));
  elements.runAdaptation.addEventListener("click", runAdaptationRound);
  document.querySelector("#refreshJobs").addEventListener("click", refreshRecentJobs);
  document.querySelector("#newExperimentButton").addEventListener("click", openExperimentDialog);
  document.querySelector("#jobsNewExperiment").addEventListener("click", openExperimentDialog);
  document.querySelector("#closeDialog").addEventListener("click", () => elements.experimentDialog.close());
  document.querySelector("#cancelDialog").addEventListener("click", () => elements.experimentDialog.close());
  elements.taskSelect.addEventListener("change", updateModelOptions);
  elements.modelSelect.addEventListener("change", updateDialogParameter);
  elements.dialogThreshold.addEventListener("input", () => {
    elements.dialogThresholdOutput.textContent = Number(elements.dialogThreshold.value).toFixed(2);
  });
  elements.primaryFile.addEventListener("change", () => {
    elements.primaryFileName.textContent = elements.primaryFile.files[0]?.name || "PNG 或 JPEG，最大 32 MB";
  });
  elements.secondaryFile.addEventListener("change", () => {
    elements.secondaryFileName.textContent = elements.secondaryFile.files[0]?.name || "变化检测必填";
  });
  elements.experimentForm.addEventListener("submit", submitUpload);
  elements.datasetForm.addEventListener("submit", submitDataset);
  elements.datasetUploadMode.addEventListener("change", syncDatasetUploadMode);
  elements.datasetFolder.addEventListener("change", renderDatasetFolderSummary);
  elements.workflowForm.addEventListener("submit", submitWorkflow);
  elements.workflowDataset.addEventListener("change", syncWorkflowDatasetTask);
  elements.workflowTask.addEventListener("change", updateWorkflowModelOptions);
  elements.workflowModels.addEventListener("change", renderWorkflowParameters);
  document.querySelector("#refreshWorkflows").addEventListener("click", refreshWorkflows);
  document.querySelector("#refreshDatasets").addEventListener("click", refreshDatasets);
  document.querySelector("#refreshJobCatalog").addEventListener("click", refreshJobCatalog);
  [elements.jobStatusFilter, elements.jobTaskFilter, elements.jobModelFilter].forEach((filter) => {
    filter.addEventListener("change", refreshJobCatalog);
  });
  elements.evaluationForm.addEventListener("submit", submitEvaluation);
  document.querySelector("#refreshEvaluations").addEventListener("click", refreshEvaluations);
  elements.openAgentButton.addEventListener("click", async () => {
    elements.agentDialog.showModal();
    await Promise.all([refreshAgentStatus(), refreshAgentConversations()]);
    if (state.agentStatus?.ready) elements.agentInput.focus();
  });
  elements.newAgentConversation.addEventListener("click", startNewAgentConversation);
  elements.closeAgent.addEventListener("click", () => elements.agentDialog.close());
  elements.agentForm.addEventListener("submit", submitAgentMessage);
  elements.agentInput.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      elements.agentForm.requestSubmit();
    }
  });
  document.querySelector("#openDocsButton").addEventListener("click", () => window.open("/docs", "_blank", "noopener"));
  document.querySelector("#aboutButton").addEventListener("click", () => elements.aboutDialog.showModal());
  document.querySelector("#closeAbout").addEventListener("click", () => elements.aboutDialog.close());
  document.querySelectorAll("[data-nav]").forEach((button) => {
    button.addEventListener("click", () => showModule(button.dataset.nav));
  });
}

async function bootstrap() {
  bindEvents();
  updateCompare(elements.compareSlider.value);
  try {
    const [health, modelsPayload, scenarios] = await Promise.all([
      api("/api/v1/health"),
      api("/api/v1/models"),
      api("/api/v1/scenarios"),
    ]);
    setHealth(health);
    state.models = modelsPayload.items;
    state.scenarios = scenarios;
    state.currentScenario = scenarios[0] || null;
    populateModelFilters();
    updateWorkflowModelOptions();
    renderModelCatalog();
    renderScenarios();
    updateModelOptions();
    if (state.currentScenario) {
      selectScenario(state.currentScenario);
      if (health.demo_archive) await bootstrapScenarioExamples();
    }
    await refreshRecentJobs();
  } catch (error) {
    setOffline("引擎连接失败");
    elements.scenarioList.innerHTML = '<p class="muted">无法读取研究场景，请检查服务日志。</p>';
    elements.mapStage.classList.remove("is-loading");
    elements.emptyState.hidden = false;
    showToast(error instanceof Error ? error.message : "应用初始化失败", true);
  }
}

bootstrap();
