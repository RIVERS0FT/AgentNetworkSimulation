import type { CampusStats } from '../types/urban';

interface UrbanIntelSummaryProps {
  stats: CampusStats;
}

export function UrbanIntelSummary({ stats }: UrbanIntelSummaryProps) {
  return (
    <footer className="h-36 bg-paper-light border-t border-ink/10 overflow-y-auto select-none">
      <div className="p-3">
        <div className="flex gap-4">
          {/* CAMPUS SUMMARY */}
          <div className="flex-1">
            <div className="font-military text-[11px] tracking-[0.12em] text-ink pb-1 mb-2 border-b border-ink/20">
              CAMPUS SUMMARY — HUAWEI SMART CAMPUS
            </div>
            <div className="grid grid-cols-4 gap-x-6 gap-y-1 text-[11px]">
              <StatItem label="Buildings" value={stats.buildingCount.toLocaleString()} />
              <StatItem label="Research Centers" value={`${stats.researchCenters}`} />
              <StatItem label="Employees" value={stats.employees.toLocaleString()} />
              <StatItem label="Road Length" value={`${stats.roadLengthKm.toLocaleString()} km`} />
              <StatItem label="Green Coverage" value={`${stats.greenCoverage}%`} />
              <StatItem label="Water Coverage" value={`${stats.waterCoverage}%`} />
              <StatItem label="Parking Spaces" value={stats.parkingSpaces.toLocaleString()} />
              <StatItem label="Campus Area" value={`${stats.campusArea} km²`} />
            </div>
          </div>

          {/* LANDMARKS */}
          <div className="w-64">
            <div className="font-military text-[11px] tracking-[0.12em] text-ink pb-1 mb-2 border-b border-ink/20">
              CAMPUS LANDMARKS
            </div>
            <div className="grid grid-cols-1 gap-y-0.5 text-[10px] font-mono">
              <span className="text-ink/60">◆ CAMPUS HQ</span>
              <span className="text-ink/60">◆ AI RESEARCH TOWER</span>
              <span className="text-ink/60">◆ COMPUTING CENTER</span>
              <span className="text-ink/60">◆ INNOVATION PLAZA</span>
              <span className="text-ink/60">◆ CAMPUS LAKE</span>
              <span className="text-ink/60">◆ INNOVATION CANAL</span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="font-military text-ink-light text-[10px]">{label}:</span>
      <span className="font-mono text-ink">{value}</span>
    </div>
  );
}
