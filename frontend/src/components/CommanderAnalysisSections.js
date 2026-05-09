import { useEffect, useMemo, useState } from 'react';
import { Sparkles } from 'lucide-react';

function useActiveSection(sections, resetKey) {
  const [activeId, setActiveId] = useState(sections[0]?.id || '');

  useEffect(() => {
    setActiveId(sections[0]?.id || '');
  }, [resetKey, sections]);

  const activeSection = sections.find((section) => section.id === activeId) || sections[0];
  return [activeSection, activeId, setActiveId];
}

function SectionTabs({ sections, activeId, onChange }) {
  if (sections.length <= 1) return null;

  return (
    <div className="section-pager-tabs" role="tablist" aria-label="Analysis sections">
      {sections.map((section) => (
        <button
          key={section.id}
          type="button"
          className={`section-pager-tab ${activeId === section.id ? 'active' : ''}`}
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

  const resetKey = `${commanderData?.name || 'none'}-${commanderData?.analysis_depth || 'fast'}-strategy`;
  const [activeSection, activeId, setActiveId] = useActiveSection(sections, resetKey);

  if (!activeSection) {
    return <p className="page-copy">No strategy notes are available yet.</p>;
  }

  return (
    <div className="section-pager">
      <SectionTabs sections={sections} activeId={activeId} onChange={setActiveId} />
      <div className="space-y-3">
        {activeSection.tips.map((tip, idx) => (
          <div key={`${activeSection.id}-${idx}`} className="flex gap-3">
            <Sparkles className="w-5 h-5 text-amber-300 flex-shrink-0 mt-1" />
            <p className="text-gray-100">{tip}</p>
          </div>
        ))}
      </div>
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

  const resetKey = `${commanderData?.name || 'none'}-${commanderData?.analysis_depth || 'fast'}-cards`;
  const [activeSection, activeId, setActiveId] = useActiveSection(sections, resetKey);

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
                {card.score && <span className="recommendation-score">{card.score}</span>}
              </div>
              <p className="text-sm page-copy mb-3">{card.reason}</p>
              <div className="flex gap-2 text-xs flex-wrap">
                {card.fit_tier && <span className="theme-pill">{card.fit_tier}</span>}
                <span className="theme-pill">{card.job || card.role}</span>
                {card.evidence && <span className="theme-pill">{card.evidence}</span>}
                <span className="theme-pill">Mana Value {card.cmc}</span>
              </div>
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
            More cards runs a broader deterministic search and may take longer.
          </p>
        </div>
      )}
    </div>
  );
}
