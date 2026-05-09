import { useMemo, useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import {
  BarChart3,
  Download,
  ExternalLink,
  MinusCircle,
  PlusCircle,
  Shield,
  Sparkles,
  Swords,
  TrendingDown,
  TrendingUp,
  Zap
} from 'lucide-react';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import AppTopbar from '../components/AppTopbar';
import { ManaPipRow } from '../components/ManaSymbols';
import { API } from '../lib/api';
import useRotatingStatus from '../hooks/useRotatingStatus';

const roleMeta = {
  counters: { label: 'Counters', className: 'role-counters', Icon: Sparkles },
  draw: { label: 'Card Draw', className: 'role-draw', Icon: BarChart3 },
  ramp: { label: 'Ramp', className: 'role-ramp', Icon: Zap },
  removal: { label: 'Removal', className: 'role-removal', Icon: Swords },
  sweeper: { label: 'Sweeper', className: 'role-sweeper', Icon: Swords },
  protection: { label: 'Protection', className: 'role-protection', Icon: Shield },
  interaction: { label: 'Interaction', className: 'role-interaction', Icon: Shield },
  synergy_optimization: { label: 'Theme Fit', className: 'role-theme', Icon: Sparkles },
  curve_optimization: { label: 'Curve', className: 'role-curve', Icon: TrendingDown },
  mana_base_optimization: { label: 'Mana Base', className: 'role-ramp', Icon: Zap }
};

const roleTargets = {
  draw: [10, 12],
  ramp: [10, 12],
  removal: [7, 10],
  sweeper: [2, 4],
  interaction: [5, 8],
  protection: [3, 5]
};

function titleCase(value = '') {
  return value
    .replace(/_/g, ' ')
    .replace(/\w\S*/g, (word) => word.charAt(0).toUpperCase() + word.slice(1));
}

function getRoleMeta(role = '') {
  return roleMeta[role] || { label: titleCase(role || 'Role'), className: 'role-theme', Icon: Sparkles };
}

function ManaPips({ colors = [] }) {
  return <ManaPipRow colors={colors} compact className="mana-row" />;
}

const getCandidateCommanderName = (deck) => {
  if (deck?.commander) {
    return deck.commander;
  }

  return deck?.cards?.find((card) => card.type_line?.includes('Legendary Creature'))?.name || '';
};

const cleanCommanderName = (name) => (
  name
    .replace(/\*CMDR\*/gi, '')
    .replace(/\bCommander\b/gi, '')
    .replace(/\s*\([^)]*\)\s*$/g, '')
    .trim()
);

function RoleBadge({ role, tone = 'add' }) {
  const meta = getRoleMeta(role);
  const Icon = meta.Icon;

  return (
    <span className={`role-chip ${meta.className} ${tone === 'cut' ? 'role-cut' : ''}`}>
      <Icon className="w-3.5 h-3.5" />
      {meta.label}
    </span>
  );
}

function CardImages({ suggestion, compact = false }) {
  const hasBack = Boolean(suggestion.image_url_back);
  const wrapperClass = [
    'card-image-pair',
    compact ? 'compact' : '',
    hasBack ? 'double-faced' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={wrapperClass}>
      {suggestion.image_url && (
        <button
          type="button"
          className="card-face-frame"
          onClick={() => window.open(suggestion.image_url, '_blank')}
          aria-label={`Open ${suggestion.card_name} front image`}
        >
          {hasBack && <span>Front</span>}
          <img
            src={suggestion.image_url}
            alt={`${suggestion.card_name} front`}
            className="recommendation-image"
          />
        </button>
      )}
      {suggestion.image_url_back && (
        <button
          type="button"
          className="card-face-frame"
          onClick={() => window.open(suggestion.image_url_back, '_blank')}
          aria-label={`Open ${suggestion.card_name} back image`}
        >
          <span>Back</span>
          <img
            src={suggestion.image_url_back}
            alt={`${suggestion.card_name} back`}
            className="recommendation-image"
          />
        </button>
      )}
    </div>
  );
}

