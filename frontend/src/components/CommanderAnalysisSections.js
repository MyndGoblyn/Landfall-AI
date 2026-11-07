import { useEffect, useMemo, useState } from 'react';
import { Info } from 'lucide-react';

function useActiveSection(sections) {
  const [activeId, setActiveId] = useState(sections[0]?.id || '');

  useEffect(() => {
    if (!sections.some((section) => section.id === activeId)) {
      setActiveId(sections[0]?.id || '');
    }
  }, [activeId, sections]);

  const activeSection = sections.find((section) => section.id === activeId) || sections[0];
  return [activeSection, activeId, setActiveId];
}

export function SectionTabs({ sections, activeId, onChange, ariaLabel = 'Analysis sections' }) {
  if (sections.length <= 1) return null;

  return (
    <div className="section-pager-tabs" role="tablist" aria-label={ariaLabel}>
      {sections.map((section) => (
        <button
          key={section.id}
          type="button"
          className={`section-pager-tab ${activeId === section.id ? 'active' : ''}`}
          aria-selected={activeId === section.id}
          data-testid={`section-tab-${section.id}`}
          onClick={() => onChange(section.id)}
        >
          <span>{section.label}</span>
          <span className="section-pager-count">
            {section.tips?.length || section.cards?.length || 0}
          </span>
        </button>
      ))}
    </div>
  );
}

export function StrategyPager({ commanderData }) {
  const sections = useMemo(() => {
    const backendSections = commanderData?.strategy_sections || [];
    if (backendSections.length > 0) return backendSections;

    const tips = commanderData?.strategy_tips || [];
    return tips.length > 0 ? [{ id: 'strategy', label: 'Strategy', tips }] : [];
  }, [commanderData]);

  const [activeSection, activeId, setActiveId] = useActiveSection(sections);

  if (!activeSection) {
    return <p className="page-copy">No strategy notes are available yet.</p>;
  }

  return (
    <div className="section-pager">
      <SectionTabs sections={sections} activeId={activeId} onChange={setActiveId} />
      <div className="space-y-3">
        {activeSection.tips.map((tip, idx) => (
          <div key={`${activeSection.id}-${idx}`} className="strategy-note">
            <span className="strategy-note-index">{String(idx + 1).padStart(2, '0')}</span>
            <p className="text-gray-100">{tip}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function CoverageNotice({ data }) {
  const level = data?.coverage_level;
  if (level !== 'exploratory') return null;

  const note = (data?.coverage_notes || '')
    .replace(/^Exploratory coverage:\s*/i, '')
    .replace(/^Exploratory\s*/i, '');

  return (
    <div className={`coverage-notice coverage-${level}`} data-testid="coverage-notice">
      <Info className="coverage-notice-icon" />
      <div className="coverage-notice-copy">
        <div className="coverage-notice-title">Limited strategy signal</div>
        <p>
          {note || 'The rules text does not identify one clear build-around plan, so the recommendations are intentionally narrower.'}
        </p>
      </div>
    </div>
  );
}

export function ThemeEvidence({ commanderData }) {
  const evidence = (commanderData?.theme_evidence || [])
    .filter((item) => item.tier === 'primary' || item.tier === 'supporting');
  const fallback = (commanderData?.synergies || []).map((id) => ({
    id,
    label: id.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
    tier: 'primary',
  }));
  const themes = evidence.length > 0 ? evidence : fallback;
  const groups = [
    { tier: 'primary', label: 'Primary plan' },
    { tier: 'supporting', label: 'Supporting themes' },
  ].map((group) => ({
    ...group,
    themes: themes.filter((item) => item.tier === group.tier),
  })).filter((group) => group.themes.length > 0);

  if (groups.length === 0) {
    return <p className="page-copy">No reliable build-around theme cleared the evidence floor.</p>;
  }

  return (
    <div className="space-y-5" data-testid="theme-evidence">
      {groups.map((group) => (
        <div key={group.tier}>
          <p className="page-eyebrow mb-2">{group.label}</p>
          <div className="grid gap-2">
            {group.themes.map((theme) => (
              <div key={theme.id} className="tip-panel p-3">
                <span className="font-semibold">{theme.label}</span>
                {theme.reason && <p className="page-copy text-sm mt-1">{theme.reason}</p>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function RecommendedCardsPager({
  commanderData,
  emptyMessage,
  onFindMore,
  findMoreLoading = false,
  findMoreDisabled = false,
}) {
  const sections = useMemo(() => {
    const backendSections = commanderData?.recommended_sections || [];
    if (backendSections.length > 0) return backendSections;

    const cards = commanderData?.suggested_cards || [];
    return cards.length > 0 ? [{ id: 'cards', label: 'Recommended', cards }] : [];
  }, [commanderData]);

  const [activeSection, activeId, setActiveId] = useActiveSection(sections);

  if (!activeSection) {
    return <p className="page-copy">{emptyMessage}</p>;
  }

  return (
    <div className="section-pager">
      <SectionTabs sections={sections} activeId={activeId} onChange={setActiveId} />
      <div className="grid md:grid-cols-2 gap-4">
        {activeSection.cards.map((card, idx) => (
          <div key={`${activeSection.id}-${card.name}-${idx}`} className="card deck-card-theme commander-recommendation-card">
            <div className={`commander-card-images ${card.image_url_back ? 'double-faced' : ''}`}>
              {card.image_url && (
                <img
                  src={card.image_url}
                  alt={card.name}
                  className="commander-card-image"
                />
              )}
              {card.image_url_back && (
                <img
                  src={card.image_url_back}
                  alt={`${card.name} (back)`}
                  className="commander-card-image"
                />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-3 mb-2">
                <h4 className="font-semibold text-lg">{card.name}</h4>
              </div>
              <p className="text-sm page-copy mb-3">{card.reason}</p>
              <div className="flex gap-2 text-xs flex-wrap">
                {card.recommendation_lane && (
                  <span className="theme-pill">
                    {card.recommendation_lane === 'plan' ? 'Core plan' : 'Deck support'}
                  </span>
                )}
                <span className="theme-pill">{card.job || card.role}</span>
                <span className="theme-pill">Mana Value {card.cmc}</span>
              </div>
              {card.reason_facts?.limitations?.[0] && (
                <p className="page-copy text-xs mt-2">
                  Caveat: {card.reason_facts.limitations[0]}.
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
      {onFindMore && (
        <div className="find-more-row">
          <button
            type="button"
            className="btn-secondary px-5 py-3"
            onClick={onFindMore}
            disabled={findMoreLoading || findMoreDisabled}
          >
            {findMoreLoading ? 'Searching deeper...' : 'Find More Cards'}
          </button>
          <p className="page-copy text-sm">
            More cards runs a broader deterministic search, validates extra evidence, and may take longer.
          </p>
        </div>
      )}
    </div>
  );
}
