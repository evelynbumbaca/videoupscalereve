// ReVE Upscaler — lógica del frontend (sin dependencias).
"use strict";

const $ = (sel) => document.querySelector(sel);

const state = {
  mode: "video",        // "video" | "image"
  jobMode: "video",     // modo con el que se envió el trabajo actual
  file: null,
  scale: 4,
  system: null,
  pollTimer: null,
  // Previsualización / marca de agua
  objectUrl: null,
  wmBox: null,          // [x, y, w, h] en píxeles del archivo ORIGINAL
  mediaW: 0,
  mediaH: 0,
  wmMethod: "fast",
  _wmMedia: null,       // <video> o <img> con el frame a marcar
};

const MODE = {
  video: {
    accept: "video/*,.gif",
    dzTitle: "Arrastrá tu video acá",
    formats: "MP4 · MOV · MKV · WEBM · AVI · GIF",
    endpoint: "/api/upload",
    defaultModel: "animevideo",
    modelHint: "Para clips generados con IA, el primero suele dar el mejor resultado.",
    startText: "Mejorar video",
  },
  image: {
    accept: "image/*",
    dzTitle: "Arrastrá tu imagen acá",
    formats: "PNG · JPG · WEBP · BMP · TIFF",
    endpoint: "/api/upload-image",
    defaultModel: "general",
    modelHint: "Para fotos e imágenes realistas, 'Fotorrealista' suele ir mejor.",
    startText: "Mejorar imagen",
  },
};

// --- Detección del entorno ------------------------------------------------
async function loadSystem() {
  try {
    const res = await fetch("/api/system");
    const sys = await res.json();
    state.system = sys;
    renderSystemBadge(sys);
    renderModeNote(sys);
    configureWmMethod(sys);
  } catch (e) {
    $("#systemBadge").textContent = "No se pudo conectar con el servidor";
    $("#systemBadge").className = "badge badge-warn";
  }
}

function renderSystemBadge(sys) {
  const badge = $("#systemBadge");
  const gpu = sys.gpu?.name || "GPU desconocida";
  if (sys.mode === "ia") {
    badge.textContent = `IA activa · ${gpu}`;
    badge.className = "badge badge-ok";
  } else if (sys.mode === "fallback") {
    badge.textContent = "Modo respaldo (sin modelos IA)";
    badge.className = "badge badge-warn";
  } else {
    badge.textContent = "Faltan herramientas — ejecutá setup_tools.py";
    badge.className = "badge badge-warn";
  }
}

function renderModeNote(sys) {
  const note = $("#modeNote");
  if (sys.mode === "none") {
    note.textContent = "⚠️ ffmpeg no está instalado. Ejecutá: python scripts/setup_tools.py";
  } else if (sys.mode === "fallback") {
    note.textContent = "ℹ️ Los modelos de IA no están instalados: se usará escalado de respaldo (ffmpeg).";
  } else if (!sys.gpu?.accelerated) {
    note.textContent = "ℹ️ Sin GPU acelerada detectada: el proceso puede ser lento.";
  } else {
    note.textContent = "";
  }
}

// --- Cambio de modo (Video / Imagen) --------------------------------------
$("#tabs").addEventListener("click", (e) => {
  const tab = e.target.closest("button[data-mode]");
  if (!tab || tab.dataset.mode === state.mode) return;
  [...$("#tabs").children].forEach((b) => b.classList.remove("active"));
  tab.classList.add("active");
  setMode(tab.dataset.mode);
});

function setMode(mode) {
  state.mode = mode;
  const m = MODE[mode];
  fileInput.setAttribute("accept", m.accept);
  $("#dzTitle").textContent = m.dzTitle;
  $("#dzFormats").textContent = m.formats;
  $("#modelSelect").value = m.defaultModel;
  $("#modelHint").textContent = m.modelHint;
  $("#startBtn").textContent = m.startText;
  $("#videoOnly").classList.toggle("hidden", mode !== "video"); // interpolar solo en video
  clearFile();
}

// --- Selección de archivo -------------------------------------------------
const dropzone = $("#dropzone");
const fileInput = $("#fileInput");

