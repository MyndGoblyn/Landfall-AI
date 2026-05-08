import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import ForestManaIcon from '../components/ForestManaIcon';
import { RecommendedCardsPager, StrategyPager } from '../components/CommanderAnalysisSections';
import { ManaPipRow } from '../components/ManaSymbols';
import { useAuth } from '../context/AuthContext';
import { API } from '../lib/api';

export default function CommanderLookup() {
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [deepLoading, setDeepLoading] = useState(false);
  const [optionLoading, setOptionLoading] = useState(false);
  const [commanderOptions, setCommanderOptions] = useState([]);
  const [commanderData, setCommanderData] = useState(null);
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();

  const lookupCommander = async (commanderName, deep = false) => {
    if (deep) {
      setDeepLoading(true);
    } else {
      setLoading(true);
    }
    try {
      const response = await axios.post(
        `${API}/commander/lookup${deep ? '/deep' : ''}`,
        { commander_name: commanderName },
        { headers: getAuthHeaders() }
      );
      setCommanderData(response.data);
      setCommanderOptions([]);
      toast.success(deep ? 'Deep strategy complete!' : 'Commander found!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Commander not found');
    } finally {
      setLoading(false);
      setDeepLoading(false);
    }
  };

  const fetchCommanderOptions = async (query) => {
    setOptionLoading(true);
    try {
      const response = await axios.get(`${API}/commander/search`, {
        params: { query },
        headers: getAuthHeaders(),
      });
      return response.data.candidates || [];
    } catch (error) {
      return [];
    } finally {
      setOptionLoading(false);
    }
  };

  const shouldOfferOptionsFirst = (query) => {
    const trimmed = query.trim();
    return trimmed.length >= 2 && trimmed.length <= 12 && !trimmed.includes(' ');
  };

  const handleSearch = async (e, deep = false) => {
    e.preventDefault();
    const trimmedQuery = searchQuery.trim();
    if (!trimmedQuery) return;

    if (!deep && shouldOfferOptionsFirst(trimmedQuery)) {
      const options = await fetchCommanderOptions(trimmedQuery);
      if (options.length > 1) {
        setCommanderOptions(options);
        setCommanderData(null);
        toast.success('Choose the commander you meant.');
        return;
      }
      if (options.length === 1) {
        await lookupCommander(options[0].name, false);
        return;
      }
    }

    await lookupCommander(trimmedQuery, deep);
  };

  const handleOptionSelect = async (commanderName) => {
    setSearchQuery(commanderName);
    await lookupCommander(commanderName, false);
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
          <p className="page-eyebrow mb-2">Command Zone</p>
          <h2 className="text-4xl font-bold mb-4 page-title">Commander Lookup</h2>
          <p className="page-copy text-lg">Search any commander for strategy tips, synergy themes, and cards that fit the plan.</p>
        </div>

        <form onSubmit={handleSearch} className="max-w-2xl mx-auto mb-12">
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter commander name (e.g., Zur the Enchanter)"
              className="input flex-1"
              data-testid="commander-search-input"
            />
            <button
              type="submit"
              disabled={loading || deepLoading || optionLoading}
              className="btn-primary px-8"
              data-testid="search-commander-btn"
            >
              {loading || optionLoading ? (
                <span className="flex items-center gap-2">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                  Searching...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Search className="w-5 h-5" />
                  Search
                </span>
              )}
            </button>
            <button
              type="button"
              disabled={loading || deepLoading || optionLoading}
              onClick={(e) => handleSearch(e, true)}
              className="btn-secondary px-8"
              data-testid="deep-search-commander-btn"
            >
              {deepLoading ? (
                <span className="flex items-center gap-2">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                  Deep Searching...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5" />
                  Deep Strategy
                </span>
              )}
            </button>
          </div>
        </form>

        {commanderOptions.length > 0 && (
          <div className="glass-panel p-6 mb-10" data-testid="commander-options">
            <h3 className="text-2xl font-semibold mb-4 text-amber-300">Select a Commander</h3>
            <div className="commander-option-grid">
              {commanderOptions.map((option) => (
                <button
                  type="button"
                  key={option.name}
                  className="commander-option-card"
                  onClick={() => handleOptionSelect(option.name)}
                >
                  {option.image_url && (
                    <img src={option.image_url} alt={option.name} className="commander-option-image" />
                  )}
                  <span className="commander-option-body">
                    <span className="commander-option-name">{option.name}</span>
                    <span className="commander-option-type">{option.type_line}</span>
                    <span className="commander-option-meta">
                      Mana Value {option.cmc}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {commanderData && (
          <div className="space-y-8" data-testid="commander-results">
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
              <StrategyPager commanderData={commanderData} />
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

            {commanderData.suggested_cards && commanderData.suggested_cards.length > 0 && (
              <div className="glass-panel p-6">
                <h3 className="text-2xl font-semibold mb-6">Recommended Cards</h3>
                <RecommendedCardsPager
                  commanderData={commanderData}
                  emptyMessage="No theme-specific recommendations were found for this commander."
                />
              </div>
            )}

            {commanderData.combos && commanderData.combos.length > 0 && (
              <div className="glass-panel p-6">
                <h3 className="text-2xl font-semibold mb-6 text-amber-300">Combo Lines</h3>
                <div className="space-y-4">
                  {commanderData.combos.map((combo, idx) => (
                    <div key={idx} className="tip-panel p-4">
                      <h4 className="text-lg font-semibold text-amber-300 mb-2">{combo.name}</h4>
                      <div className="flex flex-wrap gap-2 mb-2">
                        {combo.cards.map((card, cidx) => (
                          <span key={cidx} className="theme-pill">{card}</span>
                        ))}
                      </div>
                      <p className="text-gray-100 text-sm">{combo.description}</p>
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
