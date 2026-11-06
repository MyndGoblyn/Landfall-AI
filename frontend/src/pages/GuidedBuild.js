import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Layers3,
  Library,
  ShieldCheck,
  WalletCards,
} from 'lucide-react';
import { toast } from 'sonner';
import AppTopbar from '../components/AppTopbar';
import { useAuth } from '../context/AuthContext';
import { API } from '../lib/api';

const POWER_BANDS = {
  1: [1, 2],
  2: [3, 4],
  3: [5, 6],
  4: [7, 8],
  5: [9, 10],
};

const DEFAULT_INTENT = {
  schema_version: 1,
  confirmed: false,
  format: 'commander',
  deck_name: '',
  starting_point: 'blank',
  existing_deck_id: null,
  commander_name: '',
  commander_oracle_id: '',
  partner_name: '',
  partner_oracle_id: '',
  starting_card_name: '',
  concept: '',
  build_mode: 'manual',
  playstyle: 'balanced',
  custom_strategy_priorities: [],
  target_bracket: 3,
  power_level_min: 5,
  power_level_max: 6,
  budget_mode: 'unknown',
  budget_limit_usd: '',
  max_card_price_usd: '',
  build_shape: 'full_deck',
  collection_mode: 'all_cards',
  owned_card_names: [],
  protected_cards: [],
  protected_packages: [],
  excluded_cards: [],
  intentional_constraints: [],
  notes: '',
};

const STEPS = ['Foundation', 'Direction', 'Boundaries', 'Preserve', 'Review'];

const PLAYSTYLES = [
  ['balanced', 'Balanced', 'Keep engine, interaction, pressure, and resilience level.'],
  ['aggressive', 'Aggressive', 'Prioritize pressure, combat conversion, and protection.'],
  ['value', 'Value', 'Favor repeatable engines, card flow, and recovery.'],
  ['control', 'Control', 'Raise interaction and resilience before closing speed.'],
  ['combo', 'Combo', 'Support compact win paths, setup, and protection.'],
  ['custom', 'Custom', 'Choose the exact strategy lanes yourself.'],
];

const STRATEGY_PRIORITIES = [
  ['typal', 'Typal'],
  ['go_wide', 'Go wide'],
  ['spell_chain', 'Spell chain'],
  ['donation', 'Donation'],
  ['politics', 'Politics'],
  ['graveyard_recursion', 'Graveyard recursion'],
  ['permanent_engine', 'Permanent engine'],
  ['blink', 'Blink'],
  ['voltron', 'Voltron'],
  ['compact_wins', 'Compact wins'],
  ['stack_interaction', 'Stack interaction'],
  ['mana_fixing', 'Mana fixing'],
  ['combat_combo', 'Combat combo'],
  ['card_velocity', 'Card velocity'],
  ['protection', 'Protection'],
  ['competitive', 'Competitive'],
];

const CONSTRAINTS = [
  ['typal_core', 'Protect the typal core'],
  ['spell_density', 'Protect spell density'],
  ['intentional_jank', 'Intentional jank'],
  ['flavor_first', 'Flavor first'],
  ['low_land_count', 'Low land count is intentional'],
  ['no_fast_mana', 'No fast mana'],
  ['no_tutors', 'No nonland tutors'],
  ['no_infinite_combos', 'No infinite combos'],
];

const splitCardNames = (value) => value
  .split(/[\n,]/)
  .map((item) => item.trim())
  .filter(Boolean);

const packageText = (packages) => (packages || [])
  .map((item) => `${item.name}: ${(item.cards || []).join(', ')}`)
  .join('\n');

const parsePackages = (value) => value
  .split('\n')
  .map((line) => line.trim())
  .filter(Boolean)
  .map((line) => {
    const [name, ...cardParts] = line.split(':');
    return {
      name: name.trim(),
      cards: splitCardNames(cardParts.join(':')),
    };
  })
  .filter((item) => item.name);

