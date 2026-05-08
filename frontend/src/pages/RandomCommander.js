import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Shuffle, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import ForestManaIcon from '../components/ForestManaIcon';
import { ManaPipRow } from '../components/ManaSymbols';
import { useAuth } from '../context/AuthContext';
import { API } from '../lib/api';

export default function RandomCommander() {
  const [loading, setLoading] = useState(false);
  const [commanderData, setCommanderData] = useState(null);
  const [filters, setFilters] = useState({
    colors: [],
    search_text: '',
    max_cmc: null
  });
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const suggestedCards = commanderData?.suggested_cards || [];
  const combos = commanderData?.combos || [];

  const colorOptions = [
    { id: 'C', label: 'Colorless', color: '#898577' },
    { id: 'W', label: 'White', color: '#f8f6d8' },
    { id: 'U', label: 'Blue', color: '#0e68ab' },
    { id: 'B', label: 'Black', color: '#150b00' },
    { id: 'R', label: 'Red', color: '#d3202a' },
    { id: 'G', label: 'Green', color: '#00733e' }
  ];

  const toggleColor = (colorId) => {
    if (colorId === 'C') {
      setFilters({
        ...filters,
        colors: filters.colors.includes('C') ? [] : ['C']
      });
      return;
    }

    if (filters.colors.includes(colorId)) {
      setFilters({...filters, colors: filters.colors.filter(c => c !== colorId)});
    } else {
      setFilters({...filters, colors: [...filters.colors.filter(c => c !== 'C'), colorId]});
    }
  };

  const handleRandomize = async () => {
    setLoading(true);
    try {
      const response = await axios.post(
        `${API}/commander/random`,
        filters,
        { headers: getAuthHeaders() }
      );
      setCommanderData(response.data);
      toast.success('Random commander generated!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate commander');
    } finally {
      setLoading(false);
    }
  };

  const colorText = commanderData?.color_identity?.length
    ? commanderData.color_identity.join('')
    : 'Colorless';

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <div className="container mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <ForestManaIcon className="w-8 h-8" />
            <h1 className="text-2xl font-bold brand-title">LandFall AI</h1>
          </div>
          <button
            onClick={() => navigate('/dashboard')}
            className="btn-secondary py-2 px-4"
          >
            Back to Dashboard
          </button>
        </div>
      </header>

      <main className="container mx-auto px-6 py-12 max-w-6xl">
        <div className="page-hero text-center mb-12">
          <ManaPipRow colors={['W', 'U', 'B', 'R', 'G']} className="hero-mana-row" />
          <p className="page-eyebrow mb-2">Draft A Direction</p>
          <h2 className="text-4xl font-bold mb-4 page-title">Random Commander Generator</h2>
          <p className="page-copy text-lg">Set color, strategy, and mana value constraints, then find a commander to build around.</p>
        </div>

        <div className="glass-panel p-8 mb-8">
          <h3 className="text-xl font-semibold mb-6 text-amber-300">Filters</h3>

          <div className="mb-6">
            <label className="block text-sm font-medium mb-3">Color Identity</label>
            <div className="flex flex-wrap gap-3">
              {colorOptions.map((color) => (
                <button
                  key={color.id}
                  onClick={() => toggleColor(color.id)}
                  className={`w-12 h-12 rounded-full border-2 transition-all ${
                    filters.colors.includes(color.id)
                      ? 'border-amber-300 scale-110 shadow-lg shadow-amber-500/20'
                      : 'border-white/20 hover:border-amber-300/50'
                  }`}
                  style={{ backgroundColor: color.color }}
                  title={color.label}
                  aria-label={color.label}
                  data-testid={`color-${color.id}`}
                />
              ))}
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium mb-3">Strategy Search</label>
            <div className="relative">
              <Search className="w-5 h-5 text-amber-300 absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={filters.search_text}
                onChange={(e) => setFilters({...filters, search_text: e.target.value})}
                placeholder="lifegain counters, artifact graveyard, landfall draw"
                className="input strategy-search-input w-full"
                data-testid="strategy-search-input"
              />
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium mb-3">Max Mana Value</label>
            <input
              type="number"
              value={filters.max_cmc || ''}
              onChange={(e) => setFilters({...filters, max_cmc: e.target.value ? parseInt(e.target.value) : null})}
              placeholder="Any"
              className="input max-w-xs"
              data-testid="max-cmc-input"
            />
          </div>

          <button
            onClick={handleRandomize}
            disabled={loading}
            className="btn-primary px-12 py-4 text-lg"
            data-testid="randomize-btn"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div>
                Generating...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Shuffle className="w-6 h-6" />
                Randomize Commander
              </span>
            )}
          </button>
        </div>

        {commanderData && (
          <div className="space-y-8" data-testid="random-commander-results">
            <div className="glass-panel p-8">
              <div className="flex flex-col md:flex-row gap-8">
                {commanderData.image_url && (
                  <img
                    src={commanderData.image_url}
                    alt={commanderData.name}
                    className="w-64 max-w-full h-auto rounded-lg shadow-2xl"
                  />
                )}
                <div className="flex-1">
                  <p className="page-eyebrow mb-2">Commander</p>
                  <h3 className="text-3xl font-bold mb-3 text-amber-300">{commanderData.name}</h3>
                  <p className="text-gray-100 mb-4">{commanderData.type_line}</p>
                  <div className="tip-panel p-4 mb-4">
                    <p className="text-sm text-gray-100 whitespace-pre-line">{commanderData.oracle_text}</p>
                  </div>
                  <div className="flex flex-wrap gap-3 text-sm items-center">
                    <span className="theme-pill">Mana Value {commanderData.cmc}</span>
                    <span className="theme-pill gap-2">
                      Colors {colorText}
                      <ManaPipRow colors={commanderData.color_identity || []} compact />
                    </span>
                    {commanderData.power && (
                      <span className="theme-pill">P/T {commanderData.power}/{commanderData.toughness}</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="glass-panel p-6">
              <h3 className="text-2xl font-semibold mb-4 text-amber-300">Strategy Analysis</h3>
              <div className="space-y-3">
                {commanderData.strategy_tips.map((tip, idx) => (
                  <div key={idx} className="flex gap-3">
                    <Sparkles className="w-5 h-5 text-amber-300 flex-shrink-0 mt-1" />
                    <p className="text-gray-100">{tip}</p>
                  </div>
                ))}
              </div>
            </div>

            {commanderData.synergies && commanderData.synergies.length > 0 && (
              <div className="glass-panel p-6">
                <h3 className="text-2xl font-semibold mb-4">Synergy Themes</h3>
                <div className="flex flex-wrap gap-2">
                  {commanderData.synergies.map((synergy, idx) => (
                    <span key={idx} className="theme-pill capitalize">
                      {synergy}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="glass-panel p-6">
              <h3 className="text-2xl font-semibold mb-6">Recommended Cards</h3>
              {suggestedCards.length > 0 ? (
                <div className="grid md:grid-cols-2 gap-4">
                  {suggestedCards.map((card, idx) => (
                    <div key={idx} className="card deck-card-theme flex gap-4">
                      <div className="flex gap-2 flex-shrink-0">
                        {card.image_url && (
                          <img
                            src={card.image_url}
                            alt={card.name}
                            className="w-24 h-32 object-cover rounded-lg"
                          />
                        )}
                        {card.image_url_back && (
                          <img
                            src={card.image_url_back}
                            alt={`${card.name} (back)`}
                            className="w-24 h-32 object-cover rounded-lg"
                          />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="font-semibold text-lg mb-2">{card.name}</h4>
                        <p className="text-sm page-copy mb-3">{card.reason}</p>
                        <div className="flex gap-2 text-xs flex-wrap">
                          <span className="theme-pill">{card.role}</span>
                          <span className="theme-pill">Mana Value {card.cmc}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="page-copy">
                  No theme-specific recommendations were found for this commander. Try randomizing again or loosening the filters.
                </p>
              )}
            </div>

            {combos.length > 0 && (
              <div className="glass-panel p-6">
                <h3 className="text-2xl font-semibold mb-6 text-amber-300">Combo Lines</h3>
                <div className="space-y-4">
                  {combos.map((combo, idx) => (
                    <div key={idx} className="tip-panel p-4">
                      <h4 className="text-lg font-semibold text-amber-300 mb-2">{combo.name}</h4>
                      <div className="flex flex-wrap gap-2 mb-2">
                        {combo.cards.map((card, cidx) => (
                          <span key={cidx} className="theme-pill">{card}</span>
                        ))}
                      </div>
                      <p className="text-gray-100 text-sm mb-2">{combo.description}</p>
                      {combo.power_level && <span className="text-xs page-copy">Power Level: {combo.power_level}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
