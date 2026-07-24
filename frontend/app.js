// ReVE Upscaler — lógica del frontend (sin dependencias).
"use strict";

const $ = (sel) => document.querySelector(sel);

const state = {
  file: null,
  scale: 4,
  system: null,
  pollTimer: null,
  // Previsualización / marca de agua
  objectUrl: null,
  wmBox: null,          // [x, y, w, h] en píxeles del video ORIGINAL
  videoW: 0,
  videoH: 0,
  wmMethod: "fast",     // fast (difuminado) | ia (relleno LaMa)
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

  // Preparamos la previsualización para el marcado de la marca de agua.
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
}

// --- Controles ------------------------------------------------------------
$("#scaleGroup").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-value]");
  if (!btn) return;
  [...$("#scaleGroup").children].forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  state.scale = parseInt(btn.dataset.value, 10);
});

// --- Marca de agua: previsualización + dibujo del recuadro ----------------
$("#removeWm").addEventListener("change", (e) => {
  $("#wmOptions").classList.toggle("hidden", !e.target.checked);
  if (e.target.checked) loadPreview();
});

$("#wmClear").addEventListener("click", () => {
  state.wmBox = null;
  redrawPreview();
  updateWmHint();
});

// Selector de método de borrado (rápido vs IA).
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
  if (!sys.ai_watermark) {
    iaBtn.disabled = true;
    iaBtn.title = "Complemento de IA no instalado";
  } else {
    iaBtn.disabled = false;
    iaBtn.title = "";
  }
  updateWmMethodHint();
}

