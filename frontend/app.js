// ReVE Upscaler — lógica del frontend (sin dependencias).
"use strict";

const $ = (sel) => document.querySelector(sel);

const state = {
  file: null,
  scale: 4,
  system: null,
  pollTimer: null,
};

// --- Detección del entorno ------------------------------------------------
async function loadSystem() {
  try {
    const res = await fetch("/api/system");
    const sys = await res.json();
    state.system = sys;
    renderSystemBadge(sys);
    renderModeNote(sys);
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
}

function clearFile() {
  state.file = null;
  fileInput.value = "";
  $("#fileChip").classList.add("hidden");
  $(".dz-inner").classList.remove("hidden");
  $("#startBtn").disabled = true;
}

// --- Controles ------------------------------------------------------------
$("#scaleGroup").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-value]");
  if (!btn) return;
  [...$("#scaleGroup").children].forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  state.scale = parseInt(btn.dataset.value, 10);
});

// --- Envío y seguimiento --------------------------------------------------
$("#startBtn").addEventListener("click", startJob);
$("#retryBtn").addEventListener("click", resetToSetup);
$("#againBtn").addEventListener("click", resetToSetup);

async function startJob() {
  if (!state.file) return;

  const fd = new FormData();
  fd.append("file", state.file);
  fd.append("scale", String(state.scale));
  fd.append("model", $("#modelSelect").value);
  fd.append("use_ai", String(state.system?.mode === "ia"));
  fd.append("interpolate", String($("#interpolate").checked));
  fd.append("interp_factor", "2");

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