const labelize = (value) => String(value || '')
  .replace(/_/g, ' ')
  .replace(/\b\w/g, (letter) => letter.toUpperCase());

function ChoiceCard({ active, disabled = false, title, copy, onClick }) {
  return (
    <button
      type="button"
      className={`build-choice-card ${active ? 'active' : ''}`}
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
    >
      <span>{title}</span>
      <small>{copy}</small>
      {active && <Check aria-hidden="true" />}
    </button>
  );
}

export default function GuidedBuild() {
  const [searchParams] = useSearchParams();
  const existingDeckId = searchParams.get('deck');
  const initialCommander = searchParams.get('commander') || '';
  const initialOracleId = searchParams.get('oracle_id') || '';
  const [intent, setIntent] = useState(() => ({
    ...DEFAULT_INTENT,
    deck_name: initialCommander ? `${initialCommander} deck` : '',
    starting_point: existingDeckId ? 'existing_deck' : initialCommander ? 'commander' : 'blank',
    existing_deck_id: existingDeckId,
    commander_name: initialCommander,
    commander_oracle_id: initialOracleId,
  }));
  const [step, setStep] = useState(0);
  const [loadingExisting, setLoadingExisting] = useState(Boolean(existingDeckId));
  const [normalizing, setNormalizing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [normalized, setNormalized] = useState(null);
  const [reviewConfirmed, setReviewConfirmed] = useState(false);
  const [protectedText, setProtectedText] = useState('');
  const [excludedText, setExcludedText] = useState('');
  const [ownedText, setOwnedText] = useState('');
  const [packagesText, setPackagesText] = useState('');
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!existingDeckId) return;
    const loadExisting = async () => {
      try {
        const response = await axios.get(`${API}/decks/${existingDeckId}/build-intent`, {
          headers: getAuthHeaders(),
        });
        const loaded = response.data.intent;
        setIntent(loaded);
        setProtectedText((loaded.protected_cards || []).join('\n'));
        setExcludedText((loaded.excluded_cards || []).join('\n'));
        setOwnedText((loaded.owned_card_names || []).join('\n'));
        setPackagesText(packageText(loaded.protected_packages));
        if (response.data.source === 'migrated_deck_intent_v1') {
          toast.info('Existing deck preferences were safely migrated into the new build plan.');
        }
      } catch (error) {
        toast.error(error.response?.data?.detail || 'Could not load this deck plan');
      } finally {
        setLoadingExisting(false);
      }
    };
    loadExisting();
  }, [existingDeckId]);

  const updateIntent = (field, value) => {
    setIntent((current) => ({ ...current, [field]: value }));
    setNormalized(null);
    setReviewConfirmed(false);
  };

  const updateIntentFields = (fields) => {
    setIntent((current) => ({ ...current, ...fields }));
    setNormalized(null);
    setReviewConfirmed(false);
  };

  const updateTextConstraint = (setter, value) => {
    setter(value);
    setNormalized(null);
    setReviewConfirmed(false);
  };

  const toggleListValue = (field, value) => {
    const current = intent[field] || [];
    updateIntent(
      field,
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value]
    );
  };

  const payload = useMemo(() => ({
    ...intent,
    confirmed: true,
    existing_deck_id: intent.existing_deck_id || null,
    commander_name: intent.commander_name || null,
    commander_oracle_id: intent.commander_oracle_id || null,
    partner_name: intent.partner_name || null,
    partner_oracle_id: intent.partner_oracle_id || null,
    starting_card_name: intent.starting_card_name || null,
    concept: intent.concept || null,
    budget_limit_usd: intent.budget_limit_usd === '' ? null : Number(intent.budget_limit_usd),
    max_card_price_usd: intent.max_card_price_usd === '' ? null : Number(intent.max_card_price_usd),
    owned_card_names: splitCardNames(ownedText),
    protected_cards: splitCardNames(protectedText),
    protected_packages: parsePackages(packagesText),
    excluded_cards: splitCardNames(excludedText),
    notes: intent.notes || null,
  }), [intent, ownedText, protectedText, packagesText, excludedText]);

  const validateStep = () => {
    if (step === 0) {
      if (!intent.deck_name.trim()) return 'Give this deck plan a name.';
      if (intent.starting_point === 'commander' && !intent.commander_name.trim()) {
        return 'Choose a commander for this starting point.';
      }
      if (intent.starting_point === 'card' && !intent.starting_card_name.trim()) {
        return 'Name the card this build should start from.';
      }
      if (intent.starting_point === 'concept' && !intent.concept.trim()) {
        return 'Describe the concept this build should preserve.';
      }
    }
    if (step === 1 && intent.playstyle === 'custom' && !intent.custom_strategy_priorities.length) {
      return 'Choose at least one custom strategy priority.';
    }
    if (step === 2) {
      if (intent.budget_mode === 'strict' && intent.max_card_price_usd === '') {
        return 'A strict budget needs a per-card ceiling.';
      }
      if (intent.budget_mode === 'target'
        && intent.max_card_price_usd === ''
        && intent.budget_limit_usd === '') {
        return 'Add a total or per-card target.';
      }
      if (intent.collection_mode === 'owned_only' && !splitCardNames(ownedText).length) {
        return 'Owned-only mode needs at least one owned card.';
      }
    }
    return null;
  };

  const nextStep = async () => {
    const issue = validateStep();
    if (issue) {
      toast.error(issue);
      return;
    }
    if (step < 3) {
      setStep((current) => current + 1);
      return;
    }
    setNormalizing(true);
    try {
      const response = await axios.post(`${API}/build-intents/normalize`, payload, {
        headers: getAuthHeaders(),
      });
      setNormalized(response.data);
      setStep(4);
    } catch (error) {
      toast.error(error.response?.data?.detail?.[0]?.msg || error.response?.data?.detail || 'Build choices conflict');
    } finally {
      setNormalizing(false);
    }
  };

  const savePlan = async () => {
    if (!reviewConfirmed || !normalized) return;
    setSaving(true);
    try {
      if (existingDeckId) {
        await axios.put(
          `${API}/decks/${existingDeckId}/build-intent`,
          normalized.intent,
          { headers: getAuthHeaders() }
        );
        toast.success('Build plan saved to your deck.');
        navigate(
          normalized.intent.build_mode === 'guided_scaffold'
            ? `/deck/${existingDeckId}/build`
            : '/dashboard'
        );
        return;
      }
      const commanders = [
        normalized.intent.commander_name,
        normalized.intent.partner_name,
      ].filter(Boolean);
      const response = await axios.post(
        `${API}/decks`,
        {
          name: normalized.intent.deck_name,
          commander: commanders[0] || null,
          commanders,
          format: normalized.intent.format,
          build_intent: normalized.intent,
        },
        { headers: getAuthHeaders() }
      );
      const scaffoldEnabled = normalized.intent.build_mode === 'guided_scaffold';
      toast.success(scaffoldEnabled
        ? 'Build plan saved. Review the deterministic scaffold before applying it.'
        : 'Build plan saved. Add cards when you are ready.');
      navigate(scaffoldEnabled
        ? `/deck/${response.data.id}/build`
        : `/deck/${response.data.id}/import`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not save this build plan');
    } finally {
      setSaving(false);
    }
  };

  if (loadingExisting) {
    return (
      <div className="app-shell">
        <AppTopbar />
        <main className="build-loading" role="status">Loading the saved deck intent...</main>
      </div>
    );
  }

  const mapping = normalized?.mapping;
  const deckProfile = normalized?.deck_intent_profile;

  return (
    <div className="app-shell">
      <AppTopbar />
      <main className="container mx-auto px-6 py-10 max-w-7xl guided-build-page" data-testid="guided-build">
        <section className="guided-build-hero">
          <div>
            <p className="page-eyebrow">Guided Build</p>
            <h1>Define the deck before choosing the cards.</h1>
            <p>
              Every choice becomes a visible engine constraint. Manual plans open a deck; Guided scaffold plans open a bounded, reviewable construction workspace.
            </p>
          </div>
          <div className="guided-build-contract">
            <ShieldCheck aria-hidden="true" />
            <span>Versioned intent contract</span>
            <strong>Schema v1</strong>
          </div>
        </section>

        <nav className="build-step-nav" aria-label="Build plan steps">
          {STEPS.map((label, index) => (
            <button
              type="button"
              key={label}
              className={index === step ? 'active' : index < step ? 'complete' : ''}
              onClick={() => index < step && setStep(index)}
              disabled={index > step}
            >
              <span>{index < step ? <Check aria-hidden="true" /> : null}</span>
              {label}
            </button>
          ))}
        </nav>

        <section className="build-workspace">
          <div className="build-step-panel">
            {step === 0 && (
              <div data-testid="build-step-foundation">
                <p className="page-eyebrow">Foundation</p>
                <h2>What are we beginning with?</h2>
                <p className="build-step-copy">Name the plan and identify the facts already fixed.</p>

                <div className="build-field-grid">
                  <label>
                    <span>Deck name</span>
                    <input
                      className="input"
                      value={intent.deck_name}
                      maxLength={120}
                      onChange={(event) => updateIntent('deck_name', event.target.value)}
                      data-testid="build-name-input"
                    />
                  </label>
                  <label>
                    <span>Format</span>
                    <input className="input" value="Commander · 100 cards · singleton" disabled />
                    <small>Additional formats stay unavailable until their validation suites exist.</small>
                  </label>
                </div>

                <div className="build-choice-grid build-choice-grid-wide">
                  {[
                    ['blank', 'Blank plan', 'Start with no fixed card.'],
                    ['commander', 'Commander', 'Begin from a commander or partner pair.'],
                    ['card', 'Card', 'Build outward from a noncommander card.'],
                    ['concept', 'Concept', 'Protect a theme, experience, or restriction.'],
                    ['imported_list', 'Imported list', 'Plan around a list you will import next.'],
                    ['existing_deck', 'Existing deck', 'Re-plan a deck already in your workspace.'],
                  ].map(([id, title, copy]) => (
                    <ChoiceCard
                      key={id}
                      title={title}
                      copy={copy}
                      active={intent.starting_point === id}
                      disabled={id === 'existing_deck' && !existingDeckId}
                      onClick={() => updateIntent('starting_point', id)}
                    />
                  ))}
                </div>

                {(intent.starting_point === 'commander' || intent.commander_name) && (
                  <div className="build-field-grid mt-6">
                    <label>
                      <span>Commander</span>
                      <input
                        className="input"
                        value={intent.commander_name || ''}
                        placeholder="Meren of Clan Nel Toth"
                        onChange={(event) => updateIntent('commander_name', event.target.value)}
                        data-testid="build-commander-input"
                      />
                    </label>
                    <label>
                      <span>Partner or background <small>optional</small></span>
                      <input
                        className="input"
                        value={intent.partner_name || ''}
                        placeholder="Second commander or background"
                        onChange={(event) => updateIntent('partner_name', event.target.value)}
                      />
                    </label>
                  </div>
                )}
                {intent.starting_point === 'card' && (
                  <label className="build-full-field mt-6">
                    <span>Starting card</span>
                    <input
                      className="input"
                      value={intent.starting_card_name || ''}
                      onChange={(event) => updateIntent('starting_card_name', event.target.value)}
                    />
                  </label>
                )}
                {intent.starting_point === 'concept' && (
                  <label className="build-full-field mt-6">
                    <span>Concept to preserve</span>
                    <textarea
                      className="input"
                      rows={3}
                      value={intent.concept || ''}
                      placeholder="Political gifts without becoming generic group hug"
                      onChange={(event) => updateIntent('concept', event.target.value)}
                    />
                  </label>
                )}
              </div>
            )}

            {step === 1 && (
              <div data-testid="build-step-direction">
                <p className="page-eyebrow">Direction</p>
                <h2>How should the deck play?</h2>
                <p className="build-step-copy">Playstyle becomes explicit strategy-lane weights; the power band becomes visible card-policy boundaries.</p>

                <div className="build-choice-grid">
                  {PLAYSTYLES.map(([id, title, copy]) => (
                    <ChoiceCard
                      key={id}
                      title={title}
                      copy={copy}
                      active={intent.playstyle === id}
                      onClick={() => updateIntent('playstyle', id)}
                    />
                  ))}
                </div>

                {intent.playstyle === 'custom' && (
                  <div className="build-check-grid mt-6">
                    {STRATEGY_PRIORITIES.map(([id, label]) => (
                      <label key={id}>
                        <input
                          type="checkbox"
                          checked={intent.custom_strategy_priorities.includes(id)}
                          onChange={() => toggleListValue('custom_strategy_priorities', id)}
                        />
                        <span>{label}</span>
                      </label>
                    ))}
                  </div>
                )}

                <div className="build-section-divider">
                  <span>LandFall power band</span>
                  <small>An internal, inspectable scale—not an unsupported claim about a table.</small>
                </div>
                <div className="power-band-grid">
                  {[
                    [1, 'Expressive', 'Low pressure; no fast mana, tutors, or compact loops.'],
                    [2, 'Casual', 'Measured upgrades with limited tutoring and no compact loops.'],
                    [3, 'Focused', 'Efficient plans with disclosed combo and power exceptions.'],
                    [4, 'High power', 'Fast mana, tutors, compact wins, and high interaction allowed.'],
                    [5, 'Competitive', 'Tournament-speed efficiency and stack interaction expected.'],
                  ].map(([id, title, copy]) => (
                    <ChoiceCard
                      key={id}
                      title={title}
                      copy={copy}
                      active={intent.target_bracket === id}
                      onClick={() => {
                        const [minimum, maximum] = POWER_BANDS[id];
                        updateIntentFields({
                          target_bracket: id,
                          power_level_min: minimum,
                          power_level_max: maximum,
                        });
                      }}
                    />
                  ))}
                </div>

                <div className="build-field-grid mt-6">
                  <label>
                    <span>Power floor</span>
                    <select
                      className="input"
                      value={intent.power_level_min}
                      onChange={(event) => updateIntent('power_level_min', Number(event.target.value))}
                    >
                      {POWER_BANDS[intent.target_bracket].map((value) => <option key={value}>{value}</option>)}
                    </select>
                  </label>
                  <label>
                    <span>Power ceiling</span>
                    <select
                      className="input"
                      value={intent.power_level_max}
                      onChange={(event) => updateIntent('power_level_max', Number(event.target.value))}
                    >
                      {POWER_BANDS[intent.target_bracket].map((value) => <option key={value}>{value}</option>)}
                    </select>
                  </label>
                </div>

                <div className="build-section-divider"><span>Build mode</span></div>
                <div className="build-choice-grid">
                  <ChoiceCard
                    title="Manual deck"
                    copy="Save the plan, then import or add cards yourself."
                    active={intent.build_mode === 'manual'}
                    onClick={() => updateIntent('build_mode', 'manual')}
                  />
                  <ChoiceCard
                    title="Guided scaffold"
                    copy="Generate a bounded evidence portfolio while leaving unsupported slots open."
                    active={intent.build_mode === 'guided_scaffold'}
                    onClick={() => updateIntent('build_mode', 'guided_scaffold')}
                  />
                  <ChoiceCard
                    title="Complete draft · Phase 5"
                    copy="Disabled until the full portfolio and mana-base validation suite is promoted."
                    disabled
                    active={false}
                  />
                </div>
              </div>
            )}

            {step === 2 && (
              <div data-testid="build-step-boundaries">
                <p className="page-eyebrow">Boundaries</p>
                <h2>What limits the candidate pool?</h2>
                <p className="build-step-copy">Budgets, build scope, and owned cards become hard gates or visible preferences.</p>

                <div className="build-field-grid">
                  <label>
                    <span>Budget behavior</span>
                    <select
                      className="input"
                      value={intent.budget_mode}
                      onChange={(event) => {
                        const mode = event.target.value;
                        updateIntentFields({
                          budget_mode: mode,
                          budget_limit_usd: mode === 'unrestricted' ? '' : intent.budget_limit_usd,
                          max_card_price_usd: mode === 'unrestricted' ? '' : intent.max_card_price_usd,
                        });
                      }}
                    >
                      <option value="unknown">Not decided</option>
                      <option value="strict">Strict gate</option>
                      <option value="target">Target with disclosed exceptions</option>
                      <option value="flexible">Flexible preference</option>
                      <option value="unrestricted">Unrestricted</option>
                    </select>
                  </label>
                  <label>
                    <span>Total deck budget · USD</span>
                    <input
                      className="input"
                      type="number"
                      min="0"
                      disabled={intent.budget_mode === 'unrestricted'}
                      value={intent.budget_limit_usd}
                      onChange={(event) => updateIntent('budget_limit_usd', event.target.value)}
                      placeholder="150"
                    />
                  </label>
                  <label>
                    <span>Per-card ceiling · USD</span>
                    <input
                      className="input"
                      type="number"
                      min="0"
                      disabled={intent.budget_mode === 'unrestricted'}
                      value={intent.max_card_price_usd}
                      onChange={(event) => updateIntent('max_card_price_usd', event.target.value)}
                      placeholder="10"
                    />
                  </label>
                </div>

                <div className="build-section-divider"><span>Requested shape</span></div>
                <div className="build-choice-grid">
                  {[
                    ['full_deck', 'Full deck', 'Plan all noncommander slots.'],
                    ['core_shell', 'Core shell', 'Bound the engine and support core to 40 slots.'],
                    ['mana_base', 'Mana base', 'Limit scope to lands and mana sources.'],
                    ['missing_slots', 'Missing slots', 'Only fill gaps in an existing or imported list.'],
                  ].map(([id, title, copy]) => (
                    <ChoiceCard
                      key={id}
                      title={title}
                      copy={copy}
                      active={intent.build_shape === id}
                      disabled={id === 'missing_slots' && !['existing_deck', 'imported_list'].includes(intent.starting_point)}
                      onClick={() => updateIntent('build_shape', id)}
                    />
                  ))}
                </div>

                <div className="build-section-divider"><span>Collection preference</span></div>
                <div className="build-choice-grid">
                  {[
                    ['all_cards', 'All cards', 'Use the legal catalog without ownership bias.'],
                    ['prefer_owned', 'Prefer owned', 'Bias toward owned cards without making them mandatory.'],
                    ['owned_only', 'Owned only', 'Reject candidates outside the supplied collection.'],
                  ].map(([id, title, copy]) => (
                    <ChoiceCard
                      key={id}
                      title={title}
                      copy={copy}
                      active={intent.collection_mode === id}
                      onClick={() => updateIntent('collection_mode', id)}
                    />
                  ))}
                </div>
                {intent.collection_mode !== 'all_cards' && (
                  <label className="build-full-field mt-6">
                    <span>Owned card names</span>
                    <textarea
                      className="input"
                      rows={5}
                      value={ownedText}
                      placeholder="One card per line or comma-separated"
                      onChange={(event) => updateTextConstraint(setOwnedText, event.target.value)}
                    />
                  </label>
                )}
              </div>
            )}

            {step === 3 && (
              <div data-testid="build-step-preserve">
                <p className="page-eyebrow">Preserve</p>
                <h2>What must remain true?</h2>
                <p className="build-step-copy">These rules survive future construction and recommendation passes.</p>

                <div className="build-field-grid">
                  <label>
                    <span>Protected cards</span>
                    <textarea
                      className="input"
                      rows={5}
                      value={protectedText}
                      placeholder="Pet cards or fixed inclusions"
                      onChange={(event) => updateTextConstraint(setProtectedText, event.target.value)}
                    />
                  </label>
                  <label>
                    <span>Excluded cards</span>
                    <textarea
                      className="input"
                      rows={5}
                      value={excludedText}
                      placeholder="Cards this build must never include"
                      onChange={(event) => updateTextConstraint(setExcludedText, event.target.value)}
                    />
                  </label>
                </div>
                <label className="build-full-field mt-6">
                  <span>Protected packages</span>
                  <textarea
                    className="input"
                    rows={4}
                    value={packagesText}
                    placeholder="Package name: Card One, Card Two"
                    onChange={(event) => updateTextConstraint(setPackagesText, event.target.value)}
                  />
                  <small>Use one package per line. Package names remain visible in future cut protection.</small>
                </label>

                <div className="build-section-divider"><span>Intentional constraints</span></div>
                <div className="build-check-grid">
                  {CONSTRAINTS.map(([id, label]) => (
                    <label key={id}>
                      <input
                        type="checkbox"
                        checked={intent.intentional_constraints.includes(id)}
                        onChange={() => toggleListValue('intentional_constraints', id)}
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>

                <label className="build-full-field mt-6">
                  <span>Desired experience</span>
                  <textarea
                    className="input"
                    rows={4}
                    value={intent.notes || ''}
                    placeholder="Describe what should feel true when the deck plays well."
                    onChange={(event) => updateIntent('notes', event.target.value)}
                  />
                </label>
              </div>
            )}

            {step === 4 && normalized && (
              <div data-testid="build-step-review">
                <p className="page-eyebrow">Review</p>
                <h2>The engine contract, before any cards.</h2>
                <p className="build-step-copy">This is the normalized input future construction must obey. No hidden prompt or popularity shortcut is added.</p>

                <div className="build-review-grid">
                  <article>
                    <Layers3 aria-hidden="true" />
                    <span>Playstyle mapping</span>
                    <strong>{labelize(mapping.playstyle.id)}</strong>
                    <p>{mapping.playstyle.strategy_priorities.map(labelize).join(' · ')}</p>
                    <div className="mapping-chip-row">
                      {Object.entries(mapping.playstyle.lane_weights).map(([lane, weight]) => (
                        <span key={lane}>{labelize(lane)} {weight}×</span>
                      ))}
                    </div>
                  </article>
                  <article>
                    <ShieldCheck aria-hidden="true" />
                    <span>Power policy</span>
                    <strong>{mapping.power.range.join('–')} · {labelize(intent.playstyle)}</strong>
                    <p>
                      Fast mana {mapping.power.policies.fast_mana}; tutors {mapping.power.policies.tutors}; compact combos {mapping.power.policies.compact_combos}; interaction {mapping.power.policies.interaction}.
                    </p>
                  </article>
                  <article>
                    <WalletCards aria-hidden="true" />
                    <span>Budget and collection</span>
                    <strong>{labelize(mapping.budget.mode)} · {labelize(mapping.collection.mode)}</strong>
                    <p>
                      {mapping.budget.hard_gate ? 'Price limits are hard gates.' : 'Price limits are preferences or targets.'}
                      {' '}{mapping.collection.hard_gate ? 'Only supplied owned cards qualify.' : `${mapping.collection.owned_card_count} owned cards bias selection.`}
                    </p>
                  </article>
                  <article>
                    <Library aria-hidden="true" />
                    <span>Build scope</span>
                    <strong>{labelize(mapping.build_shape.scope)}</strong>
                    <p>At most {mapping.build_shape.maximum_requested_slots} slots may be requested by this shape.</p>
                  </article>
                </div>

                <section className="build-engine-ledger">
                  <div>
                    <span>Engine profile</span>
                    <strong>{deckProfile.optimization_mode} · power {deckProfile.power_level_min}–{deckProfile.power_level_max}</strong>
                  </div>
                  <div>
                    <span>Enforced priorities</span>
                    <strong>{deckProfile.strategy_priorities.map(labelize).join(' · ') || 'Balanced defaults'}</strong>
                  </div>
                  <div>
                    <span>Protected constraints</span>
                    <strong>{deckProfile.intentional_constraints.map(labelize).join(' · ') || 'None added'}</strong>
                  </div>
                </section>

                <div className="build-phase-boundary">
                  <ShieldCheck aria-hidden="true" />
                  <div>
                    <strong>{mapping.construction.enabled ? 'Bounded scaffold construction is enabled.' : 'Manual construction stays in control.'}</strong>
                    <p>
                      {mapping.construction.enabled
                        ? 'Phase 4 can propose a validated partial portfolio and basic-land baseline. Unsupported slots remain open.'
                        : 'Saving opens a manual deck without selecting cards.'}
                      {' '}Complete-list generation remains disabled until Phase 5 promotion.
                    </p>
                  </div>
                </div>

                <label className="build-confirm-row">
                  <input
                    type="checkbox"
                    checked={reviewConfirmed}
                    onChange={(event) => setReviewConfirmed(event.target.checked)}
                    data-testid="build-confirm-input"
                  />
                  <span>
                    <strong>I confirm this is the deck experience I want.</strong>
                    <small>Future systems may propose structured changes, but cannot silently replace this intent.</small>
                  </span>
                </label>
              </div>
            )}
          </div>

          <aside className="build-context-rail">
            <p className="page-eyebrow">Current contract</p>
            <h3>{intent.deck_name || 'Unnamed deck plan'}</h3>
            <dl>
              <div><dt>Start</dt><dd>{labelize(intent.starting_point)}</dd></div>
              <div><dt>Commander</dt><dd>{intent.commander_name || 'Not fixed'}</dd></div>
              <div><dt>Playstyle</dt><dd>{labelize(intent.playstyle)}</dd></div>
              <div><dt>Power</dt><dd>{intent.power_level_min}–{intent.power_level_max}</dd></div>
              <div><dt>Budget</dt><dd>{labelize(intent.budget_mode)}</dd></div>
              <div><dt>Scope</dt><dd>{labelize(intent.build_shape)}</dd></div>
            </dl>
            <div className="build-context-note">
              <strong>Intent first</strong>
              <span>The same confirmed fields always normalize to the same engine input.</span>
            </div>
          </aside>
        </section>

        <footer className="build-footer-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => step === 0 ? navigate('/dashboard') : setStep((current) => current - 1)}
          >
            <ArrowLeft aria-hidden="true" /> {step === 0 ? 'Leave builder' : 'Back'}
          </button>
          {step < 4 ? (
            <button
              type="button"
              className="btn-primary"
              onClick={nextStep}
              disabled={normalizing}
              data-testid="build-next-button"
            >
              {normalizing ? 'Checking choices...' : step === 3 ? 'Review mappings' : 'Continue'}
              {!normalizing && <ArrowRight aria-hidden="true" />}
            </button>
          ) : (
            <button
              type="button"
              className="btn-primary"
              onClick={savePlan}
              disabled={!reviewConfirmed || saving}
              data-testid="build-save-button"
            >
              {saving
                ? 'Saving plan...'
                : intent.build_mode === 'guided_scaffold'
                  ? existingDeckId ? 'Save and rebuild scaffold' : 'Save and build scaffold'
                  : existingDeckId ? 'Save deck plan' : 'Save and open manual deck'}
              {!saving && <ArrowRight aria-hidden="true" />}
            </button>
          )}
        </footer>
      </main>
    </div>
  );
}
