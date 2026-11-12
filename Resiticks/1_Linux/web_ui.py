#!/usr/bin/env python3
"""
HTML/CSS/JS Web UI template for Resiticks Studio (Telemetry Studio HUD layout,
8 slots, Master Slider Bridge Toggle, Realtime Inspector, Web PES Calibration,
Anti-Drift deadzone tuning, Slot Swapping, USB Diagnostics, GitHub Updater).
"""

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Resiticks Studio — Hub Universal de Joysticks</title>
<style>
  :root {
    --bg-base: #060a13;
    --bg-header: #0c1322;
    --bg-panel: #0d1424;
    --bg-card: #101829;
    --bg-inset: #080d18;
    --card-border: #1c2742;
    --card-border-light: #253454;
    --primary: #3b82f6;
    --primary-hover: #2563eb;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --text: #f8fafc;
    --text-muted: #64748b;
    --text-sub: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: var(--bg-base); color: var(--text); height: 100vh; overflow: hidden; display: flex; flex-direction: column; font-size: 13px; }

  /* Top Command Bar */
  header {
    height: 62px; background: var(--bg-header); border-bottom: 1px solid var(--card-border);
    padding: 0 20px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
  }
  .h-left { display: flex; align-items: center; gap: 20px; }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 17px; color: #fff; letter-spacing: -0.3px; }
  .brand-icon {
    width: 32px; height: 32px; border-radius: 9px;
    background: linear-gradient(135deg, #3b82f6, #1d4ed8);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 16px rgba(59,130,246,0.45);
  }
  .segmented { background: #070b14; border: 1px solid var(--card-border); padding: 4px; border-radius: 9px; display: flex; gap: 4px; }
  .tab-btn {
    background: transparent; color: var(--text-muted); border: 1px solid transparent;
    padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; transition: 0.15s;
    display: inline-flex; align-items: center; gap: 6px;
  }
  .tab-btn.active { background: #18233b; color: #60a5fa; border-color: rgba(59,130,246,0.3); }

  .h-right { display: flex; align-items: center; gap: 12px; }

  /* Master Bridge Slider Toggle (de Opción 1 integrado en Header) */
  .bridge-master-toggle {
    display: flex; align-items: center; gap: 12px;
    background: linear-gradient(180deg, rgba(16,185,129,0.14), rgba(16,185,129,0.04));
    border: 1px solid rgba(16,185,129,0.35); border-radius: 10px;
    padding: 6px 14px; cursor: pointer; user-select: none; transition: 0.2s;
  }
  .bridge-master-toggle.paused {
    background: linear-gradient(180deg, rgba(245,158,11,0.14), rgba(245,158,11,0.04));
    border-color: rgba(245,158,11,0.35);
  }
  .bridge-text-group { display: flex; flex-direction: column; }
  .bridge-badge-label {
    display: flex; align-items: center; gap: 6px;
    font-size: 11px; font-weight: 800; letter-spacing: 0.05em; color: #6ee7b7; text-transform: uppercase;
  }
  .bridge-master-toggle.paused .bridge-badge-label { color: #fde68a; }
  .pulse-dot { width: 7px; height: 7px; border-radius: 50%; background: #10b981; box-shadow: 0 0 0 3px rgba(16,185,129,0.25); }
  .bridge-master-toggle.paused .pulse-dot { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245,158,11,0.25); }
  .bridge-sub-info { font-size: 10px; color: var(--text-sub); }

  .switch-track {
    width: 44px; height: 24px; background: #10b981; border-radius: 99px;
    position: relative; transition: background 0.2s; flex-shrink: 0;
  }
  .bridge-master-toggle.paused .switch-track { background: #334155; }
  .switch-thumb {
    position: absolute; width: 18px; height: 18px; border-radius: 50%; background: #fff;
    top: 3px; right: 3px; transition: transform 0.2s; box-shadow: 0 2px 5px rgba(0,0,0,0.3);
  }
  .bridge-master-toggle.paused .switch-thumb { transform: translateX(-20px); }

  .btn {
    background: var(--primary); color: #fff; border: none; padding: 7px 13px;
    border-radius: 7px; font-weight: 600; font-size: 12px; cursor: pointer;
    text-decoration: none; display: inline-flex; align-items: center; gap: 6px; transition: 0.15s;
  }
  .btn:hover { filter: brightness(1.1); }
  .btn-ghost { background: #131c31; border: 1px solid var(--card-border-light); color: #cbd5e1; }
  .btn-ghost:hover { background: #1c2742; }
  .btn-small {
    background: #1e293b; color: #cbd5e1; border: 1px solid #334155;
    padding: 4px 9px; border-radius: 5px; font-size: 11px; cursor: pointer; font-weight: 600;
  }
  .btn-small:hover { background: #334155; color: #fff; }

  /* Banners */
  .alert-banner { display: none; padding: 9px 18px; font-size: 12px; flex-shrink: 0; }
  .alert-banner.warn { display: flex; align-items: center; justify-content: space-between; background: rgba(245,158,11,0.12); border-bottom: 1px solid #d97706; color: #fde68a; }
  .alert-banner.error { display: block; background: rgba(239,68,68,0.14); border-bottom: 1px solid #ef4444; color: #fecaca; }

  /* Tab Viewports */
  .tab-content { display: none; flex: 1; overflow: hidden; }
  .tab-content.active { display: flex; }

  /* Dashboard Viewport: Split Roster & Inspector */
  #tab-dashboard { display: grid; grid-template-columns: 1fr 470px; }
  @media (max-width: 1024px) { #tab-dashboard { grid-template-columns: 1fr; } .inspector { display: none; } }

  .left-pane { padding: 16px 20px; display: flex; flex-direction: column; gap: 12px; border-right: 1px solid var(--card-border); overflow-y: auto; }
  .section-bar { display: flex; justify-content: space-between; align-items: center; }
  .section-title { font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); }
  .mini-metrics { display: flex; gap: 14px; font-size: 11px; color: var(--text-sub); font-family: ui-monospace, monospace; }
  .mini-metrics b { color: #38bdf8; }

  /* Roster 2x2 */
  .roster-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  @media (max-width: 720px) { .roster-grid { grid-template-columns: 1fr; } }

  .slot-card {
    background: var(--bg-panel); border: 1px solid var(--card-border); border-radius: 12px;
    padding: 13px; display: flex; flex-direction: column; gap: 9px; cursor: pointer; transition: 0.15s;
    position: relative; overflow: hidden;
  }
  .slot-card:hover { border-color: #2e4370; }
  .slot-card.selected {
    background: linear-gradient(145deg, #131e36, #0f172a);
    border-color: var(--primary); box-shadow: 0 0 0 1px rgba(59,130,246,0.35), 0 10px 24px rgba(0,0,0,0.35);
  }
  .slot-card::before {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
    background: var(--slot-color, #3b82f6);
  }
  .slot-card.empty-slot {
    cursor: default; opacity: 0.65; border-style: dashed; background: #080d18;
  }
  .slot-card.empty-slot:hover { border-color: var(--card-border); }

  .tile-top { display: flex; justify-content: space-between; align-items: center; }
  .tile-tag { font-size: 10.5px; font-weight: 800; padding: 2px 7px; border-radius: 4px; background: #18233b; color: var(--text-sub); }
  .slot-card.selected .tile-tag { background: var(--primary); color: #fff; }
  .tile-title { font-size: 13.5px; font-weight: 700; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tile-sub { font-size: 11px; color: var(--text-muted); font-family: ui-monospace, monospace; }

  .tile-live-row {
    background: var(--bg-inset); border: 1px solid #162036; border-radius: 8px;
    padding: 8px 10px; display: flex; align-items: center; justify-content: space-between;
  }
  .mini-sticks { display: flex; gap: 10px; }
  .mini-stick-ring { width: 38px; height: 38px; border-radius: 50%; border: 1px solid #283858; background: #0d1424; position: relative; }
  .mini-dot { width: 8px; height: 8px; border-radius: 50%; background: #60a5fa; position: absolute; top: 15px; left: 15px; transform: translate(0, 0); box-shadow: 0 0 6px #3b82f6; }
  .mini-face-btns { display: flex; gap: 4px; }
  .m-face-btn { width: 19px; height: 19px; border-radius: 50%; border: 1px solid #29395a; background: #111a2e; font-size: 8.5px; font-weight: 800; color: #64748b; display: flex; align-items: center; justify-content: center; }
  .m-face-btn.pressed { background: #10b981; color: #fff; border-color: #34d399; }
  .m-face-btn.pressed-y { background: #f59e0b; color: #fff; border-color: #fbbf24; }

  .tile-foot { display: flex; justify-content: space-between; align-items: center; font-size: 10.5px; color: var(--text-muted); }
  .drift-pill { font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; background: rgba(16,185,129,0.12); color: #34d399; }
  .drift-pill.drift { background: rgba(245,158,11,0.14); color: #fbbf24; }

  /* Extra Slots Dock 5-8 */
  .extra-slots-bar {
    margin-top: auto; background: #0a101d; border: 1px solid var(--card-border);
    border-radius: 10px; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center;
  }
  .extra-pills { display: flex; gap: 8px; }
  .extra-pill {
    background: #11192c; border: 1px solid #1f2d4a; border-radius: 6px;
    padding: 5px 11px; font-size: 11px; color: #64748b; cursor: pointer; transition: 0.15s;
  }
  .extra-pill.occupied { color: #6ee7b7; border-color: rgba(16,185,129,0.3); background: rgba(16,185,129,0.08); font-weight: 700; }
  .extra-pill.selected { border-color: var(--primary); color: #60a5fa; background: rgba(59,130,246,0.15); }

  /* Right Pane: Inspector */
  .inspector {
    background: #090f1d; padding: 18px 22px; display: flex; flex-direction: column;
    gap: 13px; overflow-y: auto;
  }
  .insp-header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid var(--card-border); padding-bottom: 12px; }
  .insp-tag { font-size: 10.5px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; color: var(--primary); margin-bottom: 3px; }
  .insp-title { font-size: 16px; font-weight: 800; color: #fff; }
  .insp-sub { font-size: 11px; color: var(--text-muted); font-family: ui-monospace, monospace; margin-top: 2px; }

  .scopes-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .scope-box { background: var(--bg-card); border: 1px solid var(--card-border); border-radius: 10px; padding: 10px; text-align: center; }
  .scope-lbl { font-size: 10.5px; font-weight: 700; color: var(--text-sub); text-transform: uppercase; }
  .scope-radar {
    width: 104px; height: 104px; border-radius: 50%; margin: 8px auto;
    background: radial-gradient(circle, #131d33 0%, #070b14 75%);
    border: 1px solid #2a3c60; position: relative;
  }
  .cross-h { position: absolute; left: 8px; right: 8px; top: 50%; height: 1px; background: rgba(148,163,184,0.18); }
  .cross-v { position: absolute; top: 8px; bottom: 8px; left: 50%; width: 1px; background: rgba(148,163,184,0.18); }
  .scope-dz-ring { position: absolute; border-radius: 50%; border: 1px dashed rgba(239,68,68,0.7); top: 50%; left: 50%; transform: translate(-50%, -50%); pointer-events: none; }
  .scope-dot { width: 12px; height: 12px; border-radius: 50%; background: #3b82f6; box-shadow: 0 0 10px #3b82f6; position: absolute; top: 46px; left: 46px; transform: translate(0, 0); }
  .scope-coords { font-family: ui-monospace, monospace; font-size: 10.5px; color: var(--text-muted); }

  /* Triggers and Dpad in Inspector */
  .insp-triggers-bar { display: grid; grid-template-columns: 32px 1fr 1fr 32px; gap: 6px; align-items: center; }
  .insp-bumper { background: #141d33; border: 1px solid #253454; color: var(--text-sub); font-size: 10px; font-weight: 800; padding: 5px 0; border-radius: 5px; text-align: center; }
  .insp-bumper.pressed { background: var(--primary); color: #fff; border-color: #60a5fa; }
  .insp-trig-track { height: 20px; background: #141d33; border: 1px solid #253454; border-radius: 5px; position: relative; overflow: hidden; }
  .insp-trig-fill { height: 100%; width: 0%; background: linear-gradient(90deg, #10b981, #34d399); transition: width 0.04s; }
  .insp-trig-text { position: absolute; inset: 0; font-size: 10px; font-weight: 700; display: flex; align-items: center; justify-content: center; color: #e2e8f0; }

  /* Tuning Card */
  .insp-tuning { background: var(--bg-card); border: 1px solid var(--card-border); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 10px; font-size: 11.5px; }
  .insp-tune-head { display: flex; justify-content: space-between; font-weight: 700; color: #cbd5e1; }
  .tune-slider-block { display: flex; flex-direction: column; gap: 4px; }
  .tune-slider-block div { display: flex; justify-content: space-between; color: var(--text-sub); }
  .tune-slider-block input[type="range"] { accent-color: var(--primary); width: 100%; cursor: pointer; }

  /* Inspector Actions */
  .insp-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: auto; }
  .insp-btn {
    background: #152038; border: 1px solid #263659; color: #e2e8f0; padding: 9px;
    border-radius: 8px; font-size: 11.5px; font-weight: 600; cursor: pointer; text-align: center; transition: 0.15s;
  }
  .insp-btn:hover { background: #1f2f52; }
  .insp-btn.primary { background: rgba(59,130,246,0.18); border-color: #3b82f6; color: #60a5fa; }

  /* Library & Diagnostics Views */
  #tab-profiles, #tab-diagnostics {
    padding: 24px; flex-direction: column; gap: 16px; overflow-y: auto; width: 100%;
  }
  table { width: 100%; border-collapse: collapse; margin-top: 10px; background: var(--bg-panel); border-radius: 10px; overflow: hidden; border: 1px solid var(--card-border); }
  th { text-align: left; padding: 11px 14px; background: #131d33; color: var(--text-muted); border-bottom: 1px solid var(--card-border); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
  td { padding: 12px 14px; border-bottom: 1px solid var(--card-border); font-size: 12px; }

  .diag-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; margin-top: 6px; }
  .diag-card { background: var(--bg-card); border: 1px solid var(--card-border); border-radius: 10px; padding: 16px; }
  .diag-card h3 { font-size: 14px; margin-bottom: 10px; color: #60a5fa; display: flex; align-items: center; gap: 8px; }
  .diag-item { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #1a253e; font-size: 12px; }
  .code-box { background: #080d18; border: 1px solid var(--card-border); border-radius: 6px; padding: 8px; font-family: ui-monospace, monospace; font-size: 11px; color: #93c5fd; margin-top: 8px; word-break: break-all; }

  /* Web Calibration Modal */
  .modal-backdrop { display: none; position: fixed; inset: 0; background: rgba(2, 6, 23, 0.85); z-index: 100; align-items: center; justify-content: center; padding: 16px; }
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
  <div class="h-left">
    <div class="brand">
      <div class="brand-icon">
        <svg width="18" height="18" fill="none" stroke="#fff" stroke-width="2.3" viewBox="0 0 24 24"><path d="M6 12h4m-2-2v4m7-1h.01M18 11h.01M4 8a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4l1.2 7.2a2.5 2.5 0 0 1-4.3 2.1L15 15H9l-1.9 2.3a2.5 2.5 0 0 1-4.3-2.1L4 8Z"/></svg>
      </div>
      Resiticks Studio
    </div>
    <div class="segmented">
      <button class="tab-btn active" onclick="switchTab('tab-dashboard', this)">🏟️ Monitor &amp; Slots</button>
      <button class="tab-btn" onclick="switchTab('tab-profiles', this)">📁 Biblioteca</button>
      <button class="tab-btn" onclick="switchTab('tab-diagnostics', this)">🩺 Diagnóstico USB</button>
    </div>
  </div>

  <div class="h-right">
    <!-- Master Bridge Toggle Switch -->
    <div id="bridge-master-toggle" class="bridge-master-toggle" onclick="toggleBridge()">
      <div class="bridge-text-group">
        <div id="bridge-status-badge" class="bridge-badge-label"><span class="pulse-dot"></span> Modo Puente ON</div>
        <div id="bridge-sub-text" class="bridge-sub-info">Xbox 360 virtual activo</div>
      </div>
      <div class="switch-track">
        <div class="switch-thumb"></div>
      </div>
    </div>

    <button class="btn" style="background:#0ea5e9;" onclick="openCalibrationPicker()">🎯 Calibrar Mando</button>
    <button class="btn btn-ghost" onclick="updateFromGitHub()">🔄 Actualizar</button>
    <a href="/api/export_pack" class="btn btn-ghost">📦 Exportar .ZIP</a>
  </div>
</header>

<div id="conn-banner" class="alert-banner"></div>
<div id="errors-banner" class="alert-banner"></div>
<div id="uncal-banner" class="alert-banner"></div>

<!-- Vista 1: Dashboard Studio -->
<div id="tab-dashboard" class="tab-content active">
  <section class="left-pane">
    <div class="section-bar">
      <span class="section-title">Slots Principales (1–4)</span>
      <div class="mini-metrics">
        <span>Polling: <b id="metrics-polling-hz">-- Hz</b></span>
        <span>Latencia: <b>&lt;1 ms</b></span>
        <span>Motor: <b id="metrics-vpad-count">0 Activos</b></span>
      </div>
    </div>

    <!-- Slots 1 al 4 -->
    <div class="roster-grid" id="slots-container"></div>

    <!-- Slots de Expansión 5 al 8 -->
    <div class="extra-slots-bar">
      <span style="font-size:11px; font-weight:700; color:var(--text-muted);">SLOTS DE EXPANSIÓN (TORNEO 8 JUGADORES)</span>
      <div class="extra-pills" id="extra-slots-pills"></div>
    </div>
  </section>

  <!-- Inspector en Vivo (Derecha) -->
  <aside class="inspector" id="inspector-pane">
    <div class="insp-header">
      <div>
        <div class="insp-tag" id="insp-tag-text">Inspector en Vivo · Slot 1</div>
        <div class="insp-title" id="insp-name-text">Sin Mando Seleccionado</div>
        <div class="insp-sub" id="insp-sub-text">Conectá un joystick para inspeccionar</div>
      </div>
      <span id="insp-cal-badge" style="background:#064e3b; color:#6ee7b7; font-size:10.5px; font-weight:700; padding:3px 8px; border-radius:5px;">Calibrado</span>
    </div>

    <div class="scopes-grid">
      <div class="scope-box">
        <div class="scope-lbl">Stick Izquierdo</div>
        <div class="scope-radar">
          <div class="cross-h"></div><div class="cross-v"></div>
          <div id="insp-scope-dz-l" class="scope-dz-ring" style="width:24px; height:24px;"></div>
          <div id="insp-scope-dot-l" class="scope-dot"></div>
        </div>
        <div id="insp-coords-l" class="scope-coords">X: 0.00 &nbsp; Y: 0.00</div>
      </div>
      <div class="scope-box">
        <div class="scope-lbl">Stick Derecho</div>
        <div class="scope-radar">
          <div class="cross-h"></div><div class="cross-v"></div>
          <div id="insp-scope-dz-r" class="scope-dz-ring" style="width:24px; height:24px;"></div>
          <div id="insp-scope-dot-r" class="scope-dot"></div>
        </div>
        <div id="insp-coords-r" class="scope-coords">X: 0.00 &nbsp; Y: 0.00</div>
      </div>
    </div>

    <div class="insp-triggers-bar">
      <div id="insp-btn-lb" class="insp-bumper">LB</div>
      <div class="insp-trig-track">
        <div id="insp-fill-lt" class="insp-trig-fill"></div>
        <div id="insp-txt-lt" class="insp-trig-text">LT 0%</div>
      </div>
      <div class="insp-trig-track">
        <div id="insp-fill-rt" class="insp-trig-fill"></div>
        <div id="insp-txt-rt" class="insp-trig-text">RT 0%</div>
      </div>
      <div id="insp-btn-rb" class="insp-bumper">RB</div>
    </div>

    <div class="insp-tuning">
      <div class="insp-tune-head">
        <span>Ajuste Anti-Drift &amp; Respuesta Pro</span>
        <span id="insp-tune-slot-lbl" style="color:#60a5fa;">Slot 1</span>
      </div>
      <div class="tune-slider-block">
        <div><span>Zona Muerta Stick Izq (L):</span><b id="insp-val-dzl">8%</b></div>
        <input type="range" id="insp-input-dzl" min="2" max="30" value="8" oninput="onInspDeadzoneInput('left', this.value)" onchange="onInspDeadzoneChange('left', this.value)">
      </div>
      <div class="tune-slider-block">
        <div><span>Zona Muerta Stick Der (R):</span><b id="insp-val-dzr">8%</b></div>
        <input type="range" id="insp-input-dzr" min="2" max="30" value="8" oninput="onInspDeadzoneInput('right', this.value)" onchange="onInspDeadzoneChange('right', this.value)">
      </div>
      <div class="tune-slider-block">
        <div><span>Alcance Diagonal (Outer Scale):</span><b id="insp-val-outer">100%</b></div>
        <input type="range" id="insp-input-outer" min="100" max="135" value="100" oninput="document.getElementById('insp-val-outer').textContent=this.value+'%'" onchange="onInspProTune({outer_scale: Number(this.value)/100})">
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
        <span style="color:var(--text-sub);">Curva Stick:</span>
        <select id="insp-sel-curve" onchange="onInspProTune({sensitivity_curve: this.value})" style="background:#18233b; color:#e2e8f0; border:1px solid #2b3c63; border-radius:6px; padding:4px 8px; font-size:11.5px;">
          <option value="linear">Lineal (Estándar)</option>
          <option value="precise">Precisión PES (Suave)</option>
          <option value="aggressive">Rápida (Agresiva)</option>
        </select>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; padding-top:2px;">
        <label style="display:flex; align-items:center; gap:6px; cursor:pointer; color:var(--text-sub);">
          <input type="checkbox" id="insp-chk-nintendo" onchange="onInspProTune({nintendo_swap: this.checked})">
          <span>Layout Nintendo (A↔B, X↔Y)</span>
        </label>
        <label style="display:flex; align-items:center; gap:6px; cursor:pointer; color:var(--text-sub);">
          <input type="checkbox" id="insp-chk-trigswap" onchange="onInspProTune({trigger_bumper_swap: this.checked})">
          <span>PS2 (LT↔LB)</span>
        </label>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; padding-top:4px; border-top:1px solid #1a2540;">
        <label style="display:flex; align-items:center; gap:6px; cursor:pointer;">
          <input type="checkbox" id="insp-chk-rumble" onchange="onInspRumbleChange(this.checked)">
          <span>📳 Vibración (Rumble)</span>
        </label>
        <span id="insp-lbl-rumble" style="color:#34d399; font-weight:700;">Activa</span>
      </div>
    </div>

    <div class="insp-actions">
      <div class="insp-btn primary" onclick="inspRecalibrate()">🎯 Recalibrar PES</div>
      <div class="insp-btn" onclick="inspCenterZero()">⊕ Centrar Sticks</div>
      <div class="insp-btn" onclick="inspPromptMoveSlot()">⇄ Mover Slot</div>
      <div class="insp-btn" onclick="inspTestRumble()">📳 Probar Vibración</div>
      <div class="insp-btn" style="grid-column:span 2;" onclick="inspPinSlot()">📌 Fijar Puerto USB al Slot</div>
    </div>
  </aside>
</div>

<!-- Vista 2: Biblioteca de Perfiles -->
<div id="tab-profiles" class="tab-content">
  <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 6px;">
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
      <a href="/api/export_pack" class="btn" style="background:#10b981;">📦 Descargar Pack ZIP Completo</a>
    </div>
  </div>
  <div id="update-feedback" style="margin-bottom: 8px; font-size: 12px;"></div>
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

<!-- Vista 3: Diagnóstico USB -->
<div id="tab-diagnostics" class="tab-content">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
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
        <button class="btn" style="background:#10b981;" onclick="calSaveProfile()">💾 Guardar Perfil</button>
      </div>
    </div>
  </div>
</div>

<script>
  let lastSlotsSig = '';
  let lastProfilesRev = -1;
  let failCount = 0;
  let lastStatusData = null;
  let calPollTimer = null;
  let selectedSlot = 1;

  const SLOT_COLORS = {
    1: '#3b82f6',
    2: '#10b981',
    3: '#f59e0b',
    4: '#8b5cf6',
    5: '#06b6d4',
    6: '#ec4899',
    7: '#14b8a6',
    8: '#f97316'
  };

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
    const box = document.getElementById('bridge-master-toggle');
    const badge = document.getElementById('bridge-status-badge');
    const sub = document.getElementById('bridge-sub-text');
    if (enabled) {
      box.classList.remove('paused');
      badge.innerHTML = '<span class="pulse-dot"></span> Modo Puente ON';
      sub.textContent = 'Xbox 360 virtual activo';
    } else {
      box.classList.add('paused');
      badge.innerHTML = '<span class="pulse-dot"></span> Puente Pausado';
      sub.textContent = 'Modo Monitor (sin bloqueo)';
    }
  }

  function selectSlot(slot) {
    selectedSlot = Number(slot);
    document.querySelectorAll('.slot-card').forEach(c => c.classList.remove('selected'));
    const sc = document.getElementById('slot-card-' + selectedSlot);
    if (sc) sc.classList.add('selected');

    document.querySelectorAll('.extra-pill').forEach(p => {
      const s = Number(p.dataset.slot);
      p.classList.toggle('selected', s === selectedSlot);
    });

    updateInspectorCardHeader();
  }

  function updateInspectorCardHeader() {
    const data = lastStatusData;
    const it = data && (data.active_slots[String(selectedSlot)] || data.active_slots[selectedSlot]);
    const tag = document.getElementById('insp-tag-text');
    const name = document.getElementById('insp-name-text');
    const sub = document.getElementById('insp-sub-text');
    const badge = document.getElementById('insp-cal-badge');
    const slotLbl = document.getElementById('insp-tune-slot-lbl');

    tag.textContent = `Inspector en Vivo · Slot ${selectedSlot}`;
    slotLbl.textContent = `Slot ${selectedSlot}`;

    if (it) {
      name.textContent = it.name || 'Mando USB';
      sub.textContent = `${it.vendor}:${it.product} · ${it.dev_path} · Xbox #${selectedSlot}`;
      badge.style.display = 'inline-block';
      badge.textContent = 'Calibrado';
      badge.style.background = '#064e3b';
      badge.style.color = '#6ee7b7';

      const dzL = Math.round((it.deadzone_left ?? 0.05) * 100);
      const dzR = Math.round((it.deadzone_right ?? 0.05) * 100);
      const rumOn = it.rumble_enabled !== false;

      // Update tuning inputs only if user is not actively dragging
      if (document.activeElement !== document.getElementById('insp-input-dzl')) {
        document.getElementById('insp-input-dzl').value = dzL;
        document.getElementById('insp-val-dzl').textContent = dzL + '%';
      }
      if (document.activeElement !== document.getElementById('insp-input-dzr')) {
        document.getElementById('insp-input-dzr').value = dzR;
        document.getElementById('insp-val-dzr').textContent = dzR + '%';
      }
      const outerPct = Math.round((it.outer_scale ?? 1.0) * 100);
      if (document.activeElement !== document.getElementById('insp-input-outer')) {
        document.getElementById('insp-input-outer').value = outerPct;
        document.getElementById('insp-val-outer').textContent = outerPct + '%';
      }
      document.getElementById('insp-sel-curve').value = it.sensitivity_curve || 'linear';
      document.getElementById('insp-chk-nintendo').checked = Boolean(it.nintendo_swap);
      document.getElementById('insp-chk-trigswap').checked = Boolean(it.trigger_bumper_swap);
      document.getElementById('insp-chk-rumble').checked = rumOn;
      document.getElementById('insp-lbl-rumble').textContent = rumOn ? 'Activa' : 'Pausada';
      document.getElementById('insp-lbl-rumble').style.color = rumOn ? '#34d399' : '#94a3b8';
    } else {
      name.textContent = '(Slot Libre)';
      sub.textContent = 'No hay joystick físico asignado a este slot';
      badge.style.display = 'none';
    }
  }

  async function onInspProTune(payload) {
    const data = lastStatusData;
    const it = data && (data.active_slots[String(selectedSlot)] || data.active_slots[selectedSlot]);
    if (!it) return;
    await fetch('/api/profile/tune', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({ vendor: it.vendor, product: it.product }, payload))
    });
  }

  async function inspTestRumble() {
    const res = await fetch('/api/slot/test_rumble', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slot: selectedSlot })
    });
    const out = await res.json();
    if (!res.ok) alert(out.error || 'No se pudo probar vibración.');
    else if (out.ok === false) alert(out.message || 'El mando no reporta soporte de vibración.');
  }

  function onInspDeadzoneInput(side, val) {
    if (side === 'left') document.getElementById('insp-val-dzl').textContent = val + '%';
    else document.getElementById('insp-val-dzr').textContent = val + '%';
  }

  async function onInspDeadzoneChange(side, val) {
    const data = lastStatusData;
    const it = data && (data.active_slots[String(selectedSlot)] || data.active_slots[selectedSlot]);
    if (!it) return;
    const payload = {};
    if (side === 'left') payload.deadzone_left = Number(val) / 100;
    else payload.deadzone_right = Number(val) / 100;
    await fetch('/api/profile/tune', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({ vendor: it.vendor, product: it.product }, payload))
    });
  }

  async function onInspRumbleChange(checked) {
    const data = lastStatusData;
    const it = data && (data.active_slots[String(selectedSlot)] || data.active_slots[selectedSlot]);
    if (!it) return;
    document.getElementById('insp-lbl-rumble').textContent = checked ? 'Activa' : 'Pausada';
    document.getElementById('insp-lbl-rumble').style.color = checked ? '#34d399' : '#94a3b8';
    await fetch('/api/profile/tune', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vendor: it.vendor, product: it.product, rumble_enabled: checked })
    });
  }

  function inspRecalibrate() {
    const data = lastStatusData;
    const it = data && (data.active_slots[String(selectedSlot)] || data.active_slots[selectedSlot]);
    if (!it) { alert('Seleccioná un slot con mando conectado para recalibrar.'); return; }
    startWebCalibration(it.dev_path, it.name);
  }

  async function inspCenterZero() {
    const res = await fetch('/api/profile/center_zero', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slot: selectedSlot })
    });
    if (!res.ok) alert('No se pudo centrar los sticks.');
  }

  async function inspPromptMoveSlot() {
    const target = prompt(`Mover mando de Jugador P${selectedSlot} al Slot (1-8):`, selectedSlot === 1 ? '2' : '1');
    const toSlot = parseInt(target, 10);
    if (!toSlot || toSlot === selectedSlot || toSlot < 1 || toSlot > 8) return;
    await fetch('/api/slots/swap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_slot: selectedSlot, to_slot: toSlot })
    });
    selectSlot(toSlot);
  }

  async function inspPinSlot() {
    const data = lastStatusData;
    const it = data && (data.active_slots[String(selectedSlot)] || data.active_slots[selectedSlot]);
    if (!it || !it.pin_key) { alert('No hay joystick para fijar en este slot.'); return; }
    await fetch('/api/slots/pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slot: selectedSlot, pin_key: it.pin_key })
    });
    alert(`Slot P${selectedSlot} fijado al puerto USB del mando.`);
  }

  function buildConnectedSlotTile(slot, item) {
    const color = SLOT_COLORS[slot] || '#3b82f6';
    const dzL = Math.round((item.deadzone_left ?? 0.05) * 100);
    const isSelected = slot === selectedSlot;

    return `
      <div class="slot-card ${isSelected ? 'selected' : ''}" id="slot-card-${slot}" style="--slot-color:${color};" onclick="selectSlot(${slot})">
        <div class="tile-top">
          <span class="tile-tag">SLOT ${slot} · P${slot}</span>
          <span id="drift-pill-${slot}" class="drift-pill">● Drift OK</span>
        </div>
        <div>
          <div class="tile-title">🎮 ${escapeHtml(item.name)}</div>
          <div class="tile-sub">${escapeHtml(item.vendor)}:${escapeHtml(item.product)} · ${escapeHtml(item.dev_path)}</div>
        </div>
        <div class="tile-live-row">
          <div class="mini-sticks">
            <div class="mini-stick-ring"><div id="mini-dot-l-${slot}" class="mini-dot"></div></div>
            <div class="mini-stick-ring"><div id="mini-dot-r-${slot}" class="mini-dot"></div></div>
          </div>
          <div class="mini-face-btns">
            <div id="btn-${slot}-a" class="m-face-btn">A</div>
            <div id="btn-${slot}-b" class="m-face-btn">B</div>
            <div id="btn-${slot}-x" class="m-face-btn">X</div>
            <div id="btn-${slot}-y" class="m-face-btn">Y</div>
          </div>
        </div>
        <div class="tile-foot">
          <span>DZ: ${dzL}%</span>
          <span>${item.pin_key ? '📌 Fijado' : 'Vibración: ON'}</span>
        </div>
      </div>
    `;
  }

  function buildEmptySlotTile(slot) {
    const isSelected = slot === selectedSlot;
    return `
      <div class="slot-card empty-slot ${isSelected ? 'selected' : ''}" id="slot-card-${slot}" onclick="selectSlot(${slot})">
        <div class="tile-top">
          <span class="tile-tag">SLOT ${slot} LIBRE</span>
          <span style="font-size:10.5px; color:#475569;">DISPONIBLE</span>
        </div>
        <div style="text-align:center; padding:12px 6px;">
          <div style="font-size:12.5px; font-weight:700; color:#64748b;">Esperando mando...</div>
          <div style="font-size:11px; color:#475569; margin-top:2px;">Enchufá un mando para Jugador ${slot}</div>
        </div>
      </div>
    `;
  }

  function updateSlotLiveTelemetry(slot, item, inp) {
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

    // Mini radar dots on tile
    const dotL = document.getElementById('mini-dot-l-' + slot);
    const dotR = document.getElementById('mini-dot-r-' + slot);
    if (dotL) dotL.style.transform = `translate(${lx * 13}px, ${ly * 13}px)`;
    if (dotR) dotR.style.transform = `translate(${rx * 13}px, ${ry * 13}px)`;

    const pill = document.getElementById('drift-pill-' + slot);
    const isDrift = Math.abs(lx) > Math.max(dzL, 0.06) || Math.abs(ly) > Math.max(dzL, 0.06) ||
                    Math.abs(rx) > Math.max(dzR, 0.06) || Math.abs(ry) > Math.max(dzR, 0.06);
    if (pill) {
      pill.className = 'drift-pill' + (isDrift ? ' drift' : '');
      pill.textContent = isDrift ? '⚠️ Moviendo' : '● Drift OK';
    }

    const btnA = document.getElementById(`btn-${slot}-a`);
    const btnB = document.getElementById(`btn-${slot}-b`);
    const btnX = document.getElementById(`btn-${slot}-x`);
    const btnY = document.getElementById(`btn-${slot}-y`);
    if (btnA) btnA.classList.toggle('pressed', Boolean(btns['a']));
    if (btnB) btnB.classList.toggle('pressed', Boolean(btns['b']));
    if (btnX) btnX.classList.toggle('pressed', Boolean(btns['x']));
    if (btnY) {
      btnY.classList.toggle('pressed-y', Boolean(btns['y']));
      btnY.classList.toggle('pressed', Boolean(btns['y']));
    }

    // If this slot is currently selected in Inspector, update detailed radar & triggers
    if (slot === selectedSlot) {
      const sDotL = document.getElementById('insp-scope-dot-l');
      const sDotR = document.getElementById('insp-scope-dot-r');
      if (sDotL) sDotL.style.transform = `translate(${lx * 42}px, ${ly * 42}px)`;
      if (sDotR) sDotR.style.transform = `translate(${rx * 42}px, ${ry * 42}px)`;

      const cL = document.getElementById('insp-coords-l');
      const cR = document.getElementById('insp-coords-r');
      if (cL) cL.textContent = `X: ${lx >= 0 ? '+' : ''}${lx.toFixed(2)}  Y: ${ly >= 0 ? '+' : ''}${ly.toFixed(2)}`;
      if (cR) cR.textContent = `X: ${rx >= 0 ? '+' : ''}${rx.toFixed(2)}  Y: ${ry >= 0 ? '+' : ''}${ry.toFixed(2)}`;

      const dzRingL = document.getElementById('insp-scope-dz-l');
      const dzRingR = document.getElementById('insp-scope-dz-r');
      if (dzRingL) { const p = Math.max(8, Math.round(dzL * 90)); dzRingL.style.width = p + 'px'; dzRingL.style.height = p + 'px'; }
      if (dzRingR) { const p = Math.max(8, Math.round(dzR * 90)); dzRingR.style.width = p + 'px'; dzRingR.style.height = p + 'px'; }

      const fillLt = document.getElementById('insp-fill-lt');
      const txtLt = document.getElementById('insp-txt-lt');
      const fillRt = document.getElementById('insp-fill-rt');
      const txtRt = document.getElementById('insp-txt-rt');
      if (fillLt) fillLt.style.width = lt + '%';
      if (txtLt) txtLt.textContent = 'LT ' + lt + '%';
      if (fillRt) fillRt.style.width = rt + '%';
      if (txtRt) txtRt.textContent = 'RT ' + rt + '%';

      const bLb = document.getElementById('insp-btn-lb');
      const bRb = document.getElementById('insp-btn-rb');
      if (bLb) bLb.classList.toggle('pressed', Boolean(btns['lb']));
      if (bRb) bRb.classList.toggle('pressed', Boolean(btns['rb']));
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
      uncalBanner.innerHTML = '<span>🔌 <strong>Mando nuevo detectado sin perfil calibrado:</strong> ' +
        uncal.map(gp => `${escapeHtml(gp.name)} (${escapeHtml(gp.vendor)}:${escapeHtml(gp.product)})`).join(', ') + '</span>' +
        `<button class="btn" style="background:#f59e0b;color:#0b1120;padding:4px 10px;font-size:11px;" data-dev="${escapeHtml(uncal[0].dev_path)}" data-name="${escapeHtml(uncal[0].name)}" onclick="startWebCalibration(this.dataset.dev, this.dataset.name)">⚡ Calibrar Ahora</button>`;
    } else {
      uncalBanner.className = 'alert-banner';
      uncalBanner.innerHTML = '';
    }
  }

  function applyStatusPayload(data) {
    lastStatusData = data;
    failCount = 0;
    document.getElementById('conn-banner').className = 'alert-banner';

    updateBridgeUI(Boolean(data.bridge_enabled));
    renderBanners(data);

    let activeCount = 0;
    let maxHz = 0;
    for (let s = 1; s <= 8; s++) {
      if (data.active_slots[String(s)] || data.active_slots[s]) {
        activeCount++;
        const inp = data.live_inputs[String(s)] || data.live_inputs[s];
        if (inp && inp.polling_hz > maxHz) maxHz = inp.polling_hz;
      }
    }
    document.getElementById('metrics-vpad-count').textContent = `${activeCount} Activo${activeCount === 1 ? '' : 's'}`;
    const hzEl = document.getElementById('metrics-polling-hz');
    if (hzEl) hzEl.textContent = maxHz > 0 ? `${maxHz} Hz` : (activeCount > 0 ? 'Reposo' : '-- Hz');

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
      sigObj[s] = it ? `${it.vendor}:${it.product}:${it.dev_path}:${it.name}:${it.rumble_enabled}:${it.outer_scale}:${it.sensitivity_curve}:${it.nintendo_swap}:${it.trigger_bumper_swap}` : null;
    }
    const sig = JSON.stringify(sigObj);
    const container = document.getElementById('slots-container');
    const extraPills = document.getElementById('extra-slots-pills');

    if (sig !== lastSlotsSig) {
      lastSlotsSig = sig;
      let html1to4 = '';
      for (let s = 1; s <= 4; s++) {
        const item = data.active_slots[String(s)] || data.active_slots[s];
        html1to4 += item ? buildConnectedSlotTile(s, item) : buildEmptySlotTile(s);
      }
      for (let s = 5; s <= 8; s++) {
        const item = data.active_slots[String(s)] || data.active_slots[s];
        html1to4 += `<div style="display:none;" id="slot-card-${s}">${item ? buildConnectedSlotTile(s, item) : buildEmptySlotTile(s)}</div>`;
      }
      container.innerHTML = html1to4;

      let extraHtml = '';
      for (let s = 5; s <= 8; s++) {
        const item = data.active_slots[String(s)] || data.active_slots[s];
        const occ = item ? 'occupied' : '';
        const sel = s === selectedSlot ? 'selected' : '';
        extraHtml += `<div class="extra-pill ${occ} ${sel}" data-slot="${s}" onclick="selectSlot(${s})">P${s} · ${item ? escapeHtml(item.name).slice(0, 10) : 'Libre'}</div>`;
      }
      extraPills.innerHTML = extraHtml;

      const curItem = data.active_slots[String(selectedSlot)] || data.active_slots[selectedSlot];
      if (!curItem) {
        for (let s = 1; s <= 8; s++) {
          if (data.active_slots[String(s)] || data.active_slots[s]) { selectSlot(s); break; }
        }
      }
      updateInspectorCardHeader();
    }

    for (let s = 1; s <= 8; s++) {
      const item = data.active_slots[String(s)] || data.active_slots[s];
      const inp = data.live_inputs[String(s)] || data.live_inputs[s] || {};
      updateSlotLiveTelemetry(s, item, inp);
    }
  }

  async function updateDashboard() {
    if (document.hidden) return;
    try {
      const res = await fetch('/api/status');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      applyStatusPayload(await res.json());
    } catch (e) {
      failCount += 1;
      if (failCount >= 3) {
        const cb = document.getElementById('conn-banner');
        cb.className = 'alert-banner error';
        cb.textContent = '🔴 Sin conexión con el motor Resiticks (127.0.0.1:8765). Verificá que app.py esté corriendo.';
      }
    }
  }

  let liveEventSource = null;
  function connectLiveStream() {
    if (document.hidden || typeof EventSource === 'undefined') return;
    if (liveEventSource) { liveEventSource.close(); liveEventSource = null; }
    liveEventSource = new EventSource('/api/stream');
    liveEventSource.onmessage = (ev) => {
      try { applyStatusPayload(JSON.parse(ev.data)); } catch (e) {}
    };
    liveEventSource.onerror = () => {
      if (liveEventSource) { liveEventSource.close(); liveEventSource = null; }
    };
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

  async function launchTerminalCalibration() {
    try {
      const res = await fetch('/api/calibrate/launch', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) alert(data.error || 'No se pudo abrir la terminal.');
    } catch (e) {
      alert('Error abriendo calibración por consola.');
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

  // Web Calibration Modal
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

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      if (liveEventSource) { liveEventSource.close(); liveEventSource = null; }
    } else {
      updateDashboard();
      connectLiveStream();
    }
  });
  setInterval(() => {
    if (!liveEventSource || liveEventSource.readyState === 2) {
      updateDashboard();
      if (!liveEventSource && !document.hidden) connectLiveStream();
    }
  }, 2500);
  window.addEventListener('pagehide', () => {
    if (liveEventSource) { liveEventSource.close(); liveEventSource = null; }
  });
  updateDashboard();
  setTimeout(connectLiveStream, 2000);
  loadProfilesList();
</script>
</body>
</html>
"""
