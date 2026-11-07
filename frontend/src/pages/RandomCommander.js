import { useState } from 'react';
import { Search } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import AppTopbar from '../components/AppTopbar';
import { CoverageNotice, RecommendedCardsPager, StrategyPager, ThemeEvidence } from '../components/CommanderAnalysisSections';
import { ManaPipRow } from '../components/ManaSymbols';
import { useAuth } from '../context/AuthContext';
import { API } from '../lib/api';
import { appendMoreRecommendedCards } from '../lib/recommendations';
import TrackCommanderButton from '../components/TrackCommanderButton';

const COLOR_OPTIONS = [
  { id: 'C', label: 'Colorless', color: '#898577' },
  { id: 'W', label: 'White', color: '#f8f6d8' },
  { id: 'U', label: 'Blue', color: '#0e68ab' },
  { id: 'B', label: 'Black', color: '#150b00' },
  { id: 'R', label: 'Red', color: '#d3202a' },
  { id: 'G', label: 'Green', color: '#00733e' }
];

const initialDiscoverFilters = () => {
  const params = new URLSearchParams(window.location.search);
  const requestedColors = (params.get('colors') || '').toUpperCase();
  const colors = requestedColors.includes('C')
    ? ['C']
    : COLOR_OPTIONS.map((color) => color.id)
      .filter((color) => color !== 'C' && requestedColors.includes(color));
  const requestedCmc = Number.parseInt(params.get('max_cmc') || '', 10);
  return {
    colors,
    search_text: params.get('search_text') || '',
    max_cmc: Number.isFinite(requestedCmc) && requestedCmc >= 0 && requestedCmc <= 20
      ? requestedCmc
      : null,
  };
};

export default function RandomCommander() {
  const [loading, setLoading] = useState(false);
  const [moreLoading, setMoreLoading] = useState(false);
  const [commanderData, setCommanderData] = useState(null);
  const [filters, setFilters] = useState(initialDiscoverFilters);
  const { getAuthHeaders } = useAuth();
  const suggestedCards = commanderData?.suggested_cards || [];
  const combos = commanderData?.combos || [];

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
      toast.success('Commander found!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate commander');
    } finally {
      setLoading(false);
    }
  };

  const colorText = commanderData?.color_identity?.length
    ? commanderData.color_identity.join('')
    : 'Colorless';
  const handleFindMoreCards = async () => {
    if (!commanderData?.name || moreLoading) return;

    setMoreLoading(true);
    try {
      const existingCards = commanderData.suggested_cards || [];
      const response = await axios.post(
        `${API}/commander/recommendations/more`,
        {
          commander_name: commanderData.name,
          exclude_names: existingCards.map((card) => card.name),
          page: Math.floor(existingCards.length / 8) + 1,
        },
        { headers: getAuthHeaders() }
      );

      const newCards = response.data.suggested_cards || [];
      if (newCards.length === 0) {
        toast.info('No additional high-confidence cards found.');
        return;
      }

      setCommanderData((current) => appendMoreRecommendedCards(current, newCards));
      toast.success(`Found ${newCards.length} more cards.`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not find more cards');
    } finally {
      setMoreLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <AppTopbar />

      <main className="container mx-auto px-6 py-12 max-w-6xl">
        <section className="tool-workbench-hero discovery-workbench mb-12">
          <div className="tool-workbench-copy">
            <p className="page-eyebrow mb-3">Discover</p>
            <h2 className="page-title">Set the direction.<br /><span>Meet the commander.</span></h2>
            <p className="page-copy">Choose the colors and play pattern you want. LandFall finds a legal build-around, then explains where its plan can go.</p>
            <div className="tool-workbench-pips">
              <ManaPipRow colors={filters.colors.length > 0 ? filters.colors : ['W', 'U', 'B', 'R', 'G']} compact />
              <span>{filters.colors.length > 0 ? 'Your selected identity' : 'Any color identity'}</span>
            </div>
          </div>

        <div className="tool-workbench-panel">
          <span className="tool-workbench-label">Shape the search</span>

          <div className="mb-6">
            <label className="block text-sm font-medium mb-3">Color Identity</label>
            <div className="flex flex-wrap gap-3">
              {COLOR_OPTIONS.map((color) => (
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
                Find a Commander
              </span>
            )}
          </button>
        </div>
        </section>

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
                  <div className="commander-result-heading mb-3">
                    <h3 className="text-3xl font-bold text-amber-300">{commanderData.name}</h3>
                    <TrackCommanderButton commander={commanderData} source="discover" />
                  </div>
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

            <CoverageNotice data={commanderData} />

            <div className="glass-panel p-6">
              <h3 className="text-2xl font-semibold mb-4 text-amber-300">Strategy Analysis</h3>
              <StrategyPager commanderData={commanderData} />
            </div>

            {(commanderData.theme_evidence?.length > 0 || commanderData.synergies?.length > 0) && (
              <div className="glass-panel p-6">
                <h3 className="text-2xl font-semibold mb-4">Synergy Themes</h3>
                <ThemeEvidence commanderData={commanderData} />
              </div>
            )}

            <div className="glass-panel p-6">
              <h3 className="text-2xl font-semibold mb-6">Recommended Cards</h3>
              {suggestedCards.length > 0 ? (
                <RecommendedCardsPager
                  commanderData={commanderData}
                  emptyMessage="No theme-specific recommendations were found for this commander. Try randomizing again or loosening the filters."
                  onFindMore={handleFindMoreCards}
                  findMoreLoading={moreLoading}
                />
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
