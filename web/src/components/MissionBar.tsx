import { useState, useEffect } from 'react';

interface MissionBarProps {
  seed: number;
  onRegenerate: () => void;
  loading: boolean;
  showMap: boolean;
  onToggleMap: () => void;
}

export function MissionBar({ seed, onRegenerate, loading, showMap, onToggleMap }: MissionBarProps) {
  const [time, setTime] = useState('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(now.toISOString().replace('T', ' ').slice(0, 19) + 'Z');
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-paper-dark border-b border-ink/8 select-none">
      {/* Left — title block */}
      <div className="flex items-center gap-5">
        <div>
          <h1 className="text-base tracking-[0.06em] text-ink font-medium leading-tight">
            CAMPUS ATLAS
          </h1>
          <p className="text-[10px] tracking-[0.04em] text-ink-light leading-tight">
            HUAWEI SMART CAMPUS · MASTERPLAN
          </p>
        </div>
        <div className="h-7 w-px bg-ink/12" />
        <button
          onClick={onToggleMap}
          title={showMap ? '隐藏地图' : '显示地图'}
          className={`text-xs px-2 py-0.5 border transition-colors cursor-pointer ${
            showMap ? 'border-ink/30 text-ink bg-ink/5' : 'border-ink/15 text-ink/40 hover:text-ink hover:border-ink/30'
          }`}
        >
          🗺 地图
        </button>
        <div className="flex items-center gap-1.5 text-xs text-ink-light">
          SEED <span className="text-ink font-medium">{seed}</span>
          <button
            onClick={onRegenerate}
            disabled={loading}
            title="Random seed"
            className="text-ink/30 hover:text-ink disabled:opacity-30 transition-colors cursor-pointer leading-none text-sm"
          >
            🎲
          </button>
        </div>
      </div>

      {/* Center — reference line */}
      <div className="text-[10px] tracking-[0.08em] text-ink/25 font-medium">
        SMART CAMPUS MASTERPLAN · HUAWEI PROPRIETARY
      </div>

      {/* Right — time + regenerate */}
      <div className="flex items-center gap-4">
        <span className="text-xs text-ink-light font-mono">{time}</span>
        <button
          onClick={onRegenerate}
          disabled={loading}
          className="text-xs tracking-[0.04em] px-4 py-1.5 bg-ink hover:bg-ink/85 text-paper-light
            disabled:opacity-40 disabled:cursor-wait transition-all duration-150 cursor-pointer font-medium"
        >
          {loading ? 'GENERATING…' : 'REGENERATE'}
        </button>
      </div>
    </header>
  );
}
