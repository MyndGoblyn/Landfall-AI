import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  GitCompareArrows,
  Layers3,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import { toast } from 'sonner';
import AppTopbar from '../components/AppTopbar';
import { ManaPip } from '../components/ManaSymbols';
import { useAuth } from '../context/AuthContext';
import { API } from '../lib/api';
import useRotatingStatus from '../hooks/useRotatingStatus';

const BUILD_MESSAGES = [
  'Resolving fixed cards and protected packages',
  'Measuring commander lanes and role coverage',
  'Applying legality, budget, and collection gates',
  'Selecting the complementary evidence portfolio',
  'Allocating the basic-land baseline',
  'Validating the scaffold and recording unresolved slots',
];

const labelize = (value) => String(value || '')
  .replace(/_/g, ' ')
  .replace(/\b\w/g, (letter) => letter.toUpperCase());

const errorMessage = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail[0]?.msg || fallback;
  return fallback;
};

function DraftCard({ card }) {
  return (
    <article className="scaffold-card">
      <div className="scaffold-card-art">
        {card.image_url ? (
          <img src={card.image_url} alt="" loading="lazy" />
        ) : (
          <span aria-hidden="true">{card.qty || 1}</span>
        )}
      </div>
      <div className="scaffold-card-copy">
        <div className="scaffold-card-heading">
          <div>
            <span>{labelize(card.source)}</span>
            <h3>{card.qty > 1 ? `${card.qty}× ` : ''}{card.name}</h3>
          </div>
          {card.role && <small>{labelize(card.role)}</small>}
        </div>
        <p>{card.reason}</p>
        {card.selection_reason && <blockquote>{card.selection_reason}</blockquote>}
        <div className="scaffold-card-meta">
          {card.confidence != null && <span>Evidence {Math.round(card.confidence * 100)}%</span>}
          {card.price_usd != null && <span>${Number(card.price_usd).toFixed(2)} each</span>}
          {(card.evidence || []).slice(0, 3).map((item) => (
            <span key={item}>{labelize(item)}</span>
          ))}
        </div>
      </div>
    </article>
  );
}

function ValidationPanel({ validation }) {
  const errors = validation?.errors || [];
  const warnings = validation?.warnings || [];
  const checks = Object.entries(validation?.checks || {});
  return (
    <section className={`scaffold-validation ${errors.length ? 'has-errors' : ''}`}>
      <div className="scaffold-section-heading">
        <div>
          <p className="page-eyebrow">Hard-gate review</p>
          <h2>{errors.length ? 'The scaffold needs attention.' : 'Every hard gate passed.'}</h2>
        </div>
        {errors.length ? <AlertTriangle aria-hidden="true" /> : <ShieldCheck aria-hidden="true" />}
      </div>
      <div className="scaffold-check-grid">
        {checks.map(([name, passed]) => (
          <span key={name} className={passed ? 'passed' : 'failed'}>
            {passed ? <Check aria-hidden="true" /> : <AlertTriangle aria-hidden="true" />}
            {labelize(name)}
          </span>
        ))}
      </div>
      {(errors.length > 0 || warnings.length > 0) && (
        <div className="scaffold-issues">
          {errors.map((issue, index) => (
            <p className="error" key={`${issue.code}-${index}`}><strong>Blocked:</strong> {issue.message}</p>
          ))}
          {warnings.map((issue, index) => (
            <p key={`${issue.code}-${index}`}><strong>Review:</strong> {issue.message}</p>
          ))}
        </div>
      )}
    </section>
  );
}

