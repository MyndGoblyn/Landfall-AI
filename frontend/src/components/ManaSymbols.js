import { Diamond, Flame, Leaf, Skull, Sun, Waves } from 'lucide-react';

const manaMeta = {
  W: { label: 'White', Icon: Sun },
  U: { label: 'Blue', Icon: Waves },
  B: { label: 'Black', Icon: Skull },
  R: { label: 'Red', Icon: Flame },
  G: { label: 'Green', Icon: Leaf },
  C: { label: 'Colorless', Icon: Diamond }
};

export function ManaPip({ color = 'C', className = '' }) {
  const normalized = manaMeta[color] ? color : 'C';
  const { label, Icon } = manaMeta[normalized];

  return (
    <span
      className={`mana-dot mana-dot-${normalized} ${className}`.trim()}
      title={`${label} mana`}
      aria-label={`${label} mana`}
    >
      <Icon className="mana-glyph" aria-hidden="true" />
    </span>
  );
}

export function ManaPipRow({ colors = [], compact = false, className = '' }) {
  const identity = colors.length ? colors : ['C'];

  return (
    <span
      className={`mana-symbol-row ${compact ? 'compact' : ''} ${className}`.trim()}
      aria-label={`Color identity ${identity.join('')}`}
    >
      {identity.map((color, idx) => (
        <ManaPip key={`${color}-${idx}`} color={color} />
      ))}
    </span>
  );
}
