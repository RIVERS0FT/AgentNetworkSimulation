import type { CursorInfo } from '../types';

interface CoordinateDisplayProps {
  info: CursorInfo | null;
}

export function CoordinateDisplay({ info }: CoordinateDisplayProps) {
  if (!info) {
    return (
      <div className="absolute bottom-2 right-2 bg-paper-light/90 px-2 py-1 text-[10px] font-mono text-ink/40 select-none">
        <span>---- / ---- / ----m</span>
      </div>
    );
  }

  const elev = info.elevation !== null ? Math.round(info.elevation * 1500) : '--';

  return (
    <div className="absolute bottom-2 right-2 bg-paper-light/90 px-2 py-1 text-[10px] font-mono text-ink/70 select-none border border-ink/10">
      <span>
        [{Math.round(info.worldX)}, {Math.round(info.worldY)}]
      </span>
      <span className="mx-1 text-ink/30">|</span>
      <span>{info.sector ? `SECTOR ${info.sector}` : '--'}</span>
      <span className="mx-1 text-ink/30">|</span>
      <span>{info.terrain?.toUpperCase() || '--'}</span>
      <span className="mx-1 text-ink/30">|</span>
      <span>{elev}m</span>
    </div>
  );
}