$("#browseBtn").addEventListener("click", (e) => { e.stopPropagation(); fileInput.click(); });
dropzone.addEventListener("click", () => { if (!state.file) fileInput.click(); });
fileInput.addEventListener("change", () => { if (fileInput.files[0]) setFile(fileInput.files[0]); });

["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); })
);
dropzone.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
});

$("#removeFile").addEventListener("click", (e) => { e.stopPropagation(); clearFile(); });

function setFile(file) {
  state.file = file;
  $("#fileName").textContent = file.name;
  $("#fileChip").classList.remove("hidden");
  $(".dz-inner").classList.add("hidden");
  $("#startBtn").disabled = false;

  if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
  state.objectUrl = URL.createObjectURL(file);
  state.wmBox = null;
  if ($("#removeWm").checked) loadPreview();
}

function clearFile() {
  state.file = null;
  fileInput.value = "";
  $("#fileChip").classList.add("hidden");
  $(".dz-inner").classList.remove("hidden");
  $("#startBtn").disabled = true;
  if (state.objectUrl) { URL.revokeObjectURL(state.objectUrl); state.objectUrl = null; }
  state.wmBox = null;
  state._wmMedia = null;
}

// --- Controles ------------------------------------------------------------
$("#scaleGroup").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-value]");
  if (!btn) return;
  [...$("#scaleGroup").children].forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  state.scale = parseInt(btn.dataset.value, 10);
});

$("#removeWm").addEventListener("change", (e) => {
  $("#wmOptions").classList.toggle("hidden", !e.target.checked);
  if (e.target.checked) loadPreview();
});

$("#wmClear").addEventListener("click", () => {
  state.wmBox = null;
  redrawPreview();
  updateWmHint();
});

$("#wmMethodGroup").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-value]");
  if (!btn || btn.disabled) return;
  [...$("#wmMethodGroup").children].forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  state.wmMethod = btn.dataset.value;
  updateWmMethodHint();
});

function configureWmMethod(sys) {
  const iaBtn = $('#wmMethodGroup button[data-value="ia"]');
  if (!iaBtn) return;
  iaBtn.disabled = !sys.ai_watermark;
  iaBtn.title = sys.ai_watermark ? "" : "Complemento de IA no instalado";
  updateWmMethodHint();
}

function updateWmMethodHint() {
  const hint = $("#wmMethodHint");
  if (!hint) return;
  if (state.wmMethod === "ia") {
    hint.textContent = "Relleno generativo con IA: mejor para pantallas grandes. Más lento.";
  } else if (state.system?.ai_watermark) {
    hint.textContent = "Difuminado rápido. Para máxima calidad, probá 'Relleno con IA'.";
  } else {
    hint.textContent = "Difuminado rápido. El 'Relleno con IA' es un complemento opcional (ver guía).";
  }
}

function updateWmHint() {
  const hint = $("#wmHint");
  if (!hint) return;
  if (state.wmBox) {
    const [, , w, h] = state.wmBox;
    hint.textContent = `Zona marcada: ${Math.round(w)}×${Math.round(h)} px ✓`;
    hint.style.color = "var(--ok)";
  } else {
    hint.textContent = "Dibujá el recuadro sobre la marca.";
    hint.style.color = "";
  }
}

// --- Previsualización (video o imagen) para marcar la marca de agua -------
function loadPreview() {
  const overlay = $("#wmOverlay");
  const canvas = $("#wmCanvas");
  if (!state.objectUrl) {
    overlay.textContent = "Elegí un archivo para ver la previsualización.";
    overlay.classList.remove("hidden");
    canvas.width = 0; canvas.height = 0;
    return;
  }
  overlay.textContent = "Cargando previsualización…";
  overlay.classList.remove("hidden");

  const isImage = state.mode === "image" || (state.file && state.file.type.startsWith("image"));
  const onFail = () => { overlay.textContent = "No se pudo cargar la previsualización."; overlay.classList.remove("hidden"); };

  if (isImage) {
    const img = new Image();
    img.onload = () => { drawPreviewMedia(img, img.naturalWidth, img.naturalHeight); };
    img.onerror = onFail;
    img.src = state.objectUrl;
  } else {
    const video = document.createElement("video");
    video.muted = true; video.preload = "auto"; video.src = state.objectUrl;
    video.addEventListener("error", onFail);
    video.addEventListener("loadeddata", () => {
      try { video.currentTime = Math.min(0.5, (video.duration || 1) / 2); } catch { video.currentTime = 0; }
    });
    video.addEventListener("seeked", () => {
      if (!video.videoWidth) return onFail();
      drawPreviewMedia(video, video.videoWidth, video.videoHeight);
    }, { once: true });
  }
}

