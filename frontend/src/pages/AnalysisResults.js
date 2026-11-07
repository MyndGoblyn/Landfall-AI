import { useMemo, useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import {
  AlertTriangle,
  Download,
  ExternalLink,
  Shield,
} from 'lucide-react';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import AppTopbar from '../components/AppTopbar';
import { CoverageNotice, SectionTabs } from '../components/CommanderAnalysisSections';
import { ManaPipRow } from '../components/ManaSymbols';
import { API } from '../lib/api';
import useRotatingStatus from '../hooks/useRotatingStatus';

const roleMeta = {
  counters: { label: 'Counters', className: 'role-counters' },
  draw: { label: 'Card Draw', className: 'role-draw' },
  ramp: { label: 'Ramp', className: 'role-ramp' },
  removal: { label: 'Removal', className: 'role-removal' },
  sweeper: { label: 'Sweeper', className: 'role-sweeper' },
  protection: { label: 'Protection', className: 'role-protection' },
  interaction: { label: 'Interaction', className: 'role-interaction' },
  synergy_optimization: { label: 'Theme Fit', className: 'role-theme' },
  curve_optimization: { label: 'Curve', className: 'role-curve' },
  mana_base_optimization: { label: 'Mana Base', className: 'role-ramp' }
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
  return roleMeta[role] || { label: titleCase(role || 'Role'), className: 'role-theme' };
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

  return (
    <span className={`role-chip ${meta.className} ${tone === 'cut' ? 'role-cut' : ''}`}>
      {meta.label}
    </span>
  );
}

function InputAssessmentNotice({ assessment }) {
  const issues = assessment?.issues || [];
  if (issues.length === 0) {
    return null;
  }

  return (
    <section className="coverage-notice input-assessment-notice" role="status">
      <AlertTriangle className="coverage-notice-icon" />
      <div className="coverage-notice-copy">
        <div className="coverage-notice-title">Deck input needs review</div>
        <p>
          {assessment.mainboard_cards} main-deck cards, {assessment.land_cards} lands,
          {' '}{assessment.unique_cards} unique card names detected.
        </p>
        <ul className="input-assessment-list">
          {issues.map((issue) => (
            <li key={issue.code}>{issue.message}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function IntentNotice({ summary, invariants }) {
  if (!summary) {
    return null;
  }
  const constraints = summary.intentional_constraints || [];
  return (
    <section className="coverage-notice intent-summary-notice" role="status">
      <Shield className="coverage-notice-icon" />
      <div className="coverage-notice-copy">
        <div className="coverage-notice-title">
          Recommendation intent: {summary.confirmed ? 'confirmed' : 'conservative default'}
        </div>
        <p>
          {titleCase(summary.optimization_mode)} mode · Power {summary.power_target}
          {' · '}{titleCase(summary.budget_mode)} budget
          {' · '}{summary.protected_card_count || 0} protected cards
        </p>
        {summary.primary_strategy && <p>Declared strategy: {summary.primary_strategy}</p>}
        {summary.desired_experience && <p>Desired experience: {summary.desired_experience}</p>}
        {summary.strategy_priorities?.length > 0 && (
          <p>Enforced priorities: {summary.strategy_priorities.map(titleCase).join(' · ')}</p>
        )}
        {summary.experience_tags?.length > 0 && (
          <p>Experience tags: {summary.experience_tags.map(titleCase).join(' · ')}</p>
        )}
        <p>
          Power outliers: {titleCase(summary.power_outlier_policy || 'auto')}
          {' · '}Generic staples: {titleCase(summary.generic_staple_tolerance || 'auto')}
        </p>
        {constraints.length > 0 && (
          <div className="theme-cloud mt-2">
            {constraints.map((constraint) => (
              <span key={constraint} className="theme-pill">{titleCase(constraint)}</span>
            ))}
          </div>
        )}
        {invariants?.typal && (
          <p>
            Typal floor: preserve {invariants.typal.on_type_cards}
            {' '}{invariants.typal.creature_type} cards across swaps.
          </p>
        )}
        {invariants?.spell_density && (
          <p>
            Spell floor: preserve {invariants.spell_density.instant_sorcery_cards}
            {' '}instants and sorceries across swaps.
          </p>
        )}
        {invariants?.aura_ladder && (
          <p>
            Aura ladder: {invariants.aura_ladder.aura_cards} Auras across mana values
            {' '}{(invariants.aura_ladder.covered_mana_values || []).join(', ') || 'none'}.
            {(invariants.aura_ladder.missing_core_mana_values || []).length > 0
              ? ` Missing core rungs: ${invariants.aura_ladder.missing_core_mana_values.join(', ')}.`
              : ' Core mana-value rungs are covered.'}
          </p>
        )}
        {invariants?.card_type_spread && (
          <p>
            {invariants.card_type_spread.permanent_only ? 'Permanent' : 'Card'}-type spread:
            {' '}{Object.entries(invariants.card_type_spread.type_counts || {})
              .map(([type, count]) => `${titleCase(type)} ${count}`)
              .join(' · ')}
          </p>
        )}
        {invariants?.sacrifice_engine && (
          <p>
            Sacrifice engine: {invariants.sacrifice_engine.component_counts.outlet} outlets
            {' · '}{invariants.sacrifice_engine.component_counts.payoff} payoffs
            {' · '}{invariants.sacrifice_engine.component_counts.fodder} fodder sources.
          </p>
        )}
        {(invariants?.protected_packages || []).map((packageInfo) => (
          <p key={packageInfo.key}>
            Protected package “{packageInfo.name}”:
            {' '}{packageInfo.present_cards.length}/{packageInfo.declared_cards.length} present.
            {packageInfo.missing_cards.length > 0
              ? ` Missing: ${packageInfo.missing_cards.join(', ')}.`
              : ' Complete.'}
          </p>
        ))}
        {(invariants?.dependencies?.tutor_packages || []).map((packageInfo) => (
          <p key={`tutor-${packageInfo.key}`}>
            Tutor targets for {packageInfo.source_cards.join(', ')}:
            {' '}{packageInfo.target_count} {packageInfo.label}
            {packageInfo.target_count === 1 ? '' : 's'} found
            {' '}({titleCase(packageInfo.status)}).
            {packageInfo.status !== 'healthy' && packageInfo.target_count > 0
              ? ` Targets: ${packageInfo.target_cards.join(', ')}.`
              : ''}
          </p>
        ))}
        {(invariants?.dependencies?.named_links || []).map((link) => (
          <p key={`link-${link.key}`}>
            Exact named link: {link.source_card} → {link.target_card}
            {' '}({titleCase(link.status)}).
          </p>
        ))}
        {invariants?.dependencies?.active && (
          <p>{invariants.dependencies.limitations}</p>
        )}
        {(summary.enforcement_notes || []).map((note) => (
          <p key={note}>{note}</p>
        ))}
        {!summary.confirmed && (
          <p>Cut confidence is reduced until the deck owner confirms budget, power, and preservation goals.</p>
        )}
      </div>
    </section>
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

function RecommendationCard({ suggestion, type = 'add', index, feedbackAction, onFeedback }) {
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
          {suggestion.suggested_quantity && (
            <span>{suggestion.suggested_quantity} slots</span>
          )}
          {suggestion.price && <span>${suggestion.price.toFixed(2)}</span>}
          {suggestion.confidence_band && (
            <span>{titleCase(suggestion.confidence_band)} evidence</span>
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
          <h4>
            {suggestion.action_only
              ? 'Why this repair comes first'
              : (isAdd ? 'Why it fits' : 'Why it is flexible')}
          </h4>
          <p>{suggestion.reason}</p>
          {suggestion.evidence && (
            <p className="recommendation-evidence">Evidence: {suggestion.evidence}</p>
          )}
          {suggestion.intent_alignment?.length > 0 && (
            <p className="recommendation-intent-ok">
              Intent: {suggestion.intent_alignment.join(' · ')}
            </p>
          )}
          {suggestion.intent_warnings?.length > 0 && (
            <p className="recommendation-intent-warning">
              Intent warning: {suggestion.intent_warnings.join(' · ')}
            </p>
          )}
          {suggestion.invariant_alignment?.length > 0 && (
            <p className="recommendation-intent-ok">
              Deck plan: {suggestion.invariant_alignment.join(' · ')}
            </p>
          )}
          {suggestion.invariant_warnings?.length > 0 && (
            <p className="recommendation-intent-warning">
              Deck-plan warning: {suggestion.invariant_warnings.join(' · ')}
            </p>
          )}
        </div>
        <div className="recommendation-feedback" aria-label={`Private feedback for ${suggestion.card_name}`}>
          <span>Was this useful?</span>
          <button
            type="button"
            className={feedbackAction === (isAdd ? 'accept_add' : 'accept_cut') ? 'active' : ''}
            aria-pressed={feedbackAction === (isAdd ? 'accept_add' : 'accept_cut')}
            onClick={() => onFeedback(isAdd ? 'accept_add' : 'accept_cut', suggestion.card_name)}
          >
            {isAdd ? 'Fits the deck' : 'Cut makes sense'}
          </button>
          <button
            type="button"
            className={feedbackAction === (isAdd ? 'reject_add' : 'keep_cut') ? 'active' : ''}
            aria-pressed={feedbackAction === (isAdd ? 'reject_add' : 'keep_cut')}
            onClick={() => onFeedback(isAdd ? 'reject_add' : 'keep_cut', suggestion.card_name)}
          >
            {isAdd ? 'Not for this deck' : 'Keep this card'}
          </button>
        </div>
      </div>
    </article>
  );
}

function SwapCard({ add, cut, index, rationale, feedbackAction, onFeedback }) {
  return (
    <article className="swap-card">
      <div className="swap-column">
        <div className="swap-label add-label">
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
      {rationale && <p className="swap-rationale">{rationale}</p>}
      {add && cut && (
        <button
          type="button"
          className={`swap-feedback-button ${feedbackAction === 'accept_swap' ? 'active' : ''}`}
          aria-pressed={feedbackAction === 'accept_swap'}
          onClick={() => onFeedback('accept_swap', add.card_name, cut.card_name)}
        >
          {feedbackAction === 'accept_swap' ? 'Swap saved to private history' : 'This swap fits my plan'}
        </button>
      )}
    </article>
  );
}

function HealthMeter({ role, count, quality }) {
  const target = roleTargets[role];
  const effectiveCount = quality?.effective_count ?? count;
  const max = target ? target[1] : Math.max(effectiveCount, 1);
  const low = target ? target[0] : 0;
  const percentage = Math.min((effectiveCount / max) * 100, 100);
  const qualityStatus = {
    gap: 'Needs attention',
    quality_gap: 'Quality gap',
    saturated: 'High density',
    healthy: 'Healthy',
  }[quality?.status];
  const status = qualityStatus || (target ? (count < low ? 'Needs attention' : count > max ? 'High density' : 'Healthy') : 'Tracked');

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
        <div className="health-count">
          {quality ? `${effectiveCount} effective (${count} raw) - ${status}` : `${count} - ${status}`}
        </div>
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
  { id: 'deep', label: 'Expanded Analysis', prefixes: ['Deep Analysis -'] },
];

const DEEP_STATUS_MESSAGES = [
  'Running deeper deterministic passes',
  'Checking role coverage against commander themes',
  'Building pilot notes and risk checks',
  'Scoring upgrade and cut candidates',
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
    if (!sections.some((section) => section.id === activeId)) {
      setActiveId(sections[0]?.id || '');
    }
  }, [activeId, sections]);

  const activeSection = sections.find((section) => section.id === activeId) || sections[0];

  if (!activeSection) return null;

  return (
    <div className="pilot-note-pager">
      <SectionTabs
        sections={sections}
        activeId={activeId}
        onChange={setActiveId}
        ariaLabel="Pilot note sections"
      />
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
  const [feedbackByKey, setFeedbackByKey] = useState({});
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const deepStatus = useRotatingStatus(deepLoading, DEEP_STATUS_MESSAGES);

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
      try {
        const feedbackResponse = await axios.get(`${API}/decks/${response.data.deck_id}/feedback`, {
          headers: getAuthHeaders()
        });
        const currentFeedback = {};
        for (const item of feedbackResponse.data) {
          if (item.source_id !== analysisId) continue;
          const group = item.action.includes('add')
            ? 'add'
            : item.action.includes('cut')
              ? 'cut'
              : 'swap';
          currentFeedback[`${group}:${String(item.card_name || '').toLowerCase()}`] = item.action;
        }
        setFeedbackByKey(currentFeedback);
      } catch (_error) {
        setFeedbackByKey({});
      }
    } catch (error) {
      toast.error('Failed to load analysis');
      navigate('/dashboard');
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (action, cardName, pairedCardName = null) => {
    if (!deck?.id) return;
    try {
      const response = await axios.post(
        `${API}/decks/${deck.id}/feedback`,
        {
          analysis_id: analysisId,
          action,
          card_name: cardName,
          paired_card_name: pairedCardName,
        },
        { headers: getAuthHeaders() }
      );
      const group = action.includes('add') ? 'add' : action.includes('cut') ? 'cut' : 'swap';
      setFeedbackByKey((current) => ({
        ...current,
        [`${group}:${cardName.toLowerCase()}`]: response.data.action,
      }));
      toast.success('Saved privately. This does not automatically tune ranking.');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not save feedback');
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
      toast.success('Expanded analysis complete!');
      navigate(`/analysis/${response.data.id}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Expanded analysis failed');
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
  const roleQuality = stats.role_quality || {};
  const rolesToDisplay = Object.keys(roleQuality).length > 0
    ? Object.keys(roleQuality)
    : Object.keys(roleCounts);
  const swapPairs = analysis?.swap_pairs?.length > 0
    ? analysis.swap_pairs
    : Array.from({ length: Math.max(adds.length, cuts.length) }).map((_, index) => ({
        add: adds[index],
        cut: cuts[index],
        reason: null,
      }));
  const swapCount = swapPairs.length;
  const maxCmcCount = Math.max(...Object.values(stats.cmc_distribution || {}), 1);
  const displayCommanderName = deck?.commander || commanderCard?.name || getCandidateCommanderName(deck);
  const commanderImageUrl = commanderCard?.image_uris?.normal
    || commanderCard?.card_faces?.[0]?.image_uris?.normal
    || null;
  const commanderTypeLine = commanderCard?.type_line || commanderCard?.card_faces?.[0]?.type_line || 'Commander';
  const analysisDepth = analysis?.analysis_depth === 'deep' ? 'Expanded analysis' : 'Standard analysis';

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
                  Expanding analysis...
                </>
              ) : (
                <>
                  Expanded Analysis
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

        <InputAssessmentNotice assessment={analysis?.input_assessment} />
        <IntentNotice
          summary={analysis?.intent_summary}
          invariants={analysis?.deck_invariants}
        />
        <CoverageNotice data={analysis} />

        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="analysis-tabs">
            <TabsTrigger data-testid="overview-tab" value="overview">
              Deck Tech
            </TabsTrigger>
            <TabsTrigger data-testid="adds-tab" value="adds">
              Upgrade Board ({adds.length})
            </TabsTrigger>
            <TabsTrigger data-testid="cuts-tab" value="cuts">
              Possible Cuts ({cuts.length})
            </TabsTrigger>
            <TabsTrigger data-testid="swaps-tab" value="swaps">
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
                <RecommendationCard
                  key={`${suggestion.card_name}-${idx}`}
                  suggestion={suggestion}
                  type="add"
                  index={idx}
                  feedbackAction={feedbackByKey[`add:${suggestion.card_name.toLowerCase()}`]}
                  onFeedback={handleFeedback}
                />
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
                  <RecommendationCard
                    key={`${suggestion.card_name}-${idx}`}
                    suggestion={suggestion}
                    type="cut"
                    index={idx}
                    feedbackAction={feedbackByKey[`cut:${suggestion.card_name.toLowerCase()}`]}
                    onFeedback={handleFeedback}
                  />
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
              {swapPairs.map((pair, index) => (
                <SwapCard
                  key={`swap-${index}`}
                  add={pair.add}
                  cut={pair.cut}
                  index={index}
                  rationale={pair.reason}
                  feedbackAction={pair.add ? feedbackByKey[`swap:${pair.add.card_name.toLowerCase()}`] : null}
                  onFeedback={handleFeedback}
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
                  {rolesToDisplay.map((role) => (
                    <HealthMeter
                      key={role}
                      role={role}
                      count={roleCounts[role] || 0}
                      quality={roleQuality[role]}
                    />
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
