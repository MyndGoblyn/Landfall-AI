import { useNavigate } from 'react-router-dom';
import { Heart, LibraryBig, Sparkles, Target, TrendingUp, Zap } from 'lucide-react';
import BrandEmblem from '../components/BrandEmblem';
import BrandLogo from '../components/BrandLogo';
import { ManaPipRow } from '../components/ManaSymbols';

export default function Landing() {
  const navigate = useNavigate();

  const features = [
    {
      icon: <Zap className="w-8 h-8 text-amber-300" />,
      title: 'Fast Imports',
      description: 'Bring in public Archidekt or Moxfield lists and keep quantities, lands, and commander identity intact.'
    },
    {
      icon: <Target className="w-8 h-8 text-emerald-300" />,
      title: 'Upgrade Slots',
      description: 'Review adds, cuts, and swap conversations with role labels that match Commander deckbuilding.'
    },
    {
      icon: <TrendingUp className="w-8 h-8 text-green-300" />,
      title: 'Deck Health',
      description: 'Check draw, ramp, removal, curve, lands, and theme density from one deck-tech view.'
    },
    {
      icon: <Sparkles className="w-8 h-8 text-violet-300" />,
      title: 'Commander Tools',
      description: 'Look up commanders or generate a random build-around with synergy-aware recommendations.'
    }
  ];

  return (
    <div className="app-shell">
      <header className="fixed top-0 w-full z-50 app-topbar">
        <div className="container mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <BrandEmblem className="topbar-brand-mark" />
            <h1 className="text-2xl font-bold brand-title">LandFall AI</h1>
          </div>
          <button data-testid="header-login-btn" onClick={() => navigate('/auth')} className="btn-secondary">
            Login
          </button>
        </div>
      </header>

      <section className="landing-hero-section px-6">
        <div className="container mx-auto text-center max-w-5xl page-hero landing-hero-panel">
          <div className="landing-brand-masthead">
            <BrandLogo className="landing-brand-logo mx-auto" />
          </div>
          <div className="landing-hero-content">
            <ManaPipRow colors={['W', 'U', 'B', 'R', 'G']} className="hero-mana-row" />
            <p className="page-eyebrow mb-4">Commander deck tech and upgrade mapping</p>
            <h2 data-testid="hero-title" className="text-5xl sm:text-6xl lg:text-7xl font-bold mb-6 leading-tight page-title">
              Tune Your Commander Deck
              <span className="block text-amber-300">Like a Deck Tech</span>
            </h2>
            <p data-testid="hero-subtitle" className="text-lg sm:text-xl page-copy mb-10 max-w-3xl mx-auto">
              LandFall AI is an MTG Commander deckbuilding assistant for importing decks, analyzing strategy gaps, finding synergistic card upgrades, and exploring commanders with deterministic recommendations.
            </p>
            <div className="flex gap-4 justify-center flex-wrap">
              <button data-testid="get-started-btn" onClick={() => navigate('/auth')} className="btn-primary text-lg px-8 py-4">
                Get Started Free
              </button>
              <button
                data-testid="learn-more-btn"
                className="btn-secondary text-lg px-8 py-4"
                onClick={() => document.getElementById('features').scrollIntoView({ behavior: 'smooth' })}
              >
                See Tools
              </button>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="py-20 px-6">
        <div className="container mx-auto max-w-6xl">
          <p className="page-eyebrow text-center mb-3">What the engine checks</p>
          <h3 className="text-4xl sm:text-5xl font-bold text-center mb-16 page-title">Your Digital Deck Table</h3>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, idx) => (
              <div key={idx} className="card tool-card zone-card" data-zone={feature.title.toUpperCase()}>
                <div className="zone-rune">{idx + 1}</div>
                <div className="flex justify-center mb-4">{feature.icon}</div>
                <h4 className="text-xl font-semibold mb-3">{feature.title}</h4>
                <p className="page-copy text-sm">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-20 px-6">
        <div className="container mx-auto max-w-4xl">
          <div className="glass-panel p-12 text-center">
            <LibraryBig className="w-16 h-16 text-amber-300 mx-auto mb-6" />
            <p className="page-eyebrow mb-3">Keep the table open</p>
            <h3 className="text-4xl sm:text-5xl font-bold mb-6 page-title">Support LandFall AI</h3>
            <p className="text-xl page-copy mb-8">
              LandFall AI is free for Commander players. Support helps keep imports, card data, and analysis tools moving.
            </p>
            <div className="flex gap-4 justify-center flex-wrap">
              <button
                data-testid="donate-btn"
                onClick={() => window.open('https://ko-fi.com/myndgoblyn', '_blank')}
                className="btn-primary text-lg px-10 py-4"
              >
                <Heart className="w-5 h-5 inline mr-2" />
                Donate via Ko-fi
              </button>
              <button data-testid="start-analyzing-btn" onClick={() => navigate('/auth')} className="btn-secondary text-lg px-10 py-4">
                Start Tuning
              </button>
            </div>
          </div>
        </div>
      </section>

      <footer className="py-8 px-6 border-t border-amber-400/20">
        <div className="container mx-auto text-center page-copy text-sm">
          © 2025 LandFall AI. Built for the EDH community.
        </div>
      </footer>
    </div>
  );
}
