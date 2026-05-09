import { BrainCircuit, Clock3, Database, Layers3, Search, Sparkles, Target, Wrench } from 'lucide-react';
import AppTopbar from '../components/AppTopbar';

const principles = [
  {
    Icon: BrainCircuit,
    title: 'Deterministic Intelligence',
    copy: 'LandFall AI does not generate strategy through an LLM. It uses rule-based detection, card text parsing, commander legality checks, Scryfall search syntax, and scoring layers that produce repeatable results from the same inputs.'
  },
  {
    Icon: Database,
    title: 'Scryfall Grounding',
    copy: 'Card identity, legality, type lines, oracle text, images, and candidate pools come from Scryfall data. The app narrows that pool with Commander legality, color identity, type, role, and theme filters.'
  },
  {
    Icon: Target,
    title: 'Theme Matching',
    copy: 'The engine looks for mechanical signals such as landfall, sacrifice, counters, blink, tokens, artifacts, spellslinger, graveyard use, Voltron pressure, and board-conversion plans, then ranks cards by how directly they support those signals.'
  },
  {
    Icon: Wrench,
    title: 'Human Check Still Matters',
    copy: 'The system is designed to imitate logical deck-tech reasoning, not replace the pilot. It can miss table context, budget goals, pet cards, local meta pressure, or very new mechanical patterns until the rules are refined.'
  }
];

const modes = [
  {
    Icon: Search,
    title: 'Regular Search',
    copy: 'Regular search prioritizes speed. It detects the commander, identifies the strongest themes, returns focused strategy notes, and shows a small set of high-confidence recommendations.'
  },
  {
    Icon: Sparkles,
    title: 'Deep Strategy',
    copy: 'Deep Strategy spends more time on expanded semantic passes and deeper strategy sections. It may search broader card pools, inspect more role evidence, and produce more detailed planning guidance.'
  },
  {
    Icon: Clock3,
    title: 'Why Deep Runs Take Longer',
    copy: 'More checks mean more Scryfall queries, more filtering, and more scoring. The tradeoff is better coverage and richer strategy notes, but the response time will be longer than a regular lookup.'
  }
];

const expectations = [
  'Recommended cards are intentionally limited at first so the app stays responsive and avoids overwhelming the user.',
  'Use Find More Cards when you want the engine to spend extra time looking beyond the first sharp set.',
  'Deck Analysis focuses on role balance, curve, lands, upgrade candidates, possible cuts, and commander-facing themes.',
  'Random Commander uses color identity, mana value, and keyword constraints to build Scryfall searches before the same strategy layer evaluates the result.',
  'When a broad commander name has multiple possible matches, Commander Lookup can offer specific Scryfall-backed card choices.'
];

export default function HowItWorks() {
  return (
    <div className="app-shell">
      <AppTopbar />

      <main className="container mx-auto px-6 py-12 max-w-6xl">
        <section className="page-hero mb-10">
          <p className="page-eyebrow mb-2">System Notes</p>
          <h2 className="text-4xl font-bold mb-4 page-title">How LandFall AI Works</h2>
          <p className="page-copy text-lg max-w-3xl">
            The app is built around deterministic Commander reasoning: structured rules, Scryfall data, repeatable scoring, and theme-specific heuristics tuned over time.
          </p>
        </section>

        <section className="info-grid mb-10">
          {principles.map(({ Icon, title, copy }) => (
            <article key={title} className="info-panel">
              <div className="info-icon"><Icon className="w-5 h-5" /></div>
              <h3>{title}</h3>
              <p>{copy}</p>
            </article>
          ))}
        </section>

        <section className="glass-panel p-6 mb-10">
          <div className="section-heading compact">
            <div>
              <p className="page-eyebrow">Search Modes</p>
              <h3>Speed vs Depth</h3>
            </div>
          </div>
          <div className="mode-grid">
            {modes.map(({ Icon, title, copy }) => (
              <article key={title} className="mode-panel">
                <Icon className="w-6 h-6 text-amber-300" />
                <h4>{title}</h4>
                <p>{copy}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="glass-panel p-6">
          <div className="section-heading compact">
            <div>
              <p className="page-eyebrow">Good To Know</p>
              <h3>Using the Results</h3>
            </div>
          </div>
          <div className="expectation-list">
            {expectations.map((item, index) => (
              <div key={item} className="expectation-row">
                <span>{index + 1}</span>
                <p>{item}</p>
              </div>
            ))}
          </div>
          <div className="tip-panel p-4 mt-6">
            <div className="flex gap-3 items-start">
              <Layers3 className="w-5 h-5 text-amber-300 mt-1 shrink-0" />
              <p className="text-sm text-gray-100">
                Quality improves through broader semantic profiles, tighter rejection rules, and better scoring evidence. That keeps the product free to run while still moving closer to deck-tech-style reasoning.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
