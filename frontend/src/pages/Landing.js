import { useNavigate } from 'react-router-dom';
import BrandEmblem from '../components/BrandEmblem';
import { ManaPipRow } from '../components/ManaSymbols';

const entryPoints = [
  {
    number: '01',
    tone: 'gold',
    eyebrow: 'I have a list',
    title: 'Analyze a deck',
    description: 'Import a Commander list, confirm what must stay true, then review evidence-backed adds, cuts, and swaps.',
    action: 'Start with a deck',
  },
  {
    number: '02',
    tone: 'blue',
    eyebrow: 'I have a commander',
    title: 'Study the game plan',
    description: 'Turn a commander into clear themes, pilot notes, role coverage, and cards chosen for the actual plan.',
    action: 'Open Commander Lab',
  },
  {
    number: '03',
    tone: 'green',
    eyebrow: 'I need an idea',
    title: 'Discover a build',
    description: 'Explore legal commanders by color, mana value, and strategy without starting from a generic card dump.',
    action: 'Discover commanders',
  },
];

const workflow = [
  ['Import', 'Bring in a public list or paste one directly.'],
  ['Interpret', 'Confirm budget, power, strategy, and intentional constraints.'],
  ['Evaluate', 'Check structure, role quality, curve, synergy, and legality.'],
  ['Improve', 'Compare focused upgrades with the reasoning kept in view.'],
];

