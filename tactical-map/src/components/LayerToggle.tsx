import type { LayerVisibility } from '../types';

interface LayerToggleProps {
  visibility: LayerVisibility;
  onChange: (v: LayerVisibility) => void;
}

const layers: { key: keyof LayerVisibility; label: string }[] = [
  { key: 'terrain', label: 'TERRAIN' },
  { key: 'contours', label: 'CONTOURS' },
  { key: 'rivers', label: 'RIVERS' },
  { key: 'forests', label: 'FORESTS' },
  { key: 'roads', label: 'ROADS' },
  { key: 'settlements', label: 'SETTLEMENTS' },
  { key: 'grid', label: 'GRID' },
  { key: 'symbols', label: 'UNIT SYMBOLS' },
  { key: 'routes', label: 'ROUTES' },
  { key: 'fireFans', label: 'FIRE COVERAGE' },
  { key: 'labels', label: 'ANNOTATIONS' },
  { key: 'sectors', label: 'SECTORS' },
];

export function LayerToggle({ visibility, onChange }: LayerToggleProps) {
  const toggle = (key: keyof LayerVisibility) => {
    onChange({ ...visibility, [key]: !visibility[key] });
  };

  return (
    <div className="absolute top-2 left-2 bg-paper-light/95 border border-ink/15 px-2 py-1.5 select-none">
      <div className="font-military text-[9px] tracking-[0.1em] text-ink/50 mb-1">LAYERS</div>
      <div className="flex flex-col gap-0.5">
        {layers.map(({ key, label }) => (
          <label key={key} className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={visibility[key]}
              onChange={() => toggle(key)}
              className="w-2.5 h-2.5 accent-ink"
            />
            <span className="font-military text-[9px] text-ink/70">{label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
