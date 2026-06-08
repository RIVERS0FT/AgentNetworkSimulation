// ============== Log (must be first) ==============
let logBuffer = [];
function logEntry(level, event) {
const now = new Date();
const ts = now.getFullYear() + '-' +
           (now.getMonth()+1).toString().padStart(2,'0') + '-' +
           now.getDate().toString().padStart(2,'0') + ' ' +
           now.getHours().toString().padStart(2,'0') + ':' +
           now.getMinutes().toString().padStart(2,'0') + ':' +
           now.getSeconds().toString().padStart(2,'0') + '.' +
           now.getMilliseconds().toString().padStart(3,'0');
logBuffer.push({ timestamp: ts, level, event });
if (logBuffer.length > 500) logBuffer.shift();
renderLogs();
}
function renderLogs() {
const filter = document.getElementById('log-filter')?.value || '';
const container = document.getElementById('log-entries');
const autoscroll = document.getElementById('log-autoscroll')?.checked;
if (!container) return;
const wasAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 30;
let entries = [...logBuffer];
if (filter) entries = entries.filter(e => e.level === filter);
const countEl = document.getElementById('log-count');
if (countEl) countEl.textContent = entries.length;
container.innerHTML = entries.slice(-200).map(e =>
'<div class=log-entry><span class=ts>' + e.timestamp + '</span> <span class="lv lv-' + e.level + '">' + e.level + '</span> <span class=ev>' + e.event + '</span></div>'
).join('') || '<div class=log-entry><span class=ts>--</span> <span class=ev>无日志</span></div>';
if (autoscroll && wasAtBottom) container.scrollTop = container.scrollHeight;
}
function clearLogs() { logBuffer = []; renderLogs(); }

// ============== State ==============
const API = '/api';
function $id(id) { return document.getElementById(id); }
let agents = [];
let connections = [];
let ws = null;
let hoveredAgent = null;
let simRunning = false;
let terrNainMap = null;
let tickRunning = false;
let tickInterval = null;

// ============== Agent forwarding → React iframe ==============
const iframe = document.getElementById('campus-iframe');
let _relationships = [];
function forwardAgents() {
  if (iframe && iframe.contentWindow) {
    iframe.contentWindow.postMessage({ type: 'agents', data: agents, relationships: _relationships }, '*');
  }
}

// Receive hover events from iframe → show tooltip in parent
window.addEventListener('message', (e) => {
  if (e.data?.type === 'agent-hover') {
    const found = e.data.data;
    const tt = document.getElementById('tooltip');
    if (found) {
      hoveredAgent = found;
      const statusLabel = { idle:'空闲', running:'运行中', paused:'已暂停', stopped:'已停止', error:'异常', created:'已创建' };
      const roleLabel = { scout:'侦察兵', commander:'指挥官', analyst:'分析师', support:'支援', generic:'通用', observer:'观察员' };
      let html = '<div class=tt-name>' + (found.name || found.agent_id) + '</div>';
      html += '<div class=tt-role>' + (roleLabel[found.role] || found.role) + '</div>';
      html += '<div class=tt-row><span class=lbl>ID</span><span class=val>' + found.agent_id + '</span></div>';
      html += '<div class=tt-row><span class=lbl>状态</span><span class=val>' + (statusLabel[found.status] || found.status) + '</span></div>';
      if (found.x !== undefined) {
        html += '<div class=tt-row><span class=lbl>坐标</span><span class=val>(' + found.x.toFixed(0) + ', ' + found.y.toFixed(0) + ')</span></div>';
      }
      const tasks = found.pending_task_descs || [];
      if (tasks.length > 0) { html += '<div class=tt-section>任务</div>'; tasks.forEach((t, i) => { html += '<div class=tt-task><span class=tt-task-n>' + (i+1) + '.</span> ' + t + '</div>'; }); }
      const meta = found.extra_meta || {};
      if (meta.core_goal) { html += '<div class=tt-section>目标</div><div class=tt-task>' + meta.core_goal + '</div>'; }
      if (meta.hidden_secret) { html += '<div class=tt-section>秘密</div><div class=tt-task style=color:#C0392B>' + meta.hidden_secret + '</div>'; }
      if (meta.action_space && meta.action_space.length) {
        html += '<div class=tt-section>行动</div><div class=tt-skills>' + meta.action_space.map(a => '<span class=tt-tag>' + a + '</span>').join('') + '</div>';
      }
      tt.innerHTML = html;
      tt.style.display = 'block';
      // Use mouse position from iframe, relative to parent panel
      const panelRect = document.getElementById('canvas-panel')?.getBoundingClientRect();
      const tx = (e.data.mx || 0) - (panelRect?.left || 0);
      const ty = (e.data.my || 0) - (panelRect?.top || 0);
      tt.style.left = Math.min(tx + 16, window.innerWidth - 300) + 'px';
      tt.style.top = Math.max(4, ty - 10) + 'px';
    } else {
      hoveredAgent = null;
      tt.style.display = 'none';
    }
  }
});