function updateWmMethodHint() {
  const hint = $("#wmMethodHint");
  if (!hint) return;
  const iaOk = state.system?.ai_watermark;
  if (state.wmMethod === "ia") {
    hint.textContent = "Relleno generativo con IA: mejor para pantallas grandes. Más lento.";
  } else if (iaOk) {
    hint.textContent = "Difuminado rápido. Para máxima calidad, probá 'Relleno con IA'.";
  } else {
    hint.textContent = "Difuminado rápido. El 'Relleno con IA' es un complemento opcional (ver README/guía).";
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

// Carga un frame del video (a la mitad) en el canvas para poder marcar encima.
function loadPreview() {
  const overlay = $("#wmOverlay");
  const canvas = $("#wmCanvas");
  if (!state.objectUrl) {
    overlay.textContent = "Elegí un video para ver la previsualización.";
    overlay.classList.remove("hidden");
    canvas.width = 0; canvas.height = 0;
    return;
  }
  overlay.textContent = "Cargando previsualización…";
  overlay.classList.remove("hidden");

  const video = document.createElement("video");
  video.muted = true;
  video.preload = "auto";
  video.src = state.objectUrl;

  const onFail = () => {
    overlay.textContent = "No se pudo cargar la previsualización de este video.";
    overlay.classList.remove("hidden");
  };
  video.addEventListener("error", onFail);

  video.addEventListener("loadeddata", () => {
    // Buscamos un frame representativo (la marca suele estar en todo el video).
    try { video.currentTime = Math.min(0.5, (video.duration || 1) / 2); }
    catch { video.currentTime = 0; }
  });

  video.addEventListener("seeked", () => {
    state.videoW = video.videoWidth;
    state.videoH = video.videoHeight;
    if (!state.videoW || !state.videoH) return onFail();

    // Ajustamos el canvas al ancho disponible del contenedor (máx. 600 px).
    const stageW = Math.min(600, $("#wmStage").clientWidth || 600);
    const dispW = Math.min(stageW, state.videoW);
    const dispH = Math.round(dispW * state.videoH / state.videoW);
    const canvas = $("#wmCanvas");
    canvas.width = dispW;
    canvas.height = dispH;
    state._wmVideo = video;   // guardamos para poder redibujar
    redrawPreview();
    $("#wmOverlay").classList.add("hidden");
    updateWmHint();
  }, { once: false });
}

// Redibuja el frame + el recuadro actual (si hay).
function redrawPreview() {
  const canvas = $("#wmCanvas");
  const video = state._wmVideo;
  if (!canvas || !video || !canvas.width) return;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  if (state.wmBox) {
    const s = canvas.width / state.videoW;   // original -> display
    const [ox, oy, ow, oh] = state.wmBox;
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#6d5efc";
    ctx.fillStyle = "rgba(109,94,252,0.2)";
    ctx.fillRect(ox * s, oy * s, ow * s, oh * s);
    ctx.strokeRect(ox * s, oy * s, ow * s, oh * s);
  }
}

// Dibujo del recuadro con el mouse (o el dedo).
(function setupBoxDrawing() {
  const canvas = $("#wmCanvas");
  if (!canvas) return;
  let drawing = false, startX = 0, startY = 0;

  const toDisplay = (e) => {
    const rect = canvas.getBoundingClientRect();
    const cx = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
    const cy = (e.touches ? e.touches[0].clientY : e.clientY) - rect.top;
    // CSS px -> px del buffer del canvas
    return {
      x: Math.max(0, Math.min(canvas.width, cx * canvas.width / rect.width)),
      y: Math.max(0, Math.min(canvas.height, cy * canvas.height / rect.height)),
    };
  };

  const boxToOriginal = (x0, y0, x1, y1) => {
    const s = state.videoW / canvas.width;   // display -> original
    const x = Math.min(x0, x1) * s;
    const y = Math.min(y0, y1) * s;
    const w = Math.abs(x1 - x0) * s;
    const h = Math.abs(y1 - y0) * s;
    return [Math.round(x), Math.round(y), Math.round(w), Math.round(h)];
  };

  const start = (e) => {
    if (!state._wmVideo) return;
    e.preventDefault();
    drawing = true;
    const p = toDisplay(e);
    startX = p.x; startY = p.y;
  };
  const move = (e) => {
    if (!drawing) return;
    e.preventDefault();
    const p = toDisplay(e);
    // dibujamos en vivo
    redrawPreview();
    const ctx = canvas.getContext("2d");
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#6d5efc";
    ctx.fillStyle = "rgba(109,94,252,0.2)";
    ctx.fillRect(Math.min(startX, p.x), Math.min(startY, p.y), Math.abs(p.x - startX), Math.abs(p.y - startY));
    ctx.strokeRect(Math.min(startX, p.x), Math.min(startY, p.y), Math.abs(p.x - startX), Math.abs(p.y - startY));
  };
  const end = (e) => {
    if (!drawing) return;
    drawing = false;
    const p = toDisplay(e.changedTouches ? { touches: e.changedTouches } : e);
    const box = boxToOriginal(startX, startY, p.x, p.y);
    // ignoramos recuadros diminutos (clicks accidentales)
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
    // Pedimos que marquen la zona antes de continuar.
    const hint = $("#wmHint");
    hint.textContent = "Primero dibujá el recuadro sobre la marca de agua.";
    hint.style.color = "var(--err)";
    $("#wmOptions").scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }

  const fd = new FormData();
  fd.append("file", state.file);
  fd.append("scale", String(state.scale));
  fd.append("model", $("#modelSelect").value);
  fd.append("use_ai", String(state.system?.mode === "ia"));
  fd.append("interpolate", String($("#interpolate").checked));
  fd.append("interp_factor", "2");
  fd.append("remove_watermark", String(removeWm));
  if (removeWm && state.wmBox) {
    const [x, y, w, h] = state.wmBox;
    fd.append("wm_x", String(x));
    fd.append("wm_y", String(y));
    fd.append("wm_w", String(w));
    fd.append("wm_h", String(h));
    fd.append("wm_method", state.wmMethod);
  }

  showProgress();
  setProgress(0, "Subiendo", "Enviando el video…");

  let job;
  try {
    const res = await fetch("/api/upload", { method: "POST", body: fd });
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

      if (job.status === "done") {
        clearInterval(state.pollTimer);
        showResult(job);
      } else if (job.status === "error") {
        clearInterval(state.pollTimer);
        showError(job.error || job.message || "Error desconocido.");
      }
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
  const box = $("#resultBox");
  box.classList.remove("hidden");
  $("#resultVideo").src = job.download_url;
  $("#downloadBtn").href = job.download_url;
}

function showError(msg) {
  clearInterval(state.pollTimer);
  $("#setupCard").hidden = true;
  $("#progressCard").hidden = false;
  $("#progressTitle").textContent = "Se detuvo el proceso";
  $("#resultBox").classList.add("hidden");
  const box = $("#errorBox");
  box.classList.remove("hidden");
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
