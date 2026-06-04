export function UrbanLegendPanel() {
  return (
    <aside className="w-56 bg-paper-light border-l border-ink/10 overflow-y-auto select-none">
      <div className="p-3">
        <div className="font-military text-xs tracking-[0.12em] text-ink pb-1 mb-2 border-b border-ink/20">
          CAMPUS LEGEND
        </div>

        <Section title="BUILDINGS">
          <Swatch color="#c8bda0" label="Headquarters" />
          <Swatch color="#d0c8b0" label="Research Lab" />
          <Swatch color="#ccc4a8" label="Office Tower" />
          <Swatch color="#cdc4a8" label="Innovation Center" />
          <Swatch color="#c4baa0" label="Data Center" />
          <Swatch color="#d2c8b0" label="Conference Center" />
          <Swatch color="#d4ccb4" label="Exhibition Hall" />
          <Swatch color="#d8d0b8" label="Cafeteria" />
        </Section>

        <Section title="ROADS">
          <div className="flex items-center gap-2 text-xs mb-0.5">
            <span className="w-6" style={{ height: '2.5px', background: '#3a3a3a' }} />
            <span className="font-military text-[10px] text-ink/70">Ring Road</span>
          </div>
          <div className="flex items-center gap-2 text-xs mb-0.5">
            <span className="w-6" style={{ height: '1.8px', background: '#4a4a4a' }} />
            <span className="font-military text-[10px] text-ink/70">Main Avenue</span>
          </div>
          <div className="flex items-center gap-2 text-xs mb-0.5">
            <span className="w-6" style={{ height: '1px', background: '#6b6b6b' }} />
            <span className="font-military text-[10px] text-ink/70">Internal Road</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="w-6" style={{ height: '0.6px', background: '#999', borderBottom: '1px dashed #999' }} />
            <span className="font-military text-[10px] text-ink/70">Pedestrian Path</span>
          </div>
        </Section>

        <Section title="GREEN & WATER">
          <Swatch color="#8aaa7a" label="Green Space / Park" />
          <Swatch color="#9ab8c8" label="Lake / Canal / Pond" />
        </Section>

        <Section title="FACILITIES">
          <div className="flex items-center gap-2 text-xs mb-0.5">
            <span className="font-bold text-[10px] text-[#c41e3a]">M</span>
            <span className="font-military text-[10px] text-ink/70">Metro Entrance</span>
          </div>
          <div className="flex items-center gap-2 text-xs mb-0.5">
            <span className="w-3 h-3 border border-[#3b82f6]" />
            <span className="font-military text-[10px] text-ink/70">Shuttle Station</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="font-bold text-[8px]">P</span>
            <span className="font-military text-[10px] text-ink/70">Parking Hub</span>
          </div>
        </Section>

        <Section title="ZONES">
          <Swatch color="#efe4d4" label="Headquarters" />
          <Swatch color="#ede6da" label="Research Zone" />
          <Swatch color="#eee5d8" label="Office District" />
          <Swatch color="#ece4d6" label="Innovation Center" />
          <Swatch color="#e8e0d2" label="Data Center" />
          <Swatch color="#f0e8dc" label="Residential Area" />
          <Swatch color="#e2dfd8" label="Lake District" />
        </Section>
      </div>
    </aside>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div className="font-military text-[10px] tracking-[0.1em] text-ink-light mb-1 border-b border-ink/10 pb-0.5">
        {title}
      </div>
      {children}
    </div>
  );
}

function Swatch({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1 mb-0.5">
      <span className="w-3 h-3 rounded-sm border border-ink/20" style={{ backgroundColor: color }} />
      <span className="text-[10px] font-military text-ink/60">{label}</span>
    </div>
  );
}
