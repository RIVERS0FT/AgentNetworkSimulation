interface LegendPanelProps {
  className?: string;
}

export function LegendPanel({ className = '' }: LegendPanelProps) {
  return (
    <aside className={`w-56 bg-paper-light border-l border-ink/10 overflow-y-auto select-none ${className}`}>
      <div className="p-3">
        {/* Header */}
        <div className="font-military text-xs tracking-[0.12em] text-ink pb-1 mb-2 border-b border-ink/20">
          SYMBOLOGY
        </div>

        {/* Friendly Forces */}
        <Section title="FRIENDLY FORCES">
          <SymbolItem color="#4a7db4" label="Headquarters (HQ)" symbol="▣" />
          <SymbolItem color="#4a7db4" label="Infantry Company" symbol="╳" />
          <SymbolItem color="#4a7db4" label="Armor Platoon" symbol="○" />
          <SymbolItem color="#4a7db4" label="Artillery Battery" symbol="●" />
          <SymbolItem color="#4a7db4" label="Recon Team" symbol="◆" />
          <SymbolItem color="#4a7db4" label="Supply / Logistics" symbol="⊙" />
        </Section>

        {/* Enemy Forces */}
        <Section title="ENEMY FORCES">
          <SymbolItem color="#c41e3a" label="Enemy HQ" symbol="▣" />
          <SymbolItem color="#c41e3a" label="Enemy Infantry" symbol="╳" />
          <SymbolItem color="#c41e3a" label="Enemy Armor" symbol="○" />
          <SymbolItem color="#c41e3a" label="Enemy Artillery" symbol="●" />
          <SymbolItem color="#c41e3a" label="Stronghold" symbol="▣" />
        </Section>

        {/* Observation Posts */}
        <Section title="OBSERVATION POSTS">
          <div className="flex items-center gap-2 text-xs mb-1">
            <span className="w-5 h-5 flex items-center justify-center text-[10px] text-ink">◆</span>
            <span className="font-military text-[11px] text-ink/70">OP1 / OP2 / OP3</span>
          </div>
        </Section>

        {/* Routes */}
        <Section title="ROUTES">
          <div className="flex items-center gap-2 text-xs mb-1">
            <span className="w-6 h-0.5 bg-[#3b6fa0]" />
            <span className="font-military text-[11px] text-ink/70">Advance Axis</span>
          </div>
          <div className="flex items-center gap-2 text-xs mb-1">
            <span className="w-6 h-0.5 bg-[#3b6fa0] border-dashed" />
            <span className="font-military text-[11px] text-ink/70">Planned / Flanking</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="w-6 h-0.5 bg-[#c41e3a]" />
            <span className="font-military text-[11px] text-ink/70">Enemy Movement</span>
          </div>
        </Section>

        {/* Fire Support */}
        <Section title="FIRE SUPPORT">
          <div className="flex items-center gap-2 text-xs mb-1">
            <span className="w-4 h-4 rounded-full bg-friendly/20 border border-friendly/40" />
            <span className="font-military text-[11px] text-ink/70">Artillery Fan</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="w-4 h-4 rounded-full bg-enemy/10 border border-enemy/30" />
            <span className="font-military text-[11px] text-ink/70">Mortar Coverage</span>
          </div>
        </Section>

        {/* Terrain */}
        <Section title="TERRAIN">
          <div className="flex flex-wrap gap-1.5">
            <Swatch color="#b5c8d8" label="Water" />
            <Swatch color="#c8cdc3" label="Wetland" />
            <Swatch color="#d2cdba" label="Plain" />
            <Swatch color="#3a7540" label="Forest" />
            <Swatch color="#b4b096" label="Hills" />
            <Swatch color="#9b8c64" label="Highland" />
            <Swatch color="#8c7855" label="Mountain" />
          </div>
          <div className="mt-2 text-[10px] font-mono text-ink/60">
            Contour Interval: 50m
          </div>
        </Section>
      </div>
    </aside>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div className="font-military text-[10px] tracking-[0.1em] text-ink-light mb-1.5 border-b border-ink/10 pb-0.5">
        {title}
      </div>
      {children}
    </div>
  );
}

function SymbolItem({ color, label, symbol }: { color: string; label: string; symbol: string }) {
  return (
    <div className="flex items-center gap-2 text-xs mb-1">
      <span className="w-5 h-5 flex items-center justify-center rounded-sm text-[10px] text-white font-bold" style={{ backgroundColor: color }}>
        {symbol}
      </span>
      <span className="font-military text-[11px] text-ink/70">{label}</span>
    </div>
  );
}

function Swatch({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1">
      <span className="w-3 h-3 rounded-sm border border-ink/20" style={{ backgroundColor: color }} />
      <span className="text-[10px] font-military text-ink/60">{label}</span>
    </div>
  );
}
