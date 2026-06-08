import { useEffect, useState, useCallback } from 'react';

interface AgentInfo {
  agent_id: string; name: string; role: string; status: string;
  x: number; y: number;
  skills?: string[]; tags?: string[];
  pending_task_descs?: string[];
  extra_meta?: Record<string, any>;
}

interface Relationship {
  from: string; to: string;
  relation_type?: string;
  value?: number;
  can_direct_chat?: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  idle: '#6B8A5E', running: '#5A7A9A', paused: '#B8783A',
  stopped: '#C0392B', error: '#C0392B', created: '#8B8475',
};

export function useAgentOverlay() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [hovered, setHovered] = useState<AgentInfo | null>(null);
  const [selected, setSelected] = useState<AgentInfo | null>(null);
  const [mousePos, setMousePos] = useState<{x:number;y:number}|null>(null);

  // Receive agent data from parent via postMessage
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.type === 'agents') {
        setAgents(e.data.data || []);
        setRelationships(e.data.relationships || []);
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  const handleMouse = useCallback((x: number, y: number, wx: number, wy: number, zoom: number) => {
    setMousePos({x, y});
    let found: AgentInfo | null = null;
    const rPx = Math.min(12, 6 / zoom);
    for (let i = agents.length - 1; i >= 0; i--) {
      const a = agents[i];
      if (a.x === undefined || a.y === undefined) continue;
      const dx = wx - a.x, dy = wy - a.y;
      if (Math.sqrt(dx*dx + dy*dy) < rPx + 3/zoom) { found = a; break; }
    }
    setHovered(found);
  }, [agents]);

  const handleClick = useCallback(() => {
    setSelected(hovered);
  }, [hovered]);

  return { agents, relationships, hovered, selected, mousePos, handleMouse, handleClick };
}

/** Draw relationship links between agents */
export function drawRelationships(
  ctx: CanvasRenderingContext2D,
  relationships: Relationship[],
  agents: AgentInfo[],
) {
  if (!relationships.length || !agents.length) return;
  const agentMap = new Map(agents.map(a => [a.agent_id, a]));
  ctx.save();
  ctx.lineCap = 'round';

  for (const rel of relationships) {
    const from = agentMap.get(rel.from.toLowerCase());
    const to = agentMap.get(rel.to.toLowerCase());
    if (!from || !to || from.x === undefined || to.x === undefined) continue;

    // Color: cooperative (green) vs competitive (red)
    const isCooperative = (rel.value || 0) > 0;
    const alpha = Math.min(1, Math.abs(rel.value || 50) / 100 + 0.15);
    const color = isCooperative
      ? `rgba(107,138,94,${alpha.toFixed(2)})`   // green
      : `rgba(192,57,43,${alpha.toFixed(2)})`;    // red

    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);

    if (rel.can_direct_chat) {
      ctx.setLineDash([]);
      ctx.lineWidth = 1.0;
    } else {
      ctx.setLineDash([3, 4]);
      ctx.lineWidth = 0.6;
    }
    ctx.strokeStyle = color;
    ctx.stroke();

    // Relation label at midpoint
    if (rel.relation_type) {
      const mx = (from.x + to.x) / 2;
      const my = (from.y + to.y) / 2;
      ctx.fillStyle = '#6A665F';
      ctx.font = '7px Inter,IBM Plex Sans,system-ui,sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(rel.relation_type, mx, my - 3);
      ctx.textAlign = 'start';
    }
  }
  ctx.setLineDash([]);
  ctx.restore();
}

/** Draw agents onto the shared canvas context (in world coordinates).
 *  Called inside a ctx.translate(screenX,screenY) + ctx.scale(screenW/worldW,...) transform.
 */
export function drawAgents(
  ctx: CanvasRenderingContext2D,
  agents: AgentInfo[],
  selected: AgentInfo | null,
  worldWidth: number,
  _canvasW: number, _canvasH: number,
) {
  if (!agents.length) return;
  // world coords → pixels within the transformed context (0..worldWidth maps to 0.._canvasW after scale)
  const r = Math.max(2, Math.min(10, worldWidth / 50));

  for (const a of agents) {
    if (a.x === undefined || a.y === undefined) continue;
    const color = STATUS_COLORS[a.status] || '#8B8475';

    // World coordinates (context is already transformed)
    const sx = a.x;
    const sy = a.y;

    // Selection ring
    if (selected?.agent_id === a.agent_id) {
      ctx.beginPath(); ctx.arc(sx, sy, r + 2, 0, Math.PI * 2);
      ctx.strokeStyle = color; ctx.lineWidth = 1.5 / (ctx as any)._scale_hint || 1;
      ctx.setLineDash([2, 2]); ctx.stroke(); ctx.setLineDash([]);
    }

    // Body
    ctx.beginPath(); ctx.arc(sx, sy, r, 0, Math.PI * 2);
    ctx.fillStyle = color + 'cc'; ctx.fill();
    ctx.strokeStyle = color; ctx.lineWidth = 0.8; ctx.stroke();

    // Label
    ctx.fillStyle = '#2A2A2A';
    const fontSize = Math.max(7, Math.min(11, r * 1.2));
    ctx.font = `${fontSize}px Inter,IBM Plex Sans,system-ui,sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText(a.name || a.agent_id, sx, sy - r - 2);
    ctx.textAlign = 'start';
  }
}
