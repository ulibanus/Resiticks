#!/usr/bin/env python3
"""
HTML/CSS/JS Web UI template for Resiticks Hub (8 slots, Web PES Calibration,
Anti-Drift deadzone/center tuning, Slot Swapping, USB Diagnostics, GitHub Updater).
"""

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Resiticks — Hub Universal de Joysticks</title>
<style>
  :root {
    --bg: #0b1120;
    --card-bg: #151e32;
    --card-border: #24324f;
    --primary: #3b82f6;
    --primary-hover: #2563eb;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --text: #f8fafc;
    --text-muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: var(--bg); color: var(--text); padding: 18px; font-size: 13px; }

  header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; border-bottom: 1px solid var(--card-border); padding-bottom: 14px; margin-bottom: 16px; }
  .logo-title h1 { font-size: 22px; font-weight: 800; color: #60a5fa; letter-spacing: -0.5px; display: flex; align-items: center; gap: 8px; }
  .logo-title p { font-size: 12px; color: var(--text-muted); }

  .header-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
  .tabs { display: flex; gap: 6px; flex-wrap: wrap; }
  .tab-btn { background: var(--card-bg); color: var(--text-muted); border: 1px solid var(--card-border); padding: 7px 12px; border-radius: 6px; font-weight: 600; font-size: 12px; cursor: pointer; transition: 0.15s; }
  .tab-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }

  .btn { background: var(--primary); color: #fff; border: none; padding: 7px 13px; border-radius: 6px; font-weight: 600; font-size: 12px; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; transition: 0.15s; }
  .btn:hover { filter: brightness(1.1); }
  .btn-success { background: #10b981; }
  .btn-warn { background: #d97706; }
  .btn-danger { background: #dc2626; }
  .btn-small { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; padding: 4px 9px; border-radius: 4px; font-size: 11px; cursor: pointer; text-decoration: none; font-weight: 600; }
  .btn-small:hover { background: #334155; color: #fff; }

  .tab-content { display: none; }
  .tab-content.active { display: block; }

  .status-bar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; background: #11192c; border: 1px solid var(--card-border); border-radius: 8px; padding: 9px 12px; }
  .alert-banner { display: none; padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; font-size: 12.5px; }
  .alert-banner.warn { display: block; background: rgba(245, 158, 11, 0.12); border: 1px solid #d97706; color: #fde68a; }
  .alert-banner.error { display: block; background: rgba(239, 68, 68, 0.14); border: 1px solid #ef4444; color: #fecaca; }

  .uncal-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
  .uncal-chip { background: #1e293b; border: 1px solid #d97706; padding: 5px 10px; border-radius: 6px; display: inline-flex; align-items: center; gap: 8px; color: #fff; font-size: 12px; }

  .slots-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(430px, 1fr)); gap: 14px; }
  @media (max-width: 900px) { .slots-grid { grid-template-columns: 1fr; } }

  .slot-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 10px; padding: 14px; border-top: 4px solid var(--card-border); }
  .slot-card.connected { border-top-color: var(--success); }

  .slot-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; gap: 8px; }
  .slot-tag { font-size: 11px; font-weight: 800; background: #1e293b; padding: 3px 8px; border-radius: 4px; color: #cbd5e1; }
  .slot-card.connected .slot-tag { background: #064e3b; color: #6ee7b7; }
  .slot-title { font-size: 15px; font-weight: 700; color: #fff; margin-bottom: 2px; }
  .slot-sub { font-size: 11.5px; color: var(--text-muted); margin-bottom: 10px; }

  .card-inner-tester {
    background: #090e1a;
    border: 1px solid #1c2742;
    border-radius: 8px;
    padding: 10px;
    display: grid;
    grid-template-columns: 155px 1fr;
    gap: 12px;
    align-items: center;
  }

  .sticks-box { display: flex; justify-content: space-between; align-items: flex-start; gap: 6px; }
  .stick-unit { text-align: center; flex: 1; }
  .stick-circle { width: 64px; height: 64px; border-radius: 50%; border: 1px solid #334155; position: relative; background: #121929; margin: 3px auto; }
  .deadzone-guide { border-radius: 50%; border: 1px dashed rgba(239, 68, 68, 0.7); position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); pointer-events: none; }
  .stick-dot { width: 12px; height: 12px; border-radius: 50%; background: #3b82f6; position: absolute; top: 26px; left: 26px; box-shadow: 0 0 6px #3b82f6; }
  .stick-label { font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; }
  .stick-coords { font-size: 9px; color: #64748b; font-family: monospace; margin-top: 2px; }
  .drift-badge { font-size: 9.5px; font-weight: 700; padding: 1px 4px; border-radius: 3px; display: inline-block; background: #064e3b; color: #6ee7b7; margin-top: 2px; }
  .drift-badge.drift { background: #78350f; color: #fcd34d; }

  .buttons-cluster { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .dpad-layout, .face-layout { display: grid; grid-template-columns: 20px 20px 20px; grid-template-rows: 20px 20px 20px; gap: 2px; justify-content: center; align-content: center; }
  .btn-chip {
    width: 20px; height: 20px; border-radius: 4px;
    background: #172136; border: 1px solid #293856;
    color: #64748b; font-size: 9px; font-weight: 800;
    display: flex; align-items: center; justify-content: center;
  }
  .btn-chip.circle { border-radius: 50%; font-size: 10px; }
  .btn-chip.pressed { background: #3b82f6; color: #ffffff; border-color: #60a5fa; box-shadow: 0 0 8px rgba(59, 130, 246, 0.8); transform: scale(1.08); }

  .triggers-row { display: grid; grid-template-columns: auto 1fr 1fr auto; gap: 6px; align-items: center; margin-bottom: 6px; }
  .trig-badge { font-size: 10px; font-weight: 700; background: #172136; border: 1px solid #293856; padding: 2px 6px; border-radius: 4px; color: #94a3b8; text-align: center; }
  .trig-badge.pressed { background: #10b981; color: #fff; border-color: #34d399; }
  .trig-bar-wrap { background: #172136; border: 1px solid #293856; border-radius: 4px; height: 18px; position: relative; overflow: hidden; }
  .trig-bar-fill { background: #10b981; height: 100%; width: 0%; transition: width 0.04s; }
  .trig-bar-text { position: absolute; inset: 0; font-size: 9.5px; font-weight: 700; color: #e2e8f0; display: flex; align-items: center; justify-content: center; }

  .card-tune-panel { margin-top: 8px; padding: 8px 10px; background: #101729; border: 1px solid #1e2d4a; border-radius: 6px; display: none; font-size: 11.5px; }
  .card-tune-panel.open { display: block; }
  .tune-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 5px 0; }
  .tune-row input[type="range"] { flex: 1; accent-color: #3b82f6; }

  .card-footer { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 10px; font-size: 11px; }
  .slot-select { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px; padding: 3px 6px; font-size: 11px; }

  table { width: 100%; border-collapse: collapse; margin-top: 15px; }
  th { text-align: left; padding: 9px; background: #151e32; color: var(--text-muted); border-bottom: 1px solid var(--card-border); font-size: 12px; }
  td { padding: 9px; border-bottom: 1px solid var(--card-border); font-size: 12px; }

  .diag-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; margin-top: 12px; }
  .diag-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; }
  .diag-card h3 { font-size: 14px; margin-bottom: 8px; color: #60a5fa; }
  .diag-item { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #1e293b; }
  .code-box { background: #090e1a; border: 1px solid #24324f; border-radius: 6px; padding: 8px; font-family: monospace; font-size: 11px; color: #93c5fd; margin-top: 8px; word-break: break-all; }

  /* Web Calibration Modal */
  .modal-backdrop { display: none; position: fixed; inset: 0; background: rgba(2, 6, 23, 0.82); z-index: 100; align-items: center; justify-content: center; padding: 16px; }
  .modal-backdrop.open { display: flex; }
  .modal-box { background: #131c31; border: 1px solid #2d4066; border-radius: 12px; max-width: 780px; width: 100%; padding: 20px; box-shadow: 0 25px 50px rgba(0,0,0,0.6); max-height: 92vh; overflow-y: auto; }
  .pes-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 14px 0; }
  .pes-col { background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 10px; }
  .pes-col h4 { font-size: 11px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px; text-align: center; }
  .pes-step { display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; border-radius: 4px; margin-bottom: 3px; font-size: 11.5px; color: #94a3b8; border: 1px solid transparent; }
  .pes-step.done { color: #6ee7b7; background: rgba(16, 185, 129, 0.08); }
  .pes-step.current { color: #fff; background: rgba(59, 130, 246, 0.25); border-color: #3b82f6; font-weight: 700; }
  .progress-track { background: #0b1120; border-radius: 99px; height: 8px; overflow: hidden; margin: 8px 0; }
  .progress-fill { background: #3b82f6; height: 100%; width: 0%; transition: width 0.2s; }
</style>
</head>
<body>

<header>
  <div class="logo-title">
    <h1>🎮 Resiticks</h1>
    <p>Hub Universal de Joysticks &amp; Puente Multi-Jugador (Hasta 8 Jugadores)</p>
  </div>
  <div class="header-actions">
    <button id="btn-bridge-toggle" class="btn btn-success" onclick="toggleBridge()">🟢 Puente Activo</button>
    <button class="btn" style="background: #0ea5e9;" onclick="openCalibrationPicker()">🎯 Calibrar Mando (Web)</button>
    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('tab-dashboard', this)">🏟️ Partida en Vivo</button>
      <button class="tab-btn" onclick="switchTab('tab-profiles', this)">📁 Biblioteca</button>
      <button class="tab-btn" onclick="switchTab('tab-diagnostics', this)">🩺 Diagnóstico USB</button>
    </div>
  </div>
</header>

<div id="conn-banner" class="alert-banner"></div>
<div id="errors-banner" class="alert-banner"></div>
<div id="uncal-banner" class="alert-banner"></div>

<div id="tab-dashboard" class="tab-content active">
  <div class="status-bar">
    <div>
      <span style="color: var(--text-muted);">Estado del Motor:</span>
      <strong id="motor-status-text" style="color: #34d399; margin-left: 5px;">🟢 ACTIVO (EVIOCGRAB + Xbox 360 Virtuales)</strong>
    </div>
    <div style="font-size: 11.5px; color: var(--text-muted);">
      💡 Mové palancas o botones para testear • Usá ⚙️ Ajustes para anti-drift, centro y cambio de jugador (P1↔P2)
    </div>
  </div>
  <div class="slots-grid" id="slots-container"></div>
</div>

<div id="tab-profiles" class="tab-content">
  <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
    <div>
      <h2 style="font-size: 18px; color: #fff;">Biblioteca de Mandos Guardados</h2>
      <p style="color: var(--text-muted); font-size: 12px;">Perfiles listos para conectar y jugar. Podés actualizar desde GitHub o importar perfiles de amigos.</p>
    </div>
    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
      <button class="btn" style="background: #6366f1;" onclick="updateFromGitHub()">🔄 Actualizar desde GitHub</button>
      <label class="btn" style="background: #0284c7; cursor: pointer;">
        📤 Importar JSON
        <input type="file" accept=".json" style="display:none;" onchange="importProfileFile(event)">
      </label>
      <button class="btn" onclick="launchTerminalCalibration()">🖥️ Calibrador Consola</button>
      <a href="/api/export_pack" class="btn btn-success">📦 Descargar Pack ZIP Completo</a>
    </div>
  </div>
  <div id="update-feedback" style="margin-bottom: 10px; font-size: 12px;"></div>
  <table>
    <thead>
      <tr>
        <th>Nombre del Joystick</th>
        <th>VID:PID</th>
        <th>Deadzone (Izq / Der)</th>
        <th>Vibración</th>
        <th>Acciones</th>
      </tr>
    </thead>
    <tbody id="profiles-body"></tbody>
  </table>
</div>

<div id="tab-diagnostics" class="tab-content">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
    <div>
      <h2 style="font-size: 18px; color: #fff;">Diagnóstico Hardware, Permisos &amp; USB</h2>
      <p style="color: var(--text-muted); font-size: 12px;">Verificación de <code>/dev/uinput</code>, permisos de lectura/escritura y caídas USB (error -71/-32).</p>
    </div>
    <button class="btn" onclick="loadDiagnostics()">🔄 Re-escanear Sistema</button>
  </div>
  <div id="diag-content" class="diag-grid"></div>
</div>

<!-- Web Calibration Wizard Modal -->
<div id="cal-modal" class="modal-backdrop">
  <div class="modal-box">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <h2 id="cal-title" style="font-size:17px; color:#60a5fa;">🎯 Asistente Visual PES Settings</h2>
      <button class="btn-small" onclick="cancelWebCalibration()">✕ Cerrar</button>
    </div>

    <div id="cal-picker-view" style="margin-top:12px;">
      <p style="color:var(--text-muted); margin-bottom:10px;">Elegí el mando conectado que querés calibrar (los demás jugadores siguen jugando sin cortes):</p>
      <div id="cal-device-list" style="display:flex; flex-direction:column; gap:8px;"></div>
    </div>

    <div id="cal-wizard-view" style="display:none; margin-top:10px;">
      <div class="progress-track"><div id="cal-progress-fill" class="progress-fill"></div></div>
      <div id="cal-prompt-box" style="background:#0b1120; border:1px solid #3b82f6; border-radius:8px; padding:12px; margin-top:8px;">
        <div id="cal-step-counter" style="font-size:11px; color:#93c5fd;">Paso 1 / 25</div>
        <div id="cal-step-prompt" style="font-size:16px; font-weight:700; color:#fff; margin-top:4px;">Esperando entrada...</div>
        <div id="cal-warning-box" style="display:none; margin-top:8px; background:rgba(245,158,11,0.16); border:1px solid #f59e0b; padding:8px; border-radius:6px; color:#fde68a; font-size:12px;"></div>
        <div style="display:flex; gap:8px; margin-top:10px; flex-wrap:wrap;">
          <button id="btn-cal-prev" class="btn-small" onclick="calPrevStep()">⬅️ Paso Anterior</button>
          <button id="btn-cal-skip" class="btn-small" onclick="calSkipStep()">⏩ Saltear Opcional</button>
          <button id="btn-cal-keep" class="btn-small" style="display:none; border-color:#f59e0b; color:#fde68a;" onclick="calAcceptWarning()">Conservar igual</button>
        </div>
      </div>

      <div class="pes-columns">
        <div class="pes-col"><h4>Columna Izquierda (PES)</h4><div id="pes-col-left"></div></div>
        <div class="pes-col"><h4>Columna Derecha (PES)</h4><div id="pes-col-right"></div></div>
      </div>
    </div>

    <div id="cal-save-view" style="display:none; margin-top:12px;">
      <h3 style="color:#34d399; margin-bottom:8px;">🎉 ¡Calibración Completada!</h3>
      <div id="cal-consistency-warnings" style="margin-bottom:10px; color:#fde68a; font-size:12px;"></div>
      <label style="display:block; margin-bottom:6px; color:var(--text-muted);">Nombre del perfil / amigo:</label>
      <input id="cal-custom-name" type="text" style="width:100%; padding:8px; border-radius:6px; border:1px solid #334155; background:#0b1120; color:#fff; margin-bottom:12px;">
      <div style="display:flex; gap:8px; justify-content:flex-end;">
        <button class="btn-small" onclick="cancelWebCalibration()">Cancelar</button>
        <button class="btn btn-success" onclick="calSaveProfile()">💾 Guardar Perfil</button>
      </div>
    </div>
  </div>
</div>

<script>
  let lastSlotsSig = '';
  let lastProfilesRev = -1;
  let openTuneSlots = new Set();
  let failCount = 0;
  let lastStatusData = null;
  let calPollTimer = null;

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function switchTab(tabId, btnEl) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    if (btnEl) btnEl.classList.add('active');
    if (tabId === 'tab-profiles') loadProfilesList();
    if (tabId === 'tab-diagnostics') loadDiagnostics();
  }

  async function toggleBridge() {
    try {
      const res = await fetch('/api/bridge/toggle', { method: 'POST' });
      const data = await res.json();
      updateBridgeUI(data.bridge_enabled);
    } catch (e) {
      alert('No se pudo cambiar el estado del puente.');
    }
  }

  function updateBridgeUI(enabled) {
    const btn = document.getElementById('btn-bridge-toggle');
    const txt = document.getElementById('motor-status-text');
    if (enabled) {
      btn.className = 'btn btn-success';
      btn.textContent = '🟢 Puente Activo';
      txt.style.color = '#34d399';
      txt.textContent = '🟢 ACTIVO (EVIOCGRAB + Xbox 360 Virtuales)';
    } else {
      btn.className = 'btn btn-warn';
      btn.textContent = '⏸️ Puente Pausado';
      txt.style.color = '#fcd34d';
      txt.textContent = '⏸️ PAUSADO (Modo Monitor sin bloqueo EVIOCGRAB)';
    }
  }

  async function launchTerminalCalibration() {
    try {
      const res = await fetch('/api/calibrate/launch', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) alert(data.error || 'No se pudo abrir la terminal.');
    } catch (e) {
      alert('Error abriendo calibración por consola.');
    }
  }

  function toggleTunePanel(slot) {
    if (openTuneSlots.has(slot)) openTuneSlots.delete(slot);
    else openTuneSlots.add(slot);
    const el = document.getElementById('tune-panel-' + slot);
    if (el) el.classList.toggle('open', openTuneSlots.has(slot));
  }

  async function swapOrMoveSlot(fromSlot, targetSlot) {
    const toSlot = parseInt(targetSlot, 10);
    if (!toSlot || toSlot === fromSlot) return;
    await fetch('/api/slots/swap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_slot: fromSlot, to_slot: toSlot })
    });
  }

  async function pinSlotPreference(slot, pinKey) {
    await fetch('/api/slots/pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slot: slot, pin_key: pinKey })
    });
  }

  async function tuneProfile(vendor, product, payload) {
    await fetch('/api/profile/tune', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({ vendor, product }, payload))
    });
  }

  async function centerZeroStick(slot) {
    const res = await fetch('/api/profile/center_zero', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slot })
    });
    if (!res.ok) alert('No se pudo calibrar el centro en reposo.');
  }

  function buildEmptySlotHtml(slot) {
    return `
      <div class="slot-card" id="slot-card-${slot}">
        <div class="slot-header">
          <span class="slot-tag">JUGADOR ${slot} [P${slot}]</span>
          <span style="font-size: 11px; color: #64748b;">DISPONIBLE</span>
        </div>
        <div class="slot-title" style="color: #64748b;">(Slot Libre)</div>
        <div class="slot-sub">Enchufá cualquier joystick para tomar el Jugador ${slot}.</div>
        <div class="card-inner-tester" style="opacity: 0.3; text-align: center; display: block; padding: 25px 10px; color: #64748b;">
          Esperando mando de amigo...
        </div>
      </div>
    `;
  }

  function buildConnectedSlotHtml(slot, item) {
    const dzL = Math.round((item.deadzone_left ?? 0.05) * 100);
    const dzR = Math.round((item.deadzone_right ?? 0.05) * 100);
    const dzPxL = Math.max(4, Math.round((item.deadzone_left ?? 0.05) * 46));
    const dzPxR = Math.max(4, Math.round((item.deadzone_right ?? 0.05) * 46));
    const rumbleOn = item.rumble_enabled !== false;

    let swapOpts = '';
    for (let s = 1; s <= 8; s++) {
      swapOpts += `<option value="${s}" ${s === slot ? 'selected' : ''}>P${s}</option>`;
    }

    return `
      <div class="slot-card connected" id="slot-card-${slot}">
        <div class="slot-header">
          <span class="slot-tag">JUGADOR ${slot} [P${slot}]</span>
          <div style="display:flex; align-items:center; gap:6px;">
            <select class="slot-select" title="Mover o intercambiar slot" onchange="swapOrMoveSlot(${slot}, this.value)">${swapOpts}</select>
            <button class="btn-small" title="Fijar este puerto USB al Jugador ${slot}" data-slot="${slot}" data-pinkey="${escapeHtml(item.pin_key || '')}" onclick="pinSlotPreference(Number(this.dataset.slot), this.dataset.pinkey)">📌</button>
            <span style="font-size: 11px; color: #34d399; font-weight: 700;">🟢 CONECTADO</span>
          </div>
        </div>
        <div class="slot-title">🎮 ${escapeHtml(item.name)}</div>
        <div class="slot-sub">Hardware: <code>${escapeHtml(item.vendor)}:${escapeHtml(item.product)}</code> • ${escapeHtml(item.dev_path)} • Xbox 360 Pad ${slot}</div>

        <div class="card-inner-tester">
          <div class="sticks-box">
            <div class="stick-unit">
              <div class="stick-label">Stick Izq</div>
              <div class="stick-circle">
                <div id="dz-l-${slot}" class="deadzone-guide" style="width:${dzPxL}px;height:${dzPxL}px;"></div>
                <div id="dot-l-${slot}" class="stick-dot"></div>
              </div>
              <div id="coord-l-${slot}" class="stick-coords">0.00, 0.00</div>
              <span id="drift-l-${slot}" class="drift-badge">Drift: OK</span>
            </div>

            <div class="stick-unit">
              <div class="stick-label">Stick Der</div>
              <div class="stick-circle">
                <div id="dz-r-${slot}" class="deadzone-guide" style="width:${dzPxR}px;height:${dzPxR}px;"></div>
                <div id="dot-r-${slot}" class="stick-dot"></div>
              </div>
              <div id="coord-r-${slot}" class="stick-coords">0.00, 0.00</div>
              <span id="drift-r-${slot}" class="drift-badge">Drift: OK</span>
            </div>
          </div>

          <div>
            <div class="triggers-row">
              <span id="btn-${slot}-lb" class="trig-badge">LB</span>
              <div class="trig-bar-wrap"><div id="bar-lt-${slot}" class="trig-bar-fill"></div><div id="txt-lt-${slot}" class="trig-bar-text">LT 0%</div></div>
              <div class="trig-bar-wrap"><div id="bar-rt-${slot}" class="trig-bar-fill"></div><div id="txt-rt-${slot}" class="trig-bar-text">RT 0%</div></div>
              <span id="btn-${slot}-rb" class="trig-badge">RB</span>
            </div>

            <div class="buttons-cluster">
              <div class="dpad-layout">
                <div></div>
                <div id="btn-${slot}-dpup" class="btn-chip">▲</div>
                <div></div>
                <div id="btn-${slot}-dpleft" class="btn-chip">◀</div>
                <div class="btn-chip" style="font-size: 7px; color: #475569;">+</div>
                <div id="btn-${slot}-dpright" class="btn-chip">▶</div>
                <div></div>
                <div id="btn-${slot}-dpdown" class="btn-chip">▼</div>
                <div></div>
              </div>

              <div class="face-layout">
                <div></div>
                <div id="btn-${slot}-y" class="btn-chip circle">Y</div>
                <div></div>
                <div id="btn-${slot}-x" class="btn-chip circle">X</div>
                <div id="btn-${slot}-guide" class="btn-chip circle" style="font-size: 7.5px;">Xbox</div>
                <div id="btn-${slot}-b" class="btn-chip circle">B</div>
                <div></div>
                <div id="btn-${slot}-a" class="btn-chip circle">A</div>
                <div></div>
              </div>
            </div>

            <div style="display: flex; justify-content: space-around; margin-top: 6px; font-size: 10px;">
              <span id="btn-${slot}-back" class="trig-badge">SELECT</span>
              <span id="btn-${slot}-thumbl" class="trig-badge">L3</span>
              <span id="btn-${slot}-thumbr" class="trig-badge">R3</span>
              <span id="btn-${slot}-start" class="trig-badge">START</span>
            </div>
          </div>
        </div>

        <div id="tune-panel-${slot}" class="card-tune-panel ${openTuneSlots.has(slot) ? 'open' : ''}">
          <div class="tune-row">
            <span>Zona Muerta Izq (<strong id="dzl-val-${slot}">${dzL}%</strong>):</span>
            <input type="range" min="2" max="30" value="${dzL}" data-vendor="${escapeHtml(item.vendor)}" data-product="${escapeHtml(item.product)}" oninput="document.getElementById('dzl-val-${slot}').textContent=this.value+'%'" onchange="tuneProfile(this.dataset.vendor, this.dataset.product, {deadzone_left: this.value/100})">
          </div>
          <div class="tune-row">
            <span>Zona Muerta Der (<strong id="dzr-val-${slot}">${dzR}%</strong>):</span>
            <input type="range" min="2" max="30" value="${dzR}" data-vendor="${escapeHtml(item.vendor)}" data-product="${escapeHtml(item.product)}" oninput="document.getElementById('dzr-val-${slot}').textContent=this.value+'%'" onchange="tuneProfile(this.dataset.vendor, this.dataset.product, {deadzone_right: this.value/100})">
          </div>
          <div class="tune-row">
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
              <input type="checkbox" ${rumbleOn ? 'checked' : ''} data-vendor="${escapeHtml(item.vendor)}" data-product="${escapeHtml(item.product)}" onchange="tuneProfile(this.dataset.vendor, this.dataset.product, {rumble_enabled: this.checked})">
              <span>📳 Vibración (Rumble)</span>
            </label>
            <button class="btn-small" onclick="centerZeroStick(${slot})">🎯 Fijar Centro Actual (Cero)</button>
          </div>
        </div>

        <div class="card-footer">
          <span style="color: #6ee7b7; font-weight: 600;">✓ Perfil Activo</span>
          <div style="display:flex; gap:6px;">
            <button class="btn-small" onclick="toggleTunePanel(${slot})">🎛️ Anti-Drift / Ajustes</button>
            <button class="btn-small" data-dev="${escapeHtml(item.dev_path)}" data-name="${escapeHtml(item.name)}" onclick="startWebCalibration(this.dataset.dev, this.dataset.name)">⚙️ Recalibrar</button>
          </div>
        </div>
      </div>
    `;
  }

  function updateSlotLiveDom(slot, item, inp) {
    if (!item) return;
    const btns = inp.buttons || {};
    const lx = inp.lx || 0;
    const ly = inp.ly || 0;
    const rx = inp.rx || 0;
    const ry = inp.ry || 0;
    const lt = inp.lt || 0;
    const rt = inp.rt || 0;
    const dzL = item.deadzone_left ?? 0.05;
    const dzR = item.deadzone_right ?? 0.05;

    const dotL = document.getElementById('dot-l-' + slot);
    const dotR = document.getElementById('dot-r-' + slot);
    if (dotL) dotL.style.transform = `translate(${lx * 24}px, ${ly * 24}px)`;
    if (dotR) dotR.style.transform = `translate(${rx * 24}px, ${ry * 24}px)`;

    const cL = document.getElementById('coord-l-' + slot);
    const cR = document.getElementById('coord-r-' + slot);
    if (cL) cL.textContent = `${lx.toFixed(2)}, ${ly.toFixed(2)}`;
    if (cR) cR.textContent = `${rx.toFixed(2)}, ${ry.toFixed(2)}`;

    const dzElL = document.getElementById('dz-l-' + slot);
    const dzElR = document.getElementById('dz-r-' + slot);
    if (dzElL) { const p = Math.max(4, Math.round(dzL * 46)); dzElL.style.width = p+'px'; dzElL.style.height = p+'px'; }
    if (dzElR) { const p = Math.max(4, Math.round(dzR * 46)); dzElR.style.width = p+'px'; dzElR.style.height = p+'px'; }

    const drL = document.getElementById('drift-l-' + slot);
    const drR = document.getElementById('drift-r-' + slot);
    const isDriftL = Math.abs(lx) > Math.max(dzL, 0.06) || Math.abs(ly) > Math.max(dzL, 0.06);
    const isDriftR = Math.abs(rx) > Math.max(dzR, 0.06) || Math.abs(ry) > Math.max(dzR, 0.06);
    if (drL) { drL.className = 'drift-badge' + (isDriftL ? ' drift' : ''); drL.textContent = isDriftL ? '⚠️ Moviendo' : 'Drift: OK'; }
    if (drR) { drR.className = 'drift-badge' + (isDriftR ? ' drift' : ''); drR.textContent = isDriftR ? '⚠️ Moviendo' : 'Drift: OK'; }

    const barLt = document.getElementById('bar-lt-' + slot);
    const txtLt = document.getElementById('txt-lt-' + slot);
    const barRt = document.getElementById('bar-rt-' + slot);
    const txtRt = document.getElementById('txt-rt-' + slot);
    if (barLt) barLt.style.width = lt + '%';
    if (txtLt) txtLt.textContent = 'LT ' + lt + '%';
    if (barRt) barRt.style.width = rt + '%';
    if (txtRt) txtRt.textContent = 'RT ' + rt + '%';

    const btnKeys = ['a','b','x','y','lb','rb','back','start','guide','thumbl','thumbr','dpup','dpdown','dpleft','dpright'];
    for (const k of btnKeys) {
      const el = document.getElementById(`btn-${slot}-${k}`);
      if (el) el.classList.toggle('pressed', Boolean(btns[k]));
    }
  }

  function renderBanners(data) {
    const errBanner = document.getElementById('errors-banner');
    const errs = Object.entries(data.device_errors || {});
    if (errs.length > 0) {
      errBanner.className = 'alert-banner error';
      errBanner.innerHTML = '<strong>❌ Error de hardware / permisos:</strong><br>' +
        errs.map(([id, msg]) => `• ${escapeHtml(msg)}`).join('<br>');
    } else {
      errBanner.className = 'alert-banner';
      errBanner.innerHTML = '';
    }

    const uncalBanner = document.getElementById('uncal-banner');
    const uncal = data.uncalibrated_devices || [];
    if (uncal.length > 0) {
      uncalBanner.className = 'alert-banner warn';
      uncalBanner.innerHTML = '<strong>🔌 Joystick nuevo detectado sin perfil calibrado:</strong><div class="uncal-list">' +
        uncal.map(gp => `
          <div class="uncal-chip">
            <span>🎮 <strong>${escapeHtml(gp.name)}</strong> (<code>${escapeHtml(gp.vendor)}:${escapeHtml(gp.product)}</code>)</span>
            <button class="btn-small" style="background:#d97706;border-color:#f59e0b;color:#fff;" data-dev="${escapeHtml(gp.dev_path)}" data-name="${escapeHtml(gp.name)}" onclick="startWebCalibration(this.dataset.dev, this.dataset.name)">⚡ Calibrar Ahora</button>
          </div>
        `).join('') + '</div>';
    } else {
      uncalBanner.className = 'alert-banner';
      uncalBanner.innerHTML = '';
    }
  }

  async function updateDashboard() {
    try {
      const res = await fetch('/api/status');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      lastStatusData = data;
      failCount = 0;
      document.getElementById('conn-banner').className = 'alert-banner';

      updateBridgeUI(Boolean(data.bridge_enabled));
      renderBanners(data);

      if (data.profile_revision !== lastProfilesRev) {
        lastProfilesRev = data.profile_revision;
        if (document.getElementById('tab-profiles').classList.contains('active') || lastProfilesRev === 0) {
          loadProfilesList();
        }
      }

      // Rebuild DOM cards ONLY when slot occupancy/config changes, preserving clicks/sliders
      const sigObj = {};
      for (let s = 1; s <= 8; s++) {
        const it = data.active_slots[String(s)] || data.active_slots[s];
        sigObj[s] = it ? `${it.vendor}:${it.product}:${it.dev_path}:${it.name}:${it.rumble_enabled}` : null;
      }
      const sig = JSON.stringify(sigObj);
      const container = document.getElementById('slots-container');
      if (sig !== lastSlotsSig) {
        lastSlotsSig = sig;
        let html = '';
        for (let s = 1; s <= 8; s++) {
          const item = data.active_slots[String(s)] || data.active_slots[s];
          html += item ? buildConnectedSlotHtml(s, item) : buildEmptySlotHtml(s);
        }
        container.innerHTML = html;
      }

      for (let s = 1; s <= 8; s++) {
        const item = data.active_slots[String(s)] || data.active_slots[s];
        const inp = data.live_inputs[String(s)] || data.live_inputs[s] || {};
        updateSlotLiveDom(s, item, inp);
      }
    } catch (e) {
      failCount += 1;
      if (failCount >= 3) {
        const cb = document.getElementById('conn-banner');
        cb.className = 'alert-banner error';
        cb.textContent = '🔴 Sin conexión con el motor Resiticks (127.0.0.1:8765). Verificá que app.py esté corriendo.';
      }
    }
  }

  async function loadProfilesList() {
    try {
      const res = await fetch('/api/profiles');
      const profiles = await res.json();
      const body = document.getElementById('profiles-body');
      let html = '';
      for (const p of profiles) {
        const dzL = Math.round((p.deadzone_left ?? 0.05) * 100);
        const dzR = Math.round((p.deadzone_right ?? 0.05) * 100);
        const rum = p.rumble_enabled !== false ? '✅ Activa' : '⏸️ Desactivada';
        html += `
          <tr>
            <td><strong>🎮 ${escapeHtml(p.name)}</strong></td>
            <td><code>${escapeHtml(p.vendor)}:${escapeHtml(p.product)}</code></td>
            <td>${dzL}% / ${dzR}%</td>
            <td>${rum}</td>
            <td style="display:flex; gap:6px;">
              <button class="btn-small" data-vendor="${escapeHtml(p.vendor)}" data-product="${escapeHtml(p.product)}" data-name="${escapeHtml(p.name)}" onclick="renameProfile(this.dataset.vendor, this.dataset.product, this.dataset.name)">✏️ Renombrar</button>
              <button class="btn-small" style="border-color:#7f1d1d;color:#fca5a5;" data-vendor="${escapeHtml(p.vendor)}" data-product="${escapeHtml(p.product)}" data-name="${escapeHtml(p.name)}" onclick="deleteProfile(this.dataset.vendor, this.dataset.product, this.dataset.name)">🗑️</button>
            </td>
          </tr>
        `;
      }
      body.innerHTML = html;
    } catch (e) {}
  }

  async function renameProfile(vendor, product, currentName) {
    const newName = prompt('Nuevo nombre para el joystick:', currentName);
    if (!newName || !newName.trim()) return;
    await fetch('/api/profiles/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vendor, product, name: newName.trim() })
    });
    loadProfilesList();
  }

  async function deleteProfile(vendor, product, name) {
    if (!confirm(`¿Eliminar el perfil "${name}" (${vendor}:${product})?`)) return;
    await fetch('/api/profiles/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vendor, product })
    });
    loadProfilesList();
  }

  async function importProfileFile(evt) {
    const file = evt.target.files[0];
    if (!file) return;
    const text = await file.text();
    const res = await fetch('/api/profiles/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: text
    });
    const out = await res.json();
    evt.target.value = '';
    if (!res.ok) alert(out.error || 'Archivo JSON inválido.');
    else {
      document.getElementById('update-feedback').innerHTML = `<span style="color:#6ee7b7;">✅ Perfil importado: ${escapeHtml(out.name)}</span>`;
      loadProfilesList();
    }
  }

  async function updateFromGitHub() {
    const fb = document.getElementById('update-feedback');
    fb.innerHTML = '<span style="color:#93c5fd;">⏳ Consultando GitHub (ulibanus/Resiticks)...</span>';
    try {
      const res = await fetch('/api/update/github', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) fb.innerHTML = `<span style="color:#fca5a5;">❌ ${escapeHtml(data.error)}</span>`;
      else fb.innerHTML = `<span style="color:#6ee7b7;">✅ ${escapeHtml(data.message)}</span>`;
      loadProfilesList();
    } catch (e) {
      fb.innerHTML = '<span style="color:#fca5a5;">❌ Error de red consultando GitHub.</span>';
    }
  }

  async function loadDiagnostics() {
    try {
      const res = await fetch('/api/system/diagnose');
      const d = await res.json();
      const el = document.getElementById('diag-content');
      const ok = v => v ? '<span style="color:#34d399;">✅ OK</span>' : '<span style="color:#fca5a5;">❌ Falta / Sin permiso</span>';
      let usbHtml = '<span style="color:#34d399;">✅ Sin errores de energía ni -71/-32 detectados</span>';
      if (!d.usb_log_readable) {
        usbHtml = '<span style="color:#fcd34d;">ℹ️ dmesg restringido por el kernel (ejecutá <code>sudo dmesg | grep -i usb</code> para revisar).</span>';
      } else if (d.usb_errors && d.usb_errors.length > 0) {
        usbHtml = '<span style="color:#fca5a5;">⚠️ Errores USB detectados (posible hub pasivo sobrecargado):</span><div class="code-box">' +
          d.usb_errors.map(x => escapeHtml(x)).join('<br>') + '</div>';
      }

      const devHtml = (d.device_checks || []).map(c =>
        `<div class="diag-item"><span>${escapeHtml(c.name)} (<code>${escapeHtml(c.dev_path)}</code>)</span><span>R:${c.readable?'✅':'❌'} W(Rumble):${c.writable?'✅':'⚠️'}</span></div>`
      ).join('') || '<div style="color:var(--text-muted);">No hay mandos físicos conectados ahora.</div>';

      el.innerHTML = `
        <div class="diag-card">
          <h3>🔑 Permisos Kernel &amp; udev</h3>
          <div class="diag-item"><span>Usuario</span><strong>${escapeHtml(d.username)}</strong></div>
          <div class="diag-item"><span>/dev/uinput existe</span>${ok(d.uinput_exists)}</div>
          <div class="diag-item"><span>/dev/uinput R/W</span>${ok(d.uinput_rw)}</div>
          <div class="diag-item"><span>Grupo "input"</span>${ok(d.in_input_group)}</div>
          <div class="diag-item"><span>Regla udev Resiticks</span>${ok(d.udev_installed)}</div>
          ${(!d.uinput_rw || !d.in_input_group) ? '<div class="code-box">sudo ./instalar_sistema_linux.sh</div>' : ''}
        </div>
        <div class="diag-card">
          <h3>⚡ Bus USB &amp; Hub</h3>
          <div class="diag-item"><span>usbcore.old_scheme_first</span><code>${escapeHtml(d.usbcore_old_scheme_first ?? 'N/D')}</code></div>
          <div style="margin-top:8px;">${usbHtml}</div>
        </div>
        <div class="diag-card">
          <h3>🎮 Mandos Físicos Detectados</h3>
          ${devHtml}
        </div>
      `;
    } catch (e) {}
  }

  // ---- Web Calibration Modal ----
  function openCalibrationPicker() {
    document.getElementById('cal-modal').classList.add('open');
    document.getElementById('cal-picker-view').style.display = 'block';
    document.getElementById('cal-wizard-view').style.display = 'none';
    document.getElementById('cal-save-view').style.display = 'none';
    const listEl = document.getElementById('cal-device-list');
    const devs = (lastStatusData && lastStatusData.connected_devices) || [];
    if (devs.length === 0) {
      listEl.innerHTML = '<div style="color:#fcd34d;">⚠️ No hay ningún joystick conectado ahora. Enchufá uno por USB/Bluetooth y reintentá.</div>';
      return;
    }
    listEl.innerHTML = devs.map(gp => `
      <div style="display:flex; justify-content:space-between; align-items:center; background:#0b1120; border:1px solid #24324f; border-radius:8px; padding:10px;">
        <div>
          <strong>🎮 ${escapeHtml(gp.name)}</strong>
          <div style="font-size:11px; color:var(--text-muted);">VID:PID <code>${escapeHtml(gp.vendor)}:${escapeHtml(gp.product)}</code> • ${escapeHtml(gp.dev_path)}</div>
        </div>
        <button class="btn" data-dev="${escapeHtml(gp.dev_path)}" data-name="${escapeHtml(gp.name)}" onclick="startWebCalibration(this.dataset.dev, this.dataset.name)">Calibrar</button>
      </div>
    `).join('');
  }

  async function startWebCalibration(devPath, name) {
    document.getElementById('cal-modal').classList.add('open');
    document.getElementById('cal-picker-view').style.display = 'none';
    document.getElementById('cal-wizard-view').style.display = 'block';
    document.getElementById('cal-save-view').style.display = 'none';
    document.getElementById('cal-title').textContent = '🎯 Calibrando: ' + (name || devPath);

    const res = await fetch('/api/calibrate/web/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dev_path: devPath })
    });
    const st = await res.json();
    if (!res.ok) {
      alert(st.error || 'No se pudo iniciar calibración.');
      cancelWebCalibration();
      return;
    }
    renderCalibrationState(st);
    if (calPollTimer) clearInterval(calPollTimer);
    calPollTimer = setInterval(pollWebCalibration, 80);
  }

  async function pollWebCalibration() {
    try {
      const res = await fetch('/api/calibrate/web/poll');
      if (!res.ok) return;
      const st = await res.json();
      renderCalibrationState(st);
    } catch (e) {}
  }

  function renderCalibrationState(st) {
    if (st.completed) {
      if (calPollTimer) { clearInterval(calPollTimer); calPollTimer = null; }
      document.getElementById('cal-wizard-view').style.display = 'none';
      document.getElementById('cal-save-view').style.display = 'block';
      document.getElementById('cal-custom-name').value = st.default_name || '';
      const warns = st.warnings || [];
      document.getElementById('cal-consistency-warnings').innerHTML = warns.length
        ? '⚠️ Advertencias detectadas:<br>' + warns.map(w => '• ' + escapeHtml(w)).join('<br>')
        : '';
      return;
    }

    const total = st.total_steps || 25;
    const idx = st.step_idx || 0;
    document.getElementById('cal-progress-fill').style.width = Math.round((idx / total) * 100) + '%';
    const step = st.current_step || {};
    document.getElementById('cal-step-counter').textContent = `Paso ${idx + 1} / ${total}`;
    document.getElementById('cal-step-prompt').textContent = step.prompt || '';
    document.getElementById('btn-cal-skip').style.display = step.allow_skip ? 'inline-block' : 'none';

    const wBox = document.getElementById('cal-warning-box');
    const keepBtn = document.getElementById('btn-cal-keep');
    if (st.warning) {
      wBox.style.display = 'block';
      wBox.textContent = '⚠️ ' + st.warning;
      keepBtn.style.display = 'inline-block';
    } else {
      wBox.style.display = 'none';
      keepBtn.style.display = 'none';
    }

    const steps = st.steps || [];
    const mapped = st.mapped_keys || [];
    let leftHtml = '', rightHtml = '';
    steps.forEach((s, i) => {
      const cls = i === idx ? 'current' : (mapped.includes(s.key) ? 'done' : '');
      const status = i === idx ? '👈 Ahora' : (mapped.includes(s.key) ? '✓' : '—');
      const row = `<div class="pes-step ${cls}"><span>${escapeHtml(s.badge)}</span><span>${status}</span></div>`;
      if (s.col === 'left') leftHtml += row;
      else rightHtml += row;
    });
    document.getElementById('pes-col-left').innerHTML = leftHtml;
    document.getElementById('pes-col-right').innerHTML = rightHtml;
  }

  async function calSkipStep() {
    const res = await fetch('/api/calibrate/web/skip', { method: 'POST' });
    if (res.ok) renderCalibrationState(await res.json());
  }

  async function calPrevStep() {
    const res = await fetch('/api/calibrate/web/prev', { method: 'POST' });
    if (res.ok) renderCalibrationState(await res.json());
  }

  async function calAcceptWarning() {
    const res = await fetch('/api/calibrate/web/accept_warning', { method: 'POST' });
    if (res.ok) renderCalibrationState(await res.json());
  }

  async function calSaveProfile() {
    const customName = document.getElementById('cal-custom-name').value.trim();
    const res = await fetch('/api/calibrate/web/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: customName })
    });
    if (res.ok) {
      cancelWebCalibration();
      loadProfilesList();
    }
  }

  async function cancelWebCalibration() {
    if (calPollTimer) { clearInterval(calPollTimer); calPollTimer = null; }
    document.getElementById('cal-modal').classList.remove('open');
    try { await fetch('/api/calibrate/web/cancel', { method: 'POST' }); } catch (e) {}
  }

  setInterval(updateDashboard, 90);
  updateDashboard();
  loadProfilesList();
</script>
</body>
</html>
"""