function drawPreviewMedia(media, w, h) {
  state.mediaW = w; state.mediaH = h;
  if (!w || !h) return;
  const stageW = Math.min(600, $("#wmStage").clientWidth || 600);
  const dispW = Math.min(stageW, w);
  const canvas = $("#wmCanvas");
  canvas.width = dispW;
  canvas.height = Math.round(dispW * h / w);
  state._wmMedia = media;
  redrawPreview();
  $("#wmOverlay").classList.add("hidden");
  updateWmHint();
}

function redrawPreview() {
  const canvas = $("#wmCanvas");
  const media = state._wmMedia;
  if (!canvas || !media || !canvas.width) return;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(media, 0, 0, canvas.width, canvas.height);
  if (state.wmBox) {
    const s = canvas.width / state.mediaW;
    const [ox, oy, ow, oh] = state.wmBox;
    ctx.lineWidth = 2; ctx.strokeStyle = "#6d5efc"; ctx.fillStyle = "rgba(109,94,252,0.2)";
    ctx.fillRect(ox * s, oy * s, ow * s, oh * s);
    ctx.strokeRect(ox * s, oy * s, ow * s, oh * s);
  }
}

// Dibujo del recuadro con mouse / dedo.
(function setupBoxDrawing() {
  const canvas = $("#wmCanvas");
  if (!canvas) return;
  let drawing = false, startX = 0, startY = 0;

  const toDisplay = (e) => {
    const rect = canvas.getBoundingClientRect();
    const cx = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
    const cy = (e.touches ? e.touches[0].clientY : e.clientY) - rect.top;
    return {
      x: Math.max(0, Math.min(canvas.width, cx * canvas.width / rect.width)),
      y: Math.max(0, Math.min(canvas.height, cy * canvas.height / rect.height)),
    };
  };
  const boxToOriginal = (x0, y0, x1, y1) => {
    const s = state.mediaW / canvas.width;
    return [
      Math.round(Math.min(x0, x1) * s), Math.round(Math.min(y0, y1) * s),
      Math.round(Math.abs(x1 - x0) * s), Math.round(Math.abs(y1 - y0) * s),
    ];
  };
  const start = (e) => { if (!state._wmMedia) return; e.preventDefault(); drawing = true; const p = toDisplay(e); startX = p.x; startY = p.y; };
  const move = (e) => {
    if (!drawing) return; e.preventDefault();
    const p = toDisplay(e);
    redrawPreview();
    const ctx = canvas.getContext("2d");
    ctx.lineWidth = 2; ctx.strokeStyle = "#6d5efc"; ctx.fillStyle = "rgba(109,94,252,0.2)";
    ctx.fillRect(Math.min(startX, p.x), Math.min(startY, p.y), Math.abs(p.x - startX), Math.abs(p.y - startY));
    ctx.strokeRect(Math.min(startX, p.x), Math.min(startY, p.y), Math.abs(p.x - startX), Math.abs(p.y - startY));
  };
  const end = (e) => {
    if (!drawing) return; drawing = false;
    const p = toDisplay(e.changedTouches ? { touches: e.changedTouches } : e);
    const box = boxToOriginal(startX, startY, p.x, p.y);
    state.wmBox = (box[2] >= 4 && box[3] >= 4) ? box : null;
    redrawPreview();
    updateWmHint();
  };
  canvas.addEventListener("mousedown", start);
  window.addEventListener("mousemove", move);
  window.addEventListener("mouseup", end);
  canvas.addEventListener("touchstart", start, { passive: false });
  canvas.addEventListener("touchmove", move, { passive: false });
  canvas.addEventListener("touchend", end);
})();

