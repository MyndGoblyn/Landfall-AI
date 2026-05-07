export default function ForestManaIcon({ className = "w-8 h-8" }) {
  return (
    <svg className={className} viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Outer circle - stained glass frame */}
      <circle cx="50" cy="50" r="48" fill="#1a4d2e" stroke="#4a7c59" strokeWidth="2"/>
      
      {/* Inner stained glass segments - tree pattern */}
      <path d="M50 20 L50 35 L40 35 L50 50 L35 50 L50 70 L65 50 L50 50 L60 35 L50 35 Z" 
            fill="#2d5a3a" stroke="#6b9e78" strokeWidth="1.5"/>
      
      {/* Highlight segments - stained glass effect */}
      <path d="M50 20 L50 35 L45 30 Z" fill="#4a8259" opacity="0.7"/>
      <path d="M50 35 L60 35 L55 30 Z" fill="#3d6e4a" opacity="0.6"/>
      <path d="M40 35 L50 50 L45 42 Z" fill="#5a9668" opacity="0.8"/>
      <path d="M60 35 L50 50 L55 42 Z" fill="#5a9668" opacity="0.8"/>
      <path d="M35 50 L50 70 L42 60 Z" fill="#72b585" opacity="0.7"/>
      <path d="M65 50 L50 70 L58 60 Z" fill="#72b585" opacity="0.7"/>
      
      {/* Dark segments for depth */}
      <path d="M50 50 L50 70 L48 60 Z" fill="#1e4a32" opacity="0.5"/>
      
      {/* Trunk at bottom */}
      <rect x="47" y="70" width="6" height="12" fill="#3d2f1f" stroke="#5c4a3a" strokeWidth="1"/>
      
      {/* Inner glow circle */}
      <circle cx="50" cy="50" r="48" fill="none" stroke="#8fbc8f" strokeWidth="1" opacity="0.3"/>
    </svg>
  );
}
