import { useState, useEffect } from 'react';

interface MissionBarProps {
  seed: number;
  onRegenerate: () => void;
  loading: boolean;
}

export function MissionBar({ seed, onRegenerate, loading }: MissionBarProps) {
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
    <header className="flex items-center justify-between px-4 py-2 bg-paper-dark border-b border-ink/10 select-none">
      {/* Left */}
      <div className="flex items-center gap-6">
        <div>
          <h1 className="font-military text-lg tracking-[0.12em] text-ink font-semibold leading-tight">
            CAMPUS ATLAS
          </h1>
          <p className="font-military text-[10px] tracking-[0.08em] text-ink-light leading-tight">
            HUAWEI SMART CAMPUS — DIGITAL TWIN
          </p>
        </div>
        <div className="h-8 w-px bg-ink/15" />
        <div className="flex items-center gap-1.5 font-mono text-xs text-ink-light">
          SEED: <span className="text-ink font-medium">{seed}</span>
          <button
            onClick={onRegenerate}
            disabled={loading}
            title="Random seed"
            className="text-ink/40 hover:text-ink disabled:opacity-30 transition-colors cursor-pointer leading-none text-sm"
          >
            🎲
          </button>
        </div>
      </div>

      {/* Center — banner */}
      <div className="font-military text-[10px] tracking-[0.15em] text-ink/40">
        // SMART CAMPUS DIGITAL TWIN // HUAWEI PROPRIETARY //
      </div>

      {/* Right */}
      <div className="flex items-center gap-4">
        <span className="font-mono text-xs text-ink-light">{time}</span>
        <button
          onClick={onRegenerate}
          disabled={loading}
          className="font-military text-xs tracking-[0.08em] px-4 py-1.5 bg-ink hover:bg-ink/80 text-paper-light
            disabled:opacity-40 disabled:cursor-wait transition-all duration-150 cursor-pointer"
        >
          {loading ? 'GENERATING…' : 'REGENERATE'}
        </button>
      </div>
    </header>
  );
}
