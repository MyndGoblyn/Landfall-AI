import landfallLogo from '../assets/landfall-ai-logo.png';

export default function BrandLogo({ className = '', alt = 'LandFall AI' }) {
  return (
    <img
      src={landfallLogo}
      alt={alt}
      className={`brand-logo ${className}`}
      loading="eager"
      decoding="async"
    />
  );
}