export default function BuildWorkspace() {
  const { deckId } = useParams();
  const [deck, setDeck] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [applying, setApplying] = useState(false);
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const buildStatus = useRotatingStatus(generating, BUILD_MESSAGES);

  const loadWorkspace = async () => {
    try {
      const [deckResponse, draftsResponse] = await Promise.all([
        axios.get(`${API}/decks/${deckId}`, { headers: getAuthHeaders() }),
        axios.get(`${API}/decks/${deckId}/build-drafts`, { headers: getAuthHeaders() }),
      ]);
      setDeck(deckResponse.data);
      setDrafts(draftsResponse.data);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not load this build workspace'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkspace();
  }, [deckId]);

  const latest = drafts[0] || null;
  const result = latest?.result || null;
  const selectedGroups = useMemo(() => {
    const groups = { protected: [], planner_v3: [], mana_baseline: [] };
    for (const card of result?.selected_cards || []) {
      const key = Object.prototype.hasOwnProperty.call(groups, card.source)
        ? card.source
        : 'planner_v3';
      groups[key].push(card);
    }
    return groups;
  }, [result]);

  const generate = async () => {
    setGenerating(true);
    try {
      const response = await axios.post(
        `${API}/decks/${deckId}/build-drafts`,
        {},
        { headers: getAuthHeaders() }
      );
      setDrafts((current) => [response.data, ...current]);
      toast.success('Deterministic scaffold generated. Review every unresolved slot before applying.');
    } catch (error) {
      toast.error(errorMessage(error, 'The scaffold could not be generated'));
    } finally {
      setGenerating(false);
    }
  };

  const applyDraft = async () => {
    if (!latest || !result?.validation?.passed) return;
    if (!window.confirm('Apply this reviewed partial scaffold to the deck? Existing cards stay fixed, and this reviewed revision becomes the current list.')) {
      return;
    }
    setApplying(true);
    try {
      await axios.post(
        `${API}/decks/${deckId}/build-drafts/${latest.id}/apply`,
        { confirmed: true },
        { headers: getAuthHeaders() }
      );
      toast.success('Scaffold applied. Open slots remain visible in the deck assessment.');
      navigate(`/deck/${deckId}/view`);
    } catch (error) {
      toast.error(errorMessage(error, 'The scaffold could not be applied'));
    } finally {
      setApplying(false);
    }
  };

  if (loading) {
    return (
      <div className="app-shell">
        <AppTopbar />
        <main className="build-loading" role="status">Loading the deterministic build workspace...</main>
      </div>
    );
  }

  if (!deck) {
    return null;
  }

  const intent = deck.build_intent;
  const canGenerate = intent?.confirmed && intent?.build_mode === 'guided_scaffold';
  const scope = result?.scope || {};
  const validation = result?.validation;

  return (
    <div className="app-shell scaffold-page" data-testid="build-workspace">
      <AppTopbar />
      {generating && (
        <div className="analysis-progress-banner" role="status" aria-live="polite">
          <strong>Phase 4 scaffold</strong>
          <span>{buildStatus}</span>
        </div>
      )}
      <main className="container mx-auto px-6 py-10 max-w-7xl">
        <section className="scaffold-hero">
          <div>
            <p className="page-eyebrow">Deterministic constructor · Phase 4</p>
            <h1>Build with evidence, not filler.</h1>
            <p>
              Fixed cards stay fixed. Planner V3 supplies only candidates that survive legality,
              intent, budget, collection, and portfolio gates; unsupported slots remain open.
            </p>
            <div className="scaffold-commander-line">
              <strong>{deck.name}</strong>
              {deck.commander && <span>{deck.commander}</span>}
              {(deck.color_identity || []).map((color) => <ManaPip key={color} color={color} />)}
            </div>
          </div>
          <div className="scaffold-hero-actions">
            <button className="btn-secondary" onClick={() => navigate(`/build?deck=${encodeURIComponent(deckId)}`)}>
              Edit intent
            </button>
            <button
              className="btn-primary"
              onClick={generate}
              disabled={!canGenerate || generating}
              data-testid="generate-scaffold-button"
            >
              <RefreshCw aria-hidden="true" />
              {generating ? 'Building scaffold...' : latest ? 'Generate new revision' : 'Generate scaffold'}
            </button>
          </div>
        </section>

        {!canGenerate && (
          <section className="scaffold-boundary-note">
            <AlertTriangle aria-hidden="true" />
            <div>
              <strong>This deck is not configured for a guided scaffold.</strong>
              <p>Open the intent workspace, choose Guided scaffold, and confirm the visible engine mappings first.</p>
            </div>
          </section>
        )}

        {!latest && canGenerate && (
          <section className="scaffold-empty">
            <Layers3 aria-hidden="true" />
            <p className="page-eyebrow">No draft yet</p>
            <h2>The first revision will preserve the current list.</h2>
            <p>LandFall will add only a bounded portfolio. It will not replace fixed cards or invent confidence to finish the deck.</p>
          </section>
        )}

        {latest && result && (
          <>
            <section className="scaffold-summary-grid">
              <article><span>Revision</span><strong>{latest.revision}</strong><small>{labelize(result.status)}</small></article>
              <article><span>Fixed</span><strong>{scope.fixed_slots || 0}</strong><small>user-owned slots</small></article>
              <article><span>Selected</span><strong>{scope.selected_slots || 0}</strong><small>inside this pass</small></article>
              <article><span>Still open</span><strong>{scope.remaining_mainboard_slots || 0}</strong><small>never silently filled</small></article>
              <article><span>Verified subtotal</span><strong>${Number(result.budget?.verified_subtotal_usd || 0).toFixed(2)}</strong><small>{labelize(result.budget?.mode)}</small></article>
            </section>

            <ValidationPanel validation={validation} />

            <section className="scaffold-ledger-grid">
              <div className="scaffold-slot-plan">
                <div className="scaffold-section-heading">
                  <div><p className="page-eyebrow">Slot allocator</p><h2>What this pass tried to cover</h2></div>
                  <Layers3 aria-hidden="true" />
                </div>
                {(result.role_allocation || []).length ? (
                  <div className="slot-plan-list">
                    {result.role_allocation.map((lane) => (
                      <article key={lane.lane}>
                        <div><strong>{labelize(lane.lane)}</strong><span>{labelize(lane.kind)}</span></div>
                        <b>{lane.slots}</b>
                        <p>{(lane.evidence || [])[0] || 'Supported by the normalized strategy profile.'}</p>
                      </article>
                    ))}
                  </div>
                ) : <p className="page-copy">No nonland lane allocation was required for this shape.</p>}
              </div>

              <div className="scaffold-unresolved">
                <div className="scaffold-section-heading">
                  <div><p className="page-eyebrow">Abstention ledger</p><h2>Open work stays visible</h2></div>
                  <ShieldCheck aria-hidden="true" />
                </div>
                {(result.unresolved_slots || []).length ? result.unresolved_slots.map((slot, index) => (
                  <article key={`${slot.lane}-${index}`}>
                    <b>{slot.count}</b>
                    <div><strong>{labelize(slot.lane)}</strong><p>{slot.reason}</p></div>
                  </article>
                )) : <p className="page-copy">Every slot inside this bounded pass was filled by qualifying evidence.</p>}
                {scope.deferred_slots > 0 && (
                  <article>
                    <b>{scope.deferred_slots}</b>
                    <div><strong>Deferred beyond this pass</strong><p>The production scaffold is capped at {scope.request_slot_limit} new slots until complete-draft validation is promoted.</p></div>
                  </article>
                )}
              </div>
            </section>

            {[
              ['protected', 'Protected intent', 'Cards the confirmed contract requires.'],
              ['planner_v3', 'Evidence portfolio', 'Complementary additions selected by the current deterministic planner.'],
              ['mana_baseline', 'Mana baseline', 'Conservative basics allocated from measured color demand.'],
            ].map(([key, title, copy]) => selectedGroups[key].length > 0 && (
              <section className="scaffold-card-section" key={key}>
                <div className="scaffold-section-heading">
                  <div><p className="page-eyebrow">{title}</p><h2>{copy}</h2></div>
                  <span>{selectedGroups[key].reduce((sum, card) => sum + (card.qty || 1), 0)} slots</span>
                </div>
                <div className="scaffold-card-list">
                  {selectedGroups[key].map((card) => <DraftCard key={`${key}-${card.name}`} card={card} />)}
                </div>
              </section>
            ))}

            <section className="scaffold-history">
              <div className="scaffold-section-heading">
                <div><p className="page-eyebrow">Revision history</p><h2>Why the draft changed</h2></div>
                <GitCompareArrows aria-hidden="true" />
              </div>
              <div className="scaffold-history-list">
                {drafts.map((draft) => (
                  <article key={draft.id}>
                    <div><strong>Revision {draft.revision}</strong><span>{labelize(draft.status)}</span></div>
                    <p>
                      {(draft.change_summary?.added || []).length} added ·{' '}
                      {(draft.change_summary?.removed || []).length} removed ·{' '}
                      {(draft.change_summary?.unchanged || []).length} unchanged
                    </p>
                    {draft.applied_at && <small>Applied to deck</small>}
                  </article>
                ))}
              </div>
            </section>

            <section className="scaffold-final-actions">
              <button className="btn-secondary" onClick={() => navigate('/dashboard')}>
                <ArrowLeft aria-hidden="true" /> Back to decks
              </button>
              <div>
                <p>Complete-draft generation remains disabled until Phase 5 portfolio validation.</p>
                <button
                  className="btn-primary"
                  onClick={applyDraft}
                  disabled={!validation?.passed || applying || latest.applied_at}
                  data-testid="apply-scaffold-button"
                >
                  <Check aria-hidden="true" />
                  {latest.applied_at ? 'Revision applied' : applying ? 'Applying...' : 'Apply reviewed scaffold'}
                </button>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