function RecommendationCard({ suggestion, type = 'add', index }) {
  const isAdd = type === 'add';

  return (
    <article
      data-testid={`${isAdd ? 'add' : 'cut'}-card-${index}`}
      className={`recommendation-card ${isAdd ? 'recommendation-add' : 'recommendation-cut'}`}
    >
      <CardImages suggestion={suggestion} />
      <div className="recommendation-body">
        <div className="recommendation-kicker">
          {suggestion.fit_tier && <span>{suggestion.fit_tier}</span>}
          <RoleBadge role={suggestion.role_tag} tone={isAdd ? 'add' : 'cut'} />
          <span>MV {suggestion.cmc}</span>
          {suggestion.score && <span>Score {suggestion.score}</span>}
          {suggestion.price && <span>${suggestion.price.toFixed(2)}</span>}
          {suggestion.confidence && (
            <span>{Math.round(suggestion.confidence * 100)}% {isAdd ? 'match' : 'confidence'}</span>
          )}
        </div>
        <div className="recommendation-title-row">
          <h3>{suggestion.card_name}</h3>
          {suggestion.image_url && (
            <button
              type="button"
              className="icon-link-button"
              onClick={() => window.open(suggestion.image_url, '_blank')}
              aria-label={`Open ${suggestion.card_name} image`}
            >
              <ExternalLink className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="recommendation-copy">
          <h4>{isAdd ? 'Why it fits' : 'Why it is flexible'}</h4>
          <p>{suggestion.reason}</p>
          {suggestion.evidence && (
            <p className="recommendation-evidence">Evidence: {suggestion.evidence}</p>
          )}
        </div>
      </div>
    </article>
  );
}

function SwapCard({ add, cut, index }) {
  return (
    <article className="swap-card">
      <div className="swap-column">
        <div className="swap-label add-label">
          <PlusCircle className="w-4 h-4" />
          Upgrade in
        </div>
        {add ? (
          <>
            <CardImages suggestion={add} compact />
            <h3>{add.card_name}</h3>
            <RoleBadge role={add.role_tag} />
          </>
        ) : (
          <p className="muted-copy">No add paired for this slot.</p>
        )}
      </div>
      <div className="swap-divider">
        <span>{index + 1}</span>
      </div>
      <div className="swap-column">
        <div className="swap-label cut-label">
          <MinusCircle className="w-4 h-4" />
          Consider cutting
        </div>
        {cut ? (
          <>
            <CardImages suggestion={cut} compact />
            <h3>{cut.card_name}</h3>
            <RoleBadge role={cut.role_tag} tone="cut" />
          </>
        ) : (
          <p className="muted-copy">Keep this upgrade as a standalone option.</p>
        )}
      </div>
    </article>
  );
}

function HealthMeter({ role, count }) {
  const target = roleTargets[role];
  const max = target ? target[1] : Math.max(count, 1);
  const low = target ? target[0] : 0;
  const percentage = Math.min((count / max) * 100, 100);
  const status = target ? (count < low ? 'Needs attention' : count > max ? 'High density' : 'Healthy') : 'Tracked';

  return (
    <div className="health-row">
      <div>
        <div className="health-title">{titleCase(role)}</div>
        <div className="health-target">
          {target ? `Target ${target[0]}-${target[1]}` : 'Detected role'}
        </div>
      </div>
      <div className="health-meter">
        <div className="health-bar">
          <span style={{ width: `${percentage}%` }}></span>
        </div>
        <div className="health-count">{count} - {status}</div>
      </div>
    </div>
  );
}

const pilotNoteSections = [
  { id: 'game-plan', label: 'Game Plan', prefixes: ['Game Plan -'], fallbackLimit: 3 },
  { id: 'setup', label: 'Setup', prefixes: ['Setup Priority -', 'Your land count', 'Add ', 'Your deck needs'] },
  { id: 'sequencing', label: 'Sequencing', prefixes: ['Sequencing -', 'Mulligan Guidance -'] },
  { id: 'risk', label: 'Risk Check', prefixes: ['Failure Point -', 'Table Safety -'] },
  { id: 'upgrade', label: 'Upgrade Direction', prefixes: ['Upgrade Direction -', 'Counter Strategy:', 'Token Strategy:', 'Aristocrats Strategy:', 'Enchantress Strategy:', 'Voltron Strategy:', 'Graveyard Strategy:'] },
  { id: 'deep', label: 'Deep Analysis', prefixes: ['Deep Analysis -'] },
];

function buildPilotNoteSections(tips = []) {
  const remaining = tips.map((tip, index) => ({ tip, index }));
  const sections = pilotNoteSections.map((section) => {
    const matches = [];

    for (let i = remaining.length - 1; i >= 0; i -= 1) {
      const entry = remaining[i];
      if (section.prefixes.some((prefix) => entry.tip.startsWith(prefix))) {
        matches.unshift(entry);
        remaining.splice(i, 1);
      }
    }

    if (matches.length === 0 && section.fallbackLimit && remaining.length > 0) {
      matches.push(...remaining.splice(0, section.fallbackLimit));
    }

    return {
      id: section.id,
      label: section.label,
      tips: matches.sort((a, b) => a.index - b.index).map((entry) => entry.tip),
    };
  }).filter((section) => section.tips.length > 0);

  if (remaining.length > 0) {
    sections.push({
      id: 'more',
      label: 'More Notes',
      tips: remaining.sort((a, b) => a.index - b.index).map((entry) => entry.tip),
    });
  }

  return sections;
}

function PilotNotesPager({ tips = [] }) {
  const sections = useMemo(() => buildPilotNoteSections(tips), [tips]);
  const [activeId, setActiveId] = useState(sections[0]?.id || '');

  useEffect(() => {
    setActiveId(sections[0]?.id || '');
  }, [tips, sections]);

  const activeSection = sections.find((section) => section.id === activeId) || sections[0];

  if (!activeSection) return null;

  return (
    <div className="pilot-note-pager">
      {sections.length > 1 && (
        <div className="section-pager-tabs" role="tablist" aria-label="Pilot note sections">
          {sections.map((section) => (
            <button
              key={section.id}
              type="button"
              className={`section-pager-tab ${activeSection.id === section.id ? 'active' : ''}`}
              onClick={() => setActiveId(section.id)}
            >
              <span>{section.label}</span>
              <span className="section-pager-count">{section.tips.length}</span>
            </button>
          ))}
        </div>
      )}
      <div className="pilot-note-list">
        {activeSection.tips.map((tip, idx) => (
          <div key={`${activeSection.id}-${idx}`} className="pilot-note">
            <span>{idx + 1}</span>
            <p>{tip}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AnalysisResults() {
  const { analysisId } = useParams();
  const [analysis, setAnalysis] = useState(null);
  const [deck, setDeck] = useState(null);
  const [commanderCard, setCommanderCard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [deepLoading, setDeepLoading] = useState(false);
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const deepStatus = useRotatingStatus(deepLoading, [
    'Running deeper deterministic passes',
    'Checking role coverage against commander themes',
    'Building pilot notes and risk checks',
    'Scoring upgrade and cut candidates',
  ]);

  useEffect(() => {
    fetchAnalysis();
  }, [analysisId]);

  useEffect(() => {
    const fetchCommanderCard = async () => {
      const commanderName = cleanCommanderName(getCandidateCommanderName(deck));
      if (!commanderName) {
        setCommanderCard(null);
        return;
      }

      try {
        const response = await axios.get('https://api.scryfall.com/cards/named', {
          params: { exact: commanderName },
          withCredentials: false
        });
        setCommanderCard(response.data);
      } catch (error) {
        try {
          const response = await axios.get('https://api.scryfall.com/cards/named', {
            params: { fuzzy: commanderName },
            withCredentials: false
          });
          setCommanderCard(response.data);
        } catch {
          setCommanderCard(null);
        }
      }
    };

    fetchCommanderCard();
  }, [deck]);

  const fetchAnalysis = async () => {
    try {
      const response = await axios.get(`${API}/analysis/${analysisId}`, {
        headers: getAuthHeaders()
      });
      setAnalysis(response.data);

      const deckResponse = await axios.get(`${API}/decks/${response.data.deck_id}`, {
        headers: getAuthHeaders()
      });
      setDeck(deckResponse.data);
    } catch (error) {
      toast.error('Failed to load analysis');
      navigate('/dashboard');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const response = await axios.get(`${API}/analysis/${analysisId}/export`, {
        headers: getAuthHeaders()
      });

      const blob = new Blob([response.data.markdown], { type: 'text/markdown' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = response.data.filename;
      a.click();
      window.URL.revokeObjectURL(url);

      toast.success('Export downloaded!');
    } catch (error) {
      toast.error('Export failed');
    }
  };

  const handleDeepAnalysis = async () => {
    if (!deck?.id) return;

    setDeepLoading(true);
    try {
      const response = await axios.post(
        `${API}/decks/${deck.id}/analyze/deep`,
        {},
        { headers: getAuthHeaders() }
      );
      toast.success('Deep analysis complete!');
      navigate(`/analysis/${response.data.id}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Deep analysis failed');
    } finally {
      setDeepLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="analysis-shell min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-400"></div>
      </div>
    );
  }

  const stats = analysis?.stats || {};
  const adds = analysis?.suggestions_add || [];
  const cuts = analysis?.suggestions_cut || [];
  const themes = analysis?.detected_themes || [];
  const commanderSynergies = analysis?.commander_synergies || [];
  const deckThemes = Array.from(new Set([...commanderSynergies, ...themes]));
  const colorIdentity = deck?.color_identity || [];
  const roleCounts = stats.role_counts || {};
  const swapCount = Math.max(adds.length, cuts.length);
  const maxCmcCount = Math.max(...Object.values(stats.cmc_distribution || {}), 1);
  const displayCommanderName = deck?.commander || commanderCard?.name || getCandidateCommanderName(deck);
  const commanderImageUrl = commanderCard?.image_uris?.normal
    || commanderCard?.card_faces?.[0]?.image_uris?.normal
    || null;
  const commanderTypeLine = commanderCard?.type_line || commanderCard?.card_faces?.[0]?.type_line || 'Commander';
  const analysisDepth = analysis?.analysis_depth === 'deep' ? 'Deep Analysis' : 'Fast Analysis';

  return (
    <div className="analysis-shell min-h-screen">
      <AppTopbar
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <button
              data-testid="deep-analysis-btn"
              onClick={handleDeepAnalysis}
              disabled={deepLoading}
              className="btn-secondary py-2 px-4"
            >
              {deepLoading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white inline-block mr-2"></div>
                  Deep Analysis...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 inline mr-2" />
                  Deep Analysis
                </>
              )}
            </button>
            {deepLoading && <span className="loading-status-copy">{deepStatus}</span>}
            <button
              data-testid="export-btn"
              onClick={handleExport}
              className="btn-primary py-2 px-4"
            >
              <Download className="w-4 h-4 inline mr-2" />
              Export Markdown
            </button>
          </div>
        }
      />

      <main className="container mx-auto px-6 py-10 max-w-7xl">
        <section className="command-zone-panel mb-8">
          <div className="command-zone-mark">
            <div className="deckbox-spine"></div>
            <div className="deckbox-face">
              <span>Command Zone</span>
              <strong>{(deck?.commander || 'Commander').slice(0, 2).toUpperCase()}</strong>
            </div>
          </div>
          <div className="command-zone-copy">
            <div className="eyebrow">Deck Tech</div>
            <h2 data-testid="analysis-title">{deck?.name || 'Analysis Results'}</h2>
            <p>
              {deck?.commander ? (
                <>Commander: <span>{deck.commander}</span></>
              ) : (
                <>Commander analysis unavailable</>
              )}
            </p>
            <div className="command-zone-tags">
              <span className="theme-pill">{analysisDepth}</span>
              <ManaPips colors={colorIdentity} />
              {deckThemes.slice(0, 6).map((theme, idx) => (
                <span key={`${theme}-${idx}`} className="theme-pill">{titleCase(theme)}</span>
              ))}
            </div>
          </div>
          <div data-testid="stats-overview" className="deck-stat-grid">
            <div className="deck-stat-rune">
              <strong>{stats.total_cards || 0}</strong>
              <span>Cards</span>
            </div>
            <div className="deck-stat-rune">
              <strong>{stats.total_lands || 0}</strong>
              <span>Lands</span>
            </div>
            <div className="deck-stat-rune">
              <strong>{stats.avg_cmc || 0}</strong>
              <span>Avg MV</span>
            </div>
            <div className="deck-stat-rune">
              <strong>{adds.length}</strong>
              <span>Upgrades</span>
            </div>
          </div>
        </section>

        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="analysis-tabs">
            <TabsTrigger data-testid="overview-tab" value="overview">
              <BarChart3 className="w-4 h-4 mr-2" />
              Deck Tech
            </TabsTrigger>
            <TabsTrigger data-testid="adds-tab" value="adds">
              <TrendingUp className="w-4 h-4 mr-2" />
              Upgrade Board ({adds.length})
            </TabsTrigger>
            <TabsTrigger data-testid="cuts-tab" value="cuts">
              <TrendingDown className="w-4 h-4 mr-2" />
              Possible Cuts ({cuts.length})
            </TabsTrigger>
            <TabsTrigger data-testid="swaps-tab" value="swaps">
              <Sparkles className="w-4 h-4 mr-2" />
              Swap Map
            </TabsTrigger>
          </TabsList>

          <TabsContent data-testid="adds-content" value="adds">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Upgrade Board</p>
                <h3>Cards that raise the deck's ceiling</h3>
              </div>
              <span>{adds.length} recommendations</span>
            </div>
            <div className="recommendation-list">
              {adds.map((suggestion, idx) => (
                <RecommendationCard key={`${suggestion.card_name}-${idx}`} suggestion={suggestion} type="add" index={idx} />
              ))}
            </div>
          </TabsContent>

          <TabsContent data-testid="cuts-content" value="cuts">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Possible Cuts</p>
                <h3>Flexible slots to inspect first</h3>
              </div>
              <span>{cuts.length} candidates</span>
            </div>
            <div className="recommendation-list">
              {cuts.length > 0 ? (
                cuts.map((suggestion, idx) => (
                  <RecommendationCard key={`${suggestion.card_name}-${idx}`} suggestion={suggestion} type="cut" index={idx} />
                ))
              ) : (
                <div className="empty-zone">No obvious cuts found for this analysis.</div>
              )}
            </div>
          </TabsContent>

          <TabsContent data-testid="swaps-content" value="swaps">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Swap Map</p>
                <h3>Suggested upgrade conversations</h3>
              </div>
              <span>{swapCount} slots</span>
            </div>
            <div className="swap-grid">
              {Array.from({ length: swapCount }).map((_, index) => (
                <SwapCard
                  key={`swap-${index}`}
                  add={adds[index]}
                  cut={cuts[index]}
                  index={index}
                />
              ))}
            </div>
          </TabsContent>

          <TabsContent data-testid="overview-content" value="overview">
            <div className="deck-tech-grid">
              {analysis?.playstyle_tips && analysis.playstyle_tips.length > 0 && (
                <section className="deck-tech-panel">
                  <div className="section-heading compact">
                    <div>
                      <p className="eyebrow">Pilot Notes</p>
                      <h3>Game plan signals</h3>
                    </div>
                  </div>
                  <PilotNotesPager tips={analysis.playstyle_tips} />
                </section>
              )}

              <section className="deck-tech-panel deck-identity-panel">
                <div className="section-heading compact">
                  <div>
                    <p className="eyebrow">Deck Identity</p>
                    <h3>Themes and colors</h3>
                  </div>
                </div>
                <ManaPips colors={colorIdentity} />
                <div className="theme-cloud">
                  {deckThemes.map((theme, idx) => (
                    <span key={`${theme}-${idx}`} className="theme-pill">{titleCase(theme)}</span>
                  ))}
                </div>
                <div className="commander-spotlight">
                  <div className="commander-spotlight-image">
                    {commanderImageUrl ? (
                      <img src={commanderImageUrl} alt={displayCommanderName || 'Deck commander'} />
                    ) : (
                      <div className="commander-portrait-fallback">
                        {(displayCommanderName || 'Commander').slice(0, 2).toUpperCase()}
                      </div>
                    )}
                  </div>
                  <div className="commander-spotlight-copy">
                    <p className="eyebrow">Commander</p>
                    <h4>{displayCommanderName || 'Commander unavailable'}</h4>
                    <p>{commanderTypeLine}</p>
                  </div>
                </div>
              </section>

              <section className="deck-tech-panel">
                <div className="section-heading compact">
                  <div>
                    <p className="eyebrow">Mana Curve</p>
                    <h3>Mana value spread</h3>
                    <p className="muted-copy text-sm mt-2">
                      Each row groups cards by mana value. The bar compares that band against the deck's largest band, so the longest bar shows where the curve is most crowded.
                    </p>
                  </div>
                </div>
                <div className="curve-list">
                  {['0-1', '2', '3', '4', '5', '6+'].map((bracket) => {
                    const count = stats.cmc_distribution?.[bracket] || 0;
                    const percentage = (count / maxCmcCount) * 100;
                    const totalCards = stats.total_cards || 1;
                    const deckShare = Math.round((count / totalCards) * 100);
                    return (
                      <div key={bracket} className="curve-row">
                        <span className="curve-cost-rune">MV {bracket}</span>
                        <div className="curve-track">
                          <div className="curve-meta">
                            <span>{deckShare}% of deck</span>
                            <span>{Math.round(percentage)}% of peak band</span>
                          </div>
                          <div className="curve-bar"><i style={{ width: `${percentage}%` }}></i></div>
                        </div>
                        <span className="curve-count">
                          <strong>{count}</strong>
                          <span>{count === 1 ? 'card' : 'cards'}</span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className="deck-tech-panel">
                <div className="section-heading compact">
                  <div>
                    <p className="eyebrow">Deck Health</p>
                    <h3>Role coverage</h3>
                  </div>
                </div>
                <div className="health-list">
                  {Object.entries(roleCounts).map(([role, count]) => (
                    <HealthMeter key={role} role={role} count={count} />
                  ))}
                </div>
              </section>

              {analysis?.combo_suggestions && analysis.combo_suggestions.length > 0 && (
                <section className="deck-tech-panel full-span">
                  <div className="section-heading compact">
                    <div>
                      <p className="eyebrow">Lines To Know</p>
                      <h3>Combo suggestions</h3>
                    </div>
                  </div>
                  <div className="combo-list">
                    {analysis.combo_suggestions.map((combo, idx) => (
                      <div key={idx} className="combo-row">
                        <h4>{combo.name}</h4>
                        <div>
                          {combo.cards.map((card, cidx) => (
                            <span key={cidx}>{card}</span>
                          ))}
                        </div>
                        <p>{combo.description}</p>
                        <small>Power Level: {combo.power_level}</small>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