// --- Envío y seguimiento --------------------------------------------------
$("#startBtn").addEventListener("click", startJob);
$("#retryBtn").addEventListener("click", resetToSetup);
$("#againBtn").addEventListener("click", resetToSetup);

async function startJob() {
  if (!state.file) return;

  const removeWm = $("#removeWm").checked;
  if (removeWm && !state.wmBox) {
    const hint = $("#wmHint");
    hint.textContent = "Primero dibujá el recuadro sobre la marca de agua.";
    hint.style.color = "var(--err)";
    $("#wmOptions").scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }

  const m = MODE[state.mode];
  state.jobMode = state.mode;

  const fd = new FormData();
  fd.append("file", state.file);
  fd.append("scale", String(state.scale));
  fd.append("model", $("#modelSelect").value);
  fd.append("use_ai", String(state.system?.mode === "ia"));
  if (state.mode === "video") {
    fd.append("interpolate", String($("#interpolate").checked));
    fd.append("interp_factor", "2");
  }
  fd.append("remove_watermark", String(removeWm));
  if (removeWm && state.wmBox) {
    const [x, y, w, h] = state.wmBox;
    fd.append("wm_x", String(x)); fd.append("wm_y", String(y));
    fd.append("wm_w", String(w)); fd.append("wm_h", String(h));
    fd.append("wm_method", state.wmMethod);
  }

  showProgress();
  setProgress(0, "Subiendo", "Enviando el archivo…");

  let job;
  try {
    const res = await fetch(m.endpoint, { method: "POST", body: fd });
    job = await res.json();
    if (!res.ok) throw new Error(job.detail || "No se pudo iniciar el proceso.");
  } catch (e) {
    return showError(e.message || String(e));
  }
  pollJob(job.id);
}

function pollJob(id) {
  clearInterval(state.pollTimer);
  state.pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/jobs/${id}`);
      const job = await res.json();
      if (!res.ok) throw new Error(job.detail || "Trabajo no encontrado.");
      setProgress(job.progress, job.stage, job.message);
      if (job.status === "done") { clearInterval(state.pollTimer); showResult(job); }
      else if (job.status === "error") { clearInterval(state.pollTimer); showError(job.error || job.message || "Error desconocido."); }
    } catch (e) {
      clearInterval(state.pollTimer);
      showError(e.message || String(e));
    }
  }, 900);
}

// --- Vistas ---------------------------------------------------------------
function showProgress() {
  $("#setupCard").hidden = true;
  $("#progressCard").hidden = false;
  $("#resultBox").classList.add("hidden");
  $("#errorBox").classList.add("hidden");
  $("#progressTitle").textContent = "Procesando…";
}

function setProgress(frac, stage, msg) {
  const pct = Math.round((frac || 0) * 100);
  $("#progressBar").style.width = pct + "%";
  $("#progressPct").textContent = pct + "%";
  $("#progressStage").textContent = stage || "";
  $("#progressMsg").textContent = msg || "";
}

function showResult(job) {
  setProgress(1, "Completado", job.message || "");
  $("#progressTitle").textContent = "¡Listo! 🎉";
  $("#resultBox").classList.remove("hidden");

  const vid = $("#resultVideo"), img = $("#resultImage");
  if (state.jobMode === "image") {
    vid.classList.add("hidden"); vid.removeAttribute("src");
    img.classList.remove("hidden"); img.src = job.download_url;
  } else {
    img.classList.add("hidden"); img.removeAttribute("src");
    vid.classList.remove("hidden"); vid.src = job.download_url;
  }
  $("#downloadBtn").href = job.download_url;
}

function showError(msg) {
  clearInterval(state.pollTimer);
  $("#setupCard").hidden = true;
  $("#progressCard").hidden = false;
  $("#progressTitle").textContent = "Se detuvo el proceso";
  $("#resultBox").classList.add("hidden");
  $("#errorBox").classList.remove("hidden");
  $("#errorMsg").textContent = msg;
}

function resetToSetup() {
  clearInterval(state.pollTimer);
  $("#progressCard").hidden = true;
  $("#setupCard").hidden = false;
  clearFile();
}

// --- Init -----------------------------------------------------------------
loadSystem();
