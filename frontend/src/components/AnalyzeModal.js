import { useState } from 'react';
import { Plus, Trash2, X } from 'lucide-react';

const ANALYSIS_CATEGORIES = [
  { id: 'ramp', label: 'Ramp', description: 'Mana acceleration' },
  { id: 'draw', label: 'Card Draw', description: 'Card advantage' },
  { id: 'removal', label: 'Removal', description: 'Destroy/exile threats' },
  { id: 'counter', label: 'Counterspells', description: 'Stack interaction' },
  { id: 'recursion', label: 'Recursion', description: 'Graveyard recovery' },
  { id: 'tutor', label: 'Tutors', description: 'Search library' },
  { id: 'protection', label: 'Protection', description: 'Hexproof/indestructible' },
  { id: 'sweeper', label: 'Board Wipes', description: 'Mass removal' }
];

const INTENT_CONSTRAINTS = [
  { id: 'typal_core', label: 'Preserve typal core' },
  { id: 'spell_density', label: 'Preserve spell density' },
  { id: 'intentional_jank', label: 'Intentional jank' },
  { id: 'flavor_first', label: 'Flavor first' },
  { id: 'low_land_count', label: 'Low lands are intentional' },
  { id: 'no_fast_mana', label: 'No fast mana' },
  { id: 'no_tutors', label: 'No nonland tutors' },
  { id: 'no_infinite_combos', label: 'No infinite combos' },
];

const STRATEGY_PRIORITIES = [
  ['typal', 'Typal density'], ['go_wide', 'Go-wide board'],
  ['spell_chain', 'Spell chain'], ['donation', 'Donation'],
  ['politics', 'Politics'], ['graveyard_recursion', 'Graveyard recursion'],
  ['permanent_engine', 'Permanent engine'], ['blink', 'Blink'],
  ['voltron', 'Voltron'], ['compact_wins', 'Compact wins'],
  ['stack_interaction', 'Stack interaction'], ['mana_fixing', 'Mana fixing'],
  ['combat_combo', 'Combat combo'], ['card_velocity', 'Card velocity'],
  ['protection', 'Protection'],
];

const EXPERIENCE_TAGS = [
  ['budget', 'Budget'], ['casual', 'Casual'], ['political', 'Political'],
  ['chaotic', 'Chaotic'], ['jank', 'Jank'], ['flavor_first', 'Flavor first'],
  ['high_power', 'High power'], ['cedh', 'cEDH'], ['tournament', 'Tournament'],
];

const PROTECTED_ROLES = [
  ['closer', 'Closers'], ['engine', 'Engines'], ['mana_fixing', 'Mana fixing'],
  ['card_advantage', 'Card advantage'], ['interaction', 'Interaction'],
  ['tutor', 'Tutors'], ['combo_piece', 'Combo pieces'],
  ['typal_payoff', 'Typal payoffs'],
];

const splitCardNames = (value) => value
  .split(/\r?\n/)
  .map((name) => name.trim())
  .filter(Boolean);

