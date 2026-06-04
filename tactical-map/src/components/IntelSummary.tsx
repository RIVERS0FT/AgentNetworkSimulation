import type { TerrainWorld, Sector } from '../types';

interface IntelSummaryProps {
  world: TerrainWorld;
}

export function IntelSummary({ world }: IntelSummaryProps) {
  const { sectors, units, villages } = world;
  const enemyCount = units.filter(u => u.force === 'enemy').length;
  const friendlyCount = units.filter(u => u.force === 'friendly').length;
  const strongholds = units.filter(u => u.force === 'enemy' && u.label.includes('STRONGHOLD'));

  return (
    <footer className="h-36 bg-paper-light border-t border-ink/10 overflow-y-auto select-none">
      <div className="p-3">
        <div className="flex gap-4">
          {/* INTEL SUMMARY header */}
          <div className="flex-1">
            <div className="font-military text-[11px] tracking-[0.12em] text-ink pb-1 mb-2 border-b border-ink/20">
              INTEL SUMMARY
            </div>

            <div className="grid grid-cols-3 gap-x-6 gap-y-1 text-[11px]">
              <IntelItem label="Friendly Units" value={`${friendlyCount}`} />
              <IntelItem label="Enemy Contacts" value={`${enemyCount}`} />
              <IntelItem label="Strongholds" value={`${strongholds.length}`} />
              <IntelItem label="Villages" value={`${villages.length}`} />
              <IntelItem label="Sectors" value={`${sectors.length}`} />
              <IntelItem label="Map Grid" value={`${world.heightmap.width}×${world.heightmap.height}`} />
              <IntelItem label="Elevation Range" value={`${Math.round(world.heightmap.min * 1500)}m – ${Math.round(world.heightmap.max * 1500)}m`} />
              <IntelItem label="Seed" value={`${world.config.seed}`} />
              <IntelItem
                label="Dominant Terrain"
                value={getDominantTerrain(sectors)}
              />
            </div>
          </div>

          {/* Sector breakdown */}
          <div className="w-72">
            <div className="font-military text-[11px] tracking-[0.12em] text-ink pb-1 mb-2 border-b border-ink/20">
              SECTOR ASSESSMENT
            </div>
            <div className="space-y-1 text-[10px] font-mono">
              {sectors.map(s => (
                <div key={s.id} className="flex justify-between">
                  <span className="font-military text-ink/80">SECTOR {s.id}</span>
                  <span className="text-ink/60">{s.dominantTerrain.toUpperCase()}</span>
                  <span className={s.threatLevel === 'high' ? 'text-enemy' : s.threatLevel === 'medium' ? 'text-fire' : 'text-neutral-bg'}>
                    THREAT: {s.threatLevel.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Key terrain */}
          <div className="w-48">
            <div className="font-military text-[11px] tracking-[0.12em] text-ink pb-1 mb-2 border-b border-ink/20">
              KEY TERRAIN
            </div>
            <ul className="text-[10px] font-military text-ink/60 list-disc list-inside space-y-0.5">
              {getKeyTerrainItems(sectors).map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </footer>
  );
}

function IntelItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="font-military text-ink-light text-[10px]">{label}:</span>
      <span className="font-mono text-ink">{value}</span>
    </div>
  );
}

function getDominantTerrain(sectors: Sector[]): string {
  const counts: Record<string, number> = {};
  for (const s of sectors) {
    counts[s.dominantTerrain] = (counts[s.dominantTerrain] || 0) + 1;
  }
  let best = '', max = 0;
  for (const [k, v] of Object.entries(counts)) {
    if (v > max) { max = v; best = k; }
  }
  return best.toUpperCase();
}

function getKeyTerrainItems(sectors: Sector[]): string[] {
  const items: string[] = [];
  for (const s of sectors) {
    for (const kt of s.keyTerrain) {
      const item = `SECTOR ${s.id}: ${kt}`;
      if (!items.includes(item)) items.push(item);
    }
  }
  return items.slice(0, 8);
}
