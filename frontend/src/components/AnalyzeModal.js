import { useState } from 'react';
import { Sparkles, X } from 'lucide-react';

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

export default function AnalyzeModal({ deck, onClose, onAnalyze, isOpen }) {
  const [selectedCategories, setSelectedCategories] = useState([]);
  if (!isOpen || !deck) return null;

  const toggleCategory = (catId) => {
    if (selectedCategories.includes(catId)) {
      setSelectedCategories(selectedCategories.filter(c => c !== catId));
    } else {
      setSelectedCategories([...selectedCategories, catId]);
    }
  };

  const handleAnalyze = (deep = false) => {
    onAnalyze(selectedCategories.length > 0 ? selectedCategories : null, deep);
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
            <Sparkles className="w-4 h-4 inline mr-2" />
            Deep Analysis
          </button>
        </div>
        <p className="page-copy text-xs mt-4 text-center">
          Deep Analysis runs broader deterministic checks and can take longer than a fast pass.
        </p>
      </div>
    </div>
  );
}