export default function Landing() {
  const navigate = useNavigate();
  const begin = () => navigate('/auth');

  return (
    <div className="app-shell landing-shell">
      <header className="landing-topbar">
        <div className="container mx-auto px-6 landing-topbar-layout">
          <button type="button" className="topbar-brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <BrandEmblem className="topbar-brand-mark" />
            <span className="brand-title">LandFall AI</span>
          </button>
          <div className="landing-header-actions">
            <button
              type="button"
              className="landing-header-link"
              onClick={() => document.getElementById('workflow')?.scrollIntoView({ behavior: 'smooth' })}
            >
              How it works
            </button>
            <button data-testid="header-login-btn" onClick={begin} className="btn-secondary landing-login-button">
              Sign in
            </button>
          </div>
        </div>
      </header>

      <main>
        <section className="landing-hero-v2 px-6">
          <div className="container mx-auto max-w-7xl landing-hero-grid">
            <div className="landing-hero-copy">
              <p className="page-eyebrow mb-5">Commander decisions, explained</p>
              <h1 data-testid="hero-title" className="landing-display-title">
                Build with <span className="accent-gold">intent.</span><br />
                Improve with <span className="accent-blue">evidence.</span>
              </h1>
              <p data-testid="hero-subtitle" className="landing-hero-lead">
                LandFall turns a Commander list into a focused deck-tech: what the deck is doing, where it is vulnerable, and which changes best support the plan you actually want to play.
              </p>
              <div className="landing-hero-actions">
                <button data-testid="get-started-btn" onClick={begin} className="btn-primary">
                  Analyze your first deck
                </button>
                <button
                  data-testid="learn-more-btn"
                  className="btn-secondary"
                  onClick={() => document.getElementById('start')?.scrollIntoView({ behavior: 'smooth' })}
                >
                  Explore the tools
                </button>
              </div>
              <div className="landing-trust-row" aria-label="Product principles">
                <span>Deterministic scoring</span>
                <span>Commander legality</span>
                <span>Deck intent preserved</span>
              </div>
            </div>

            <div className="landing-product-preview" aria-label="Example LandFall recommendation">
              <div className="preview-heading">
                <div>
                  <span className="preview-label">Deck review</span>
                  <h2>Meren recursion</h2>
                </div>
                <ManaPipRow colors={['B', 'G']} compact />
              </div>
              <div className="preview-summary-row">
                <div><strong>100</strong><span>cards</span></div>
                <div><strong>36</strong><span>lands</span></div>
                <div><strong>7</strong><span>power</span></div>
                <div><strong>$3</strong><span>card cap</span></div>
              </div>
              <div className="preview-board">
                <div className="preview-card-stack" aria-hidden="true">
                  <div className="preview-card preview-card-back"></div>
                  <div className="preview-card preview-card-front">
                    <span>ENGINE</span>
                    <strong>Graveyard<br />value</strong>
                    <small>12 supported signals</small>
                  </div>
                </div>
                <div className="preview-recommendation">
                  <span className="preview-status">Best next change</span>
                  <h3>More repeatable sacrifice</h3>
                  <p>
                    The deck has recursion payoffs but too few free outlets to control when creatures reach the graveyard.
                  </p>
                  <div className="preview-swap">
                    <span><b>Add</b> Viscera Seer</span>
                    <span><b>Cut</b> low-impact six-drop</span>
                  </div>
                  <small>High evidence · preserves budget and recursion plan</small>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="start" className="landing-section px-6">
          <div className="container mx-auto max-w-7xl">
            <div className="landing-section-heading">
              <div>
                <p className="page-eyebrow mb-3">Choose a starting point</p>
                <h2>What are you working on?</h2>
              </div>
              <p>Each path uses the same strategy and evidence systems, tuned to the context you already have.</p>
            </div>
            <div className="landing-entry-grid">
              {entryPoints.map((entry) => (
                <button
                  key={entry.number}
                  type="button"
                  className={`landing-entry-card entry-${entry.tone}`}
                  onClick={begin}
                >
                  <span className="landing-entry-number">{entry.number}</span>
                  <span className="landing-entry-eyebrow">{entry.eyebrow}</span>
                  <strong>{entry.title}</strong>
                  <span className="landing-entry-description">{entry.description}</span>
                  <span className="landing-entry-action">{entry.action} <b aria-hidden="true">→</b></span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section id="workflow" className="landing-section landing-workflow-section px-6">
          <div className="container mx-auto max-w-7xl landing-workflow-layout">
            <div className="landing-workflow-intro">
              <p className="page-eyebrow mb-3">From list to decision</p>
              <h2>A deck-tech flow that keeps your intent in the room.</h2>
              <p>
                Recommendations are useful only when the engine understands the deck before trying to optimize it.
              </p>
            </div>
            <ol className="landing-workflow-list">
              {workflow.map(([title, description], index) => (
                <li key={title}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <div>
                    <strong>{title}</strong>
                    <p>{description}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="landing-section px-6">
          <div className="container mx-auto max-w-7xl landing-evidence-grid">
            <article className="evidence-lead-card">
              <p className="page-eyebrow">Why this card?</p>
              <h2>The reasoning is part of the result.</h2>
              <p>
                Every recommendation should connect to a detected need, commander relationship, deck constraint, or measurable role gap—not just a popular search result.
              </p>
            </article>
            <article className="evidence-detail-card">
              <span>01</span>
              <h3>Fit before popularity</h3>
              <p>Cards rank for the job and plan they support in this deck.</p>
            </article>
            <article className="evidence-detail-card">
              <span>02</span>
              <h3>Constraints stay visible</h3>
              <p>Budget, pet cards, jank, politics, and protected packages shape the answer.</p>
            </article>
            <article className="evidence-detail-card">
              <span>03</span>
              <h3>Uncertainty is honest</h3>
              <p>Limited lists and weak evidence lower confidence instead of inviting false precision.</p>
            </article>
          </div>
        </section>

        <section className="landing-section px-6" data-nosnippet>
          <div className="container mx-auto max-w-5xl landing-support-panel">
            <div>
              <p className="page-eyebrow mb-3">Built for the Commander table</p>
              <h2>Free to use. Focused on better decisions.</h2>
              <p>Support helps keep card data, imports, and analysis available to the community.</p>
            </div>
            <div className="landing-support-actions">
              <button data-testid="start-analyzing-btn" onClick={begin} className="btn-primary">Start tuning</button>
              <button
                data-testid="donate-btn"
                onClick={() => window.open('https://ko-fi.com/myndgoblyn', '_blank')}
                className="btn-secondary"
              >
                Support on Ko-fi
              </button>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer px-6">
        <div className="container mx-auto max-w-7xl">
          <span>© 2026 LandFall AI</span>
          <span>Built for the EDH community.</span>
        </div>
      </footer>
    </div>
  );
}
