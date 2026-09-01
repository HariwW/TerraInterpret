const state = {
  health: null,
  models: [],
  scenarios: [],
  currentScenario: null,
  currentJob: null,
  currentReview: null,
  currentMode: "compare",
  isRunning: false,
  toastTimer: null,
};

const elements = {
  systemHealth: document.querySelector("#systemHealth"),
  scenarioList: document.querySelector("#scenarioList"),
  scenarioCount: document.querySelector("#scenarioCount"),
  caseTitle: document.querySelector("#caseTitle"),
  caseSubtitle: document.querySelector("#caseSubtitle"),
  taskContext: document.querySelector("#taskContext"),
  dataContext: document.querySelector("#dataContext"),
  thresholdInput: document.querySelector("#thresholdInput"),
  thresholdOutput: document.querySelector("#thresholdOutput"),
  runButton: document.querySelector("#runButton"),
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
  dialogThreshold: document.querySelector("#dialogThreshold"),
  dialogThresholdOutput: document.querySelector("#dialogThresholdOutput"),
  submitExperiment: document.querySelector("#submitExperiment"),
  aboutDialog: document.querySelector("#aboutDialog"),
  toast: document.querySelector("#toast"),
};

const taskLabels = {
  change_detection: "Change detection",
  land_cover: "Land-cover mapping",
  object_detection: "Object proposals",
  road_extraction: "Road extraction",
};

const statusLabels = {
  queued: "等待调度",
  running: "正在运行",
  succeeded: "运行成功",
  failed: "运行失败",
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
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>`;
    button.addEventListener("click", () => selectScenario(scenario));
    elements.scenarioList.append(button);
  });
  syncScenarioSelection();
}

function syncScenarioSelection() {
  document.querySelectorAll(".scenario-card").forEach((card) => {
    const active = card.dataset.scenarioId === state.currentScenario?.id;
    card.classList.toggle("is-active", active);
    card.setAttribute("aria-pressed", String(active));
  });
}

function selectScenario(scenario) {
  state.currentScenario = scenario;
  state.currentJob = null;
  elements.caseTitle.textContent = scenario.title;
  elements.caseSubtitle.textContent = scenario.subtitle;
  elements.taskContext.textContent = taskLabels[scenario.task] || scenario.task;
  elements.dataContext.textContent = scenario.id === "urban-change" ? "WHU change pair" : "Bundled RGB demo";
  syncScenarioSelection();
  renderModelCard(scenario.model_id);
  resetObservation();
  elements.baseImage.src = `/api/v1/demo-assets/${scenario.primary_asset}`;
  elements.overlayImage.removeAttribute("src");
  elements.singleLayerImage.removeAttribute("src");
  elements.mapStage.classList.remove("is-loading");
  elements.emptyState.hidden = false;
  setViewMode("compare");
}

function renderModelCard(modelId) {
  const card = state.models.find((item) => item.id === modelId);
  if (!card) return;
  elements.modelName.textContent = card.name;
  elements.modelDescription.textContent = card.description;
  elements.modelStage.textContent = card.stage;
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
  elements.runButton.disabled = running;
  elements.submitExperiment.disabled = running;
  elements.mapStage.classList.toggle("is-loading", running);
  elements.stageLoader.querySelector("strong").textContent = label;
  if (running) {
    elements.emptyState.hidden = true;
    elements.timelineRun.classList.add("is-complete");
  }
}

async function runCurrentScenario() {
  if (!state.currentScenario || state.isRunning) return;
  resetObservation();
  setRunning(true);
  elements.jobStatus.className = "status-pill status-running";
  elements.jobStatus.textContent = "正在运行";
  const threshold = Number(elements.thresholdInput.value);
  try {
    const manifest = await api(
      `/api/v1/demo-runs/${encodeURIComponent(state.currentScenario.id)}?threshold=${threshold}`,
      { method: "POST" },
    );
    state.currentJob = manifest;
    elements.runId.textContent = manifest.id;
    elements.copyRunId.disabled = false;
    await waitForJob(manifest.id);
  } catch (error) {
    handleRunError(error);
  }
}

async function waitForJob(jobId) {
  const started = Date.now();
  while (Date.now() - started < 60000) {
    const job = await api(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
    state.currentJob = job;
    updateJobStatus(job);
    if (job.status === "succeeded") {
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

function handleRunError(error) {
  setRunning(false);
  elements.emptyState.hidden = false;
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

function renderJob(job) {
  updateJobStatus(job);
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
  showToast(`实验 ${job.id.slice(0, 8)} 已完成，全部产物已登记`);
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
  const threshold = provenance.parameters?.threshold ?? "—";
  elements.provenanceStatus.textContent = "✓ manifest 已登记";
  elements.provenanceStatus.classList.add("is-verified");
  elements.provenanceGrid.innerHTML = `
    <div><dt>输入 SHA-256</dt><dd title="${escapeHtml(provenance.input_sha256?.[0] || "")}">${escapeHtml(inputDigest)}…</dd></div>
    <div><dt>引擎版本</dt><dd>${escapeHtml(`${provenance.engine || "—"}@${provenance.engine_version || "—"}`)}</dd></div>
    <div><dt>模型版本</dt><dd>${escapeHtml(job.model_id)}</dd></div>
    <div><dt>参数</dt><dd>threshold=${escapeHtml(threshold)}</dd></div>`;
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
  const options = state.models.filter((model) => model.task === task);
  elements.modelSelect.replaceChildren();
  options.forEach((model) => {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = `${model.name} · ${model.stage}`;
    elements.modelSelect.append(option);
  });
  const needsSecond = task === "change_detection";
  elements.secondaryDropZone.classList.toggle("is-hidden", !needsSecond);
  elements.secondaryFile.required = needsSecond;
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

function bindEvents() {
  let compareDragging = false;
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
  document.querySelector("#newExperimentButton").addEventListener("click", () => {
    updateModelOptions();
    elements.experimentDialog.showModal();
  });
  document.querySelector("#closeDialog").addEventListener("click", () => elements.experimentDialog.close());
  document.querySelector("#cancelDialog").addEventListener("click", () => elements.experimentDialog.close());
  elements.taskSelect.addEventListener("change", updateModelOptions);
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
  document.querySelector("#openDocsButton").addEventListener("click", () => window.open("/docs", "_blank", "noopener"));
  document.querySelector("#aboutButton").addEventListener("click", () => elements.aboutDialog.showModal());
  document.querySelector("#closeAbout").addEventListener("click", () => elements.aboutDialog.close());
  document.querySelectorAll("[data-nav]").forEach((button) => {
    if (button.dataset.nav === "workbench") return;
    button.addEventListener("click", () => showToast("该模块已纳入研究路线图；本次交付聚焦可复现解译工作台。"));
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
    renderScenarios();
    updateModelOptions();
    if (state.currentScenario) {
      selectScenario(state.currentScenario);
      if (health.demo_archive) await runCurrentScenario();
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
