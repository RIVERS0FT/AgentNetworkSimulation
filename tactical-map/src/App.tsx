import { useState, useEffect } from 'react';
import type { CityStats } from './types/urban';
import { MissionBar } from './components/MissionBar';
import { UrbanAtlas } from './components/UrbanAtlas';
import { UrbanLegendPanel } from './components/UrbanLegendPanel';
import { UrbanIntelSummary } from './components/UrbanIntelSummary';
import { useUrbanGenerator } from './hooks/useUrbanGenerator';

export default function App() {
  const urban = useUrbanGenerator();
  const [urbanStats, setUrbanStats] = useState<CityStats | null>(null);

  useEffect(() => { urban.generate(123); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!urban.world) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-paper">
        <div className="font-military text-2xl tracking-[0.15em] text-ink mb-2">
          HUAWEI SMART CAMPUS ATLAS
        </div>
        <div className="font-mono text-sm text-ink-light mb-6">Generating…</div>
        <div className="w-48 h-1 bg-ink/10 overflow-hidden">
          <div className="h-full bg-ink/40 animate-pulse w-1/2" />
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-paper">
      <MissionBar
        seed={urban.seed}
        onRegenerate={urban.regenerate}
        loading={urban.loading}
      />

      <div className="flex flex-1 min-h-0">
        <div className="flex-1 relative min-w-0 flex flex-col">
          <UrbanAtlas world={urban.world!} onStats={setUrbanStats} />
          {urban.world && (
            <div className="absolute bottom-2 right-2 bg-paper-light/90 px-2 py-1 text-[10px] font-mono text-ink/50 select-none border border-ink/10">
              {urban.world.width}×{urban.world.height} · SEED {urban.seed}
            </div>
          )}
        </div>
        <UrbanLegendPanel />
      </div>

      {urbanStats && <UrbanIntelSummary stats={urbanStats} />}
    </div>
  );
}
