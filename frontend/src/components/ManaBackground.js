import './ManaBackground.css';

export default function ManaBackground() {
  return (
    <div 
      className="mana-background-gradient"
      style={{
        background: 'radial-gradient(circle at center, #00a852 0%, #00733e 50%, #004d29 100%)',
      }}
    />
  );
}