export default function AnalyzeModal({ deck, onClose, onAnalyze, isOpen }) {
  const [selectedCategories, setSelectedCategories] = useState([]);
  const savedIntent = deck?.intent_profile || {};
  const [intentConfirmed, setIntentConfirmed] = useState(Boolean(savedIntent.confirmed));
  const [optimizationMode, setOptimizationMode] = useState(savedIntent.optimization_mode || 'preserve');
  const [powerTarget, setPowerTarget] = useState(
    savedIntent.power_level_min === savedIntent.power_level_max
      ? String(savedIntent.power_level_min || '')
      : ''
  );
  const [budgetMode, setBudgetMode] = useState(savedIntent.budget_mode || 'unknown');
  const [budgetLimit, setBudgetLimit] = useState(savedIntent.budget_limit_usd ?? '');
  const [maxCardPrice, setMaxCardPrice] = useState(savedIntent.max_card_price_usd ?? '');
  const [primaryStrategy, setPrimaryStrategy] = useState(savedIntent.primary_strategy || '');
  const [desiredExperience, setDesiredExperience] = useState(savedIntent.desired_experience || '');
  const [protectedCards, setProtectedCards] = useState((savedIntent.protected_cards || []).join('\n'));
  const [excludedCards, setExcludedCards] = useState((savedIntent.excluded_cards || []).join('\n'));
  const [protectedPackages, setProtectedPackages] = useState(
    (savedIntent.protected_packages || []).map((packageInfo) => ({
      name: packageInfo.name || '',
      cards: (packageInfo.cards || []).join('\n'),
    }))
  );
  const [intentionalConstraints, setIntentionalConstraints] = useState(savedIntent.intentional_constraints || []);
  const [strategyPriorities, setStrategyPriorities] = useState(savedIntent.strategy_priorities || []);
  const [experienceTags, setExperienceTags] = useState(savedIntent.experience_tags || []);
  const [protectedRoles, setProtectedRoles] = useState(savedIntent.protected_roles || []);
  const [powerOutlierPolicy, setPowerOutlierPolicy] = useState(savedIntent.power_outlier_policy || 'auto');
  const [genericStapleTolerance, setGenericStapleTolerance] = useState(savedIntent.generic_staple_tolerance || 'auto');
  const [intentError, setIntentError] = useState('');
  if (!isOpen || !deck) return null;

  const toggleCategory = (catId) => {
    if (selectedCategories.includes(catId)) {
      setSelectedCategories(selectedCategories.filter(c => c !== catId));
    } else {
      setSelectedCategories([...selectedCategories, catId]);
    }
  };

  const toggleConstraint = (constraintId) => {
    setIntentionalConstraints((current) => (
      current.includes(constraintId)
        ? current.filter((value) => value !== constraintId)
        : [...current, constraintId]
    ));
  };

  const toggleListValue = (setter, value) => {
    setter((current) => (
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value]
    ));
  };

  const updateProtectedPackage = (index, field, value) => {
    setProtectedPackages((current) => current.map((packageInfo, packageIndex) => (
      packageIndex === index ? { ...packageInfo, [field]: value } : packageInfo
    )));
  };

  const handleAnalyze = (deep = false) => {
    if (budgetMode === 'strict' && maxCardPrice === '') {
      setIntentError('Strict budget mode requires a maximum price per suggested card.');
      return;
    }
    const numericPower = powerTarget === '' ? null : Number(powerTarget);
    const intentProfile = {
      schema_version: 1,
      confirmed: intentConfirmed,
      power_level_min: numericPower,
      power_level_max: numericPower,
      budget_mode: budgetMode,
      budget_limit_usd: budgetLimit === '' ? null : Number(budgetLimit),
      max_card_price_usd: maxCardPrice === '' ? null : Number(maxCardPrice),
      optimization_mode: optimizationMode,
      primary_strategy: primaryStrategy.trim() || null,
      desired_experience: desiredExperience.trim() || null,
      strategy_priorities: strategyPriorities,
      experience_tags: experienceTags,
      protected_roles: protectedRoles,
      power_outlier_policy: powerOutlierPolicy,
      generic_staple_tolerance: genericStapleTolerance,
      protected_cards: splitCardNames(protectedCards),
      protected_packages: protectedPackages
        .map((packageInfo) => ({
          name: packageInfo.name.trim(),
          cards: splitCardNames(packageInfo.cards),
        }))
        .filter((packageInfo) => packageInfo.name && packageInfo.cards.length > 0),
      excluded_cards: splitCardNames(excludedCards),
      intentional_constraints: intentionalConstraints,
    };
    onAnalyze(
      selectedCategories.length > 0 ? selectedCategories : null,
      deep,
      intentProfile,
    );
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 px-6">
      <div className="glass-panel p-8 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-start mb-6">
          <div>
            <p className="page-eyebrow mb-2">Deck Tech</p>
            <h3 className="text-2xl font-bold mb-2 page-title">Analyze Deck</h3>
            <p className="page-copy text-sm">Choose focus areas for a targeted pass, or leave everything open for a full review.</p>
          </div>
          <button
            onClick={onClose}
            className="icon-link-button"
            aria-label="Close analysis modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="tip-panel p-4 mb-6">
          <h4 className="font-semibold mb-1">Deck: {deck.name}</h4>
          {deck.commander && (
            <p className="text-sm text-amber-300">Commander: {deck.commander}</p>
          )}
        </div>

        <div className="mb-8">
          <h4 className="font-semibold mb-3">Category Filter</h4>
          <p className="text-sm page-copy mb-4">
            Select only the parts of the deck you want the analysis engine to prioritize.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {ANALYSIS_CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                data-testid={`category-${cat.id}`}
                onClick={() => toggleCategory(cat.id)}
                className={`p-4 rounded-lg border-2 transition-all text-left ${
                  selectedCategories.includes(cat.id)
                    ? 'border-amber-300 bg-amber-500/10'
                    : 'border-white/10 bg-white/5 hover:border-amber-300/40'
                }`}
              >
                <div className="font-semibold mb-1">{cat.label}</div>
                <div className="text-xs page-copy">{cat.description}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="intent-editor mb-8">
          <div className="mb-4">
            <p className="page-eyebrow mb-1">Recommendation Intent</p>
            <h4 className="font-semibold">Tell the engine what must remain true</h4>
            <p className="text-sm page-copy mt-1">
              These choices are saved with the deck and constrain additions and cuts.
            </p>
          </div>

          <label className="intent-confirm-row">
            <input
              data-testid="intent-confirmed-input"
              type="checkbox"
              checked={intentConfirmed}
              onChange={(event) => setIntentConfirmed(event.target.checked)}
            />
            <span>
              <strong>Use this as confirmed deck intent</strong>
              <small>When unchecked, cut confidence is deliberately reduced.</small>
            </span>
          </label>

          <div className="intent-field-grid mt-4">
            <label>
              <span>Optimization style</span>
              <select
                data-testid="optimization-mode-input"
                className="input"
                value={optimizationMode}
                onChange={(event) => setOptimizationMode(event.target.value)}
              >
                <option value="preserve">Preserve identity</option>
                <option value="tune">Tune and improve</option>
                <option value="competitive">Competitive efficiency</option>
                <option value="repair">Repair major defects</option>
              </select>
            </label>
            <label>
              <span>Target power</span>
              <select
                data-testid="power-target-input"
                className="input"
                value={powerTarget}
                onChange={(event) => setPowerTarget(event.target.value)}
              >
                <option value="">Unknown</option>
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((level) => (
                  <option key={level} value={level}>{level} / 10</option>
                ))}
              </select>
            </label>
            <label>
              <span>Budget handling</span>
              <select
                data-testid="budget-mode-input"
                className="input"
                value={budgetMode}
                onChange={(event) => setBudgetMode(event.target.value)}
              >
                <option value="unknown">Unknown</option>
                <option value="strict">Strict cap</option>
                <option value="target">Target, flag exceptions</option>
                <option value="flexible">Flexible</option>
                <option value="unrestricted">Unrestricted</option>
              </select>
            </label>
            <label>
              <span>Total deck budget (USD)</span>
              <input
                data-testid="budget-limit-input"
                className="input"
                type="number"
                min="0"
                step="1"
                value={budgetLimit}
                onChange={(event) => setBudgetLimit(event.target.value)}
                placeholder="Optional"
              />
            </label>
            <label>
              <span>Maximum suggested card (USD)</span>
              <input
                data-testid="max-card-price-input"
                className="input"
                type="number"
                min="0"
                step="0.01"
                value={maxCardPrice}
                onChange={(event) => setMaxCardPrice(event.target.value)}
                placeholder={budgetMode === 'strict' ? 'Required' : 'Optional'}
              />
            </label>
            <label>
              <span>Primary strategy</span>
              <input
                data-testid="primary-strategy-input"
                className="input"
                value={primaryStrategy}
                onChange={(event) => setPrimaryStrategy(event.target.value)}
                placeholder="Example: budget Elf tokens"
                maxLength={160}
              />
            </label>
          </div>

          <label className="block mt-4">
            <span className="block text-sm font-medium mb-2">Desired play experience</span>
            <textarea
              data-testid="desired-experience-input"
              className="input intent-textarea"
              value={desiredExperience}
              onChange={(event) => setDesiredExperience(event.target.value)}
              placeholder="Example: political group hug; avoid generic control"
              maxLength={320}
            />
          </label>

          <details className="intent-advanced mt-5">
            <summary>
              <span>
                <strong>Advanced deck preferences</strong>
                <small>Protect packages, shape strategy priorities, and enforce special constraints.</small>
              </span>
              <span className="intent-advanced-status">Optional</span>
            </summary>
            <div className="intent-advanced-body">
          <div>
            <span className="block text-sm font-medium mb-2">Enforced strategy priorities</span>
            <div className="intent-constraint-grid">
              {STRATEGY_PRIORITIES.map(([id, label]) => (
                <label key={id}>
                  <input
                    type="checkbox"
                    checked={strategyPriorities.includes(id)}
                    onChange={() => toggleListValue(setStrategyPriorities, id)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="mt-4">
            <span className="block text-sm font-medium mb-2">Desired experience tags</span>
            <div className="intent-constraint-grid">
              {EXPERIENCE_TAGS.map(([id, label]) => (
                <label key={id}>
                  <input
                    type="checkbox"
                    checked={experienceTags.includes(id)}
                    onChange={() => toggleListValue(setExperienceTags, id)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="mt-4">
            <span className="block text-sm font-medium mb-2">Roles protected from heuristic cuts</span>
            <div className="intent-constraint-grid">
              {PROTECTED_ROLES.map(([id, label]) => (
                <label key={id}>
                  <input
                    type="checkbox"
                    checked={protectedRoles.includes(id)}
                    onChange={() => toggleListValue(setProtectedRoles, id)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="intent-field-grid mt-4">
            <label>
              <span>Power outliers</span>
              <select
                className="input"
                value={powerOutlierPolicy}
                onChange={(event) => setPowerOutlierPolicy(event.target.value)}
              >
                <option value="auto">Infer from power target</option>
                <option value="preserve">Preserve intended power</option>
                <option value="allow">Allow high-power outliers</option>
              </select>
            </label>
            <label>
              <span>Generic staple tolerance</span>
              <select
                className="input"
                value={genericStapleTolerance}
                onChange={(event) => setGenericStapleTolerance(event.target.value)}
              >
                <option value="auto">Infer from strategy</option>
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
              </select>
            </label>
          </div>

          <label className="block mt-4">
            <span className="block text-sm font-medium mb-2">Never suggest cutting</span>
            <textarea
              data-testid="protected-cards-input"
              className="input intent-textarea"
              value={protectedCards}
              onChange={(event) => setProtectedCards(event.target.value)}
              placeholder="One complete card name per line"
            />
          </label>

          <label className="block mt-4">
            <span className="block text-sm font-medium mb-2">Never recommend adding</span>
            <textarea
              data-testid="excluded-cards-input"
              className="input intent-textarea"
              value={excludedCards}
              onChange={(event) => setExcludedCards(event.target.value)}
              placeholder="One complete card name per line"
            />
          </label>

          <div className="mt-4">
            <div className="flex items-center justify-between gap-3 mb-2">
              <span className="text-sm font-medium">Protected packages</span>
              <button
                type="button"
                className="btn-secondary py-2 px-3 text-xs"
                onClick={() => setProtectedPackages((current) => [
                  ...current,
                  { name: '', cards: '' },
                ])}
              >
                <Plus className="w-3.5 h-3.5 inline mr-1" />
                Add package
              </button>
            </div>
            <p className="text-xs page-copy mb-3">
              Package members are protected from cuts and tracked as one dependency set.
            </p>
            <div className="protected-package-list">
              {protectedPackages.map((packageInfo, index) => (
                <div className="protected-package-editor" key={`package-${index}`}>
                  <div className="protected-package-heading">
                    <input
                      className="input"
                      value={packageInfo.name}
                      onChange={(event) => updateProtectedPackage(index, 'name', event.target.value)}
                      placeholder="Package name"
                      maxLength={80}
                    />
                    <button
                      type="button"
                      className="icon-link-button"
                      aria-label={`Remove protected package ${index + 1}`}
                      onClick={() => setProtectedPackages((current) => (
                        current.filter((_, packageIndex) => packageIndex !== index)
                      ))}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  <textarea
                    className="input intent-textarea"
                    value={packageInfo.cards}
                    onChange={(event) => updateProtectedPackage(index, 'cards', event.target.value)}
                    placeholder="One package card per line"
                  />
                </div>
              ))}
              {protectedPackages.length === 0 && (
                <p className="muted-copy text-sm">No protected packages declared.</p>
              )}
            </div>
          </div>

          <div className="mt-4">
            <span className="block text-sm font-medium mb-2">Intentional constraints</span>
            <div className="intent-constraint-grid">
              {INTENT_CONSTRAINTS.map((constraint) => (
                <label key={constraint.id}>
                  <input
                    type="checkbox"
                    checked={intentionalConstraints.includes(constraint.id)}
                    onChange={() => toggleConstraint(constraint.id)}
                  />
                  <span>{constraint.label}</span>
                </label>
              ))}
            </div>
          </div>
            </div>
          </details>
          {intentError && <p className="intent-error mt-3">{intentError}</p>}
        </div>

        {selectedCategories.length > 0 && (
          <div className="tip-panel mb-6 p-4">
            <p className="text-sm text-amber-300">
              Selected: {selectedCategories.map(c => ANALYSIS_CATEGORIES.find(cat => cat.id === c)?.label).join(', ')}
            </p>
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={onClose}
            className="btn-secondary flex-1"
          >
            Cancel
          </button>
          <button
            data-testid="confirm-analyze-btn"
            onClick={() => handleAnalyze(false)}
            className="btn-primary flex-1"
          >
            Analyze Deck
          </button>
          <button
            data-testid="confirm-deep-analyze-btn"
            onClick={() => handleAnalyze(true)}
            className="btn-secondary flex-1"
          >
            Expanded Analysis
          </button>
        </div>
        <p className="page-copy text-xs mt-4 text-center">
          Expanded Analysis runs broader deterministic checks and can take longer than a standard pass.
        </p>
      </div>
    </div>
  );
}