// ============== WebSocket ==============
function connectWS() {
const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
ws = new WebSocket(proto + '//' + location.host + '/ws');
ws.onopen = () => { ws.send('all'); logEntry('L1', 'WebSocket 已连接'); };
ws.onmessage = (e) => {
const msg = JSON.parse(e.data);
if (msg.type === 'status' || msg.type === 'all') {
agents = msg.data.agents || [];
forwardAgents();
}
if (msg.type === 'packets' && msg.data) {
// packet stats received
}
if (msg.type === 'message') {
logEntry('L5', '消息包: ' + (msg.data.payload?.action || msg.data.type) + ' [' + msg.data.source + ' → ' + msg.data.target + ']');
}
};
ws.onclose = () => { setTimeout(connectWS, 3000); };
}
connectWS();

// ============== Scene Selector ==============
async function loadSceneList() {
  try {
    const r = await fetch(API + '/scenes');
    const data = await r.json();
    const sel = document.getElementById('scene-selector');
    if (!sel) return;
    sel.innerHTML = '<option value="">选择场景脚本</option>';
    data.scenes.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f;
      opt.textContent = f.replace('.json', '');
      sel.appendChild(opt);
    });
  } catch(e) { console.error('loadSceneList', e); }
}

function onSceneSelect() {}

async function runSelectedScene() {
  const sel = document.getElementById('scene-selector');
  const filename = sel?.value;
  if (!filename) { logEntry('L1', '请先选择场景脚本'); return; }

  let sceneName, script, scriptJson = null;
  try {
    const r = await fetch(API + '/scenes/' + encodeURIComponent(filename));
    const data = await r.json();
    const content = data.content?.trim();
    if (!content) { logEntry('L1', '场景文件内容为空'); return; }
    const json = JSON.parse(content);
    if (json.script_json) {
      sceneName = json.script_json.scenario_metadata?.title || data.name;
      scriptJson = json.script_json;
    } else if (json.script) {
      sceneName = json.name || data.name;
      script = json.script;
    } else {
      logEntry('L1', '场景格式不支持: 需要 script 或 script_json 字段'); return;
    }
  } catch(e) {
    if (e instanceof SyntaxError) { logEntry('L1', 'JSON解析失败: ' + e.message); }
    else { logEntry('L1', '读取场景失败: ' + e.message); }
    return;
  }
  if (!scriptJson && !script) { logEntry('L1', '场景文件内容为空'); return; }

  simRunning = true;
  logEntry('L1', '=== 运行场景: ' + sceneName + ' ===');
  try {
    const body = scriptJson
      ? { scene: 'auto', script_json: scriptJson, name: sceneName }
      : { scene: 'auto', script: script, name: sceneName };
    const r = await fetch(API + '/simulations/run', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    if (!r.ok) { const text = await r.text(); throw new Error(text.slice(0, 200)); }
    const data = await r.json();
    logEntry('L1', '完成: ' + (data.duration_seconds || 0) + 's | Agent: ' + (data.agent_stats?.total_agents || 0) + ' 个');
    if (data.relationships) { _relationships = data.relationships; forwardAgents(); }
    if (ws && ws.readyState === WebSocket.OPEN) ws.send('all');
  } catch(e) { logEntry('L1', '运行失败: ' + e.message); }
  simRunning = false;
}

function togglePanel(id) { document.getElementById(id).classList.toggle('minimized'); }

// ============== Start ==============
logEntry('L1', '控制台就绪');
loadSceneList();
setTimeout(() => { if (ws && ws.readyState === WebSocket.OPEN) ws.send('all'); }, 500);
