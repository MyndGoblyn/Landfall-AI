import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const repoRoot = path.resolve(root, '..');

const read = (relativePath) => readFileSync(path.join(root, relativePath), 'utf8');

const checks = [
  {
    name: 'Core protected routes are present',
    file: 'src/App.js',
    tokens: [
      'path="/dashboard"',
      'path="/commander-lookup"',
      'path="/random-commander"',
      'path="/deck/:deckId/import"',
      'path="/analysis/:analysisId"',
      'path="/how-it-works"',
    ],
  },
  {
    name: 'Dashboard primary controls are testable',
    file: 'src/pages/Dashboard.js',
    tokens: [
      'data-testid="commander-lookup-btn"',
      'data-testid="random-commander-btn"',
      'data-testid="create-deck-btn"',
      'data-testid={`analyze-deck-${deck.id}`}',
      'analysis-progress-banner',
      'intent_profile: intentProfile',
    ],
  },
  {
    name: 'Deck intent controls remain available',
    file: 'src/components/AnalyzeModal.js',
    tokens: [
      'data-testid="intent-confirmed-input"',
      'data-testid="optimization-mode-input"',
      'data-testid="power-target-input"',
      'data-testid="max-card-price-input"',
      'data-testid="protected-cards-input"',
      'data-testid="excluded-cards-input"',
      'Protected packages',
      'intentional_constraints',
      'strategy_priorities',
      'experience_tags',
      'protected_roles',
      'power_outlier_policy',
      'generic_staple_tolerance',
    ],
  },
  {
    name: 'Commander lookup controls are testable',
    file: 'src/pages/CommanderLookup.js',
    tokens: [
      'data-testid="commander-search-input"',
      'data-testid="search-commander-btn"',
      'data-testid="deep-search-commander-btn"',
      'appendMoreRecommendedCards',
    ],
  },
  {
    name: 'Random commander controls are testable',
    file: 'src/pages/RandomCommander.js',
    tokens: [
      'COLOR_OPTIONS',
      "id: 'C'",
      'data-testid="strategy-search-input"',
      'data-testid="randomize-btn"',
    ],
  },
  {
    name: 'Deck import loading copy remains visible',
    file: 'src/pages/DeckImport.js',
    tokens: [
      'IMPORT_STATUS_MESSAGES',
      'loading-status-panel',
      'First imports can take up to 1-2 minutes',
    ],
  },
  {
    name: 'Analysis results preserve tabs, pilot notes, and deep status',
    file: 'src/pages/AnalysisResults.js',
    tokens: [
      'PilotNotesPager',
      'DEEP_STATUS_MESSAGES',
      'data-testid="deep-analysis-btn"',
      'data-testid="adds-tab"',
      'data-testid="swaps-tab"',
      'Recommendation intent:',
      'Enforced priorities:',
      'Power outliers:',
      'Tutor targets for',
      'Exact named link:',
      'invariants.dependencies.limitations',
    ],
  },
  {
    name: 'Responsive CSS guards important mobile surfaces',
    file: 'src/App.css',
    tokens: [
      '@media (max-width: 900px)',
      '@media (max-width: 640px)',
      '.commander-recommendation-card',
      '.section-pager-tabs',
      '.analysis-progress-banner',
    ],
  },
  {
    name: 'Cloudflare asset caching and security headers are present',
    file: 'public/_headers',
    tokens: [
      '/static/*',
      'max-age=31556952, immutable',
      'X-Content-Type-Options: nosniff',
      'X-Frame-Options: DENY',
    ],
  },
];

const failures = [];

for (const check of checks) {
  const content = read(check.file);
  for (const token of check.tokens) {
    if (!content.includes(token)) {
      failures.push(`${check.name}: missing "${token}" in ${check.file}`);
    }
  }
}

const publicDir = path.join(root, 'public');
const qaFiles = existsSync(publicDir)
  ? readdirSync(publicDir).filter((file) => /qa|test/i.test(file))
  : [];

if (qaFiles.length > 0) {
  failures.push(`Temporary QA files still present in frontend/public: ${qaFiles.join(', ')}`);
}

const checklistPath = path.join(repoRoot, 'QA_CHECKLIST.md');
if (!existsSync(checklistPath)) {
  failures.push('QA_CHECKLIST.md is missing');
}

if (failures.length > 0) {
  console.error('Source smoke checks failed:');
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log(`Source smoke checks passed (${checks.length} groups).`);
