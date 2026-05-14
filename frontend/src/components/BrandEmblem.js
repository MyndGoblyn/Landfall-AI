import landfallEmblem from '../assets/landfall-ai-emblem.png';

export default function BrandEmblem({ className = '', alt = 'LandFall AI emblem' }) {
  return (
    <img
      src={landfallEmblem}
      alt={alt}
      className={`brand-emblem ${className}`}
      loading="eager"
      decoding="async"
    />
  );
}
