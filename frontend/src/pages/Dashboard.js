import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import AppTopbar from '../components/AppTopbar';
import AnalyzeModal from '../components/AnalyzeModal';
import { ManaPip } from '../components/ManaSymbols';
import { API } from '../lib/api';
import useRotatingStatus from '../hooks/useRotatingStatus';

const ANALYSIS_STATUS_MESSAGES = [
  'Reading deck roles and commander themes',
  'Checking synergy tags and role coverage',
  'Building pilot notes and risk checks',
  'Scoring upgrade and cut candidates',
];

export default function Dashboard() {
  const [decks, setDecks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showAnalyzeModal, setShowAnalyzeModal] = useState(false);
  const [selectedDeck, setSelectedDeck] = useState(null);
  const [newDeckName, setNewDeckName] = useState('');
  const [newDeckCommander, setNewDeckCommander] = useState(null);
  const [analysisLoadingMode, setAnalysisLoadingMode] = useState(null);
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const analysisStatus = useRotatingStatus(Boolean(analysisLoadingMode), ANALYSIS_STATUS_MESSAGES);

  useEffect(() => {
    fetchDecks();
  }, []);

  useEffect(() => {
    if (searchParams.get('newDeck') !== '1') return;
    const commander = searchParams.get('commander')?.trim() || null;
    setNewDeckCommander(commander);
    setNewDeckName(commander ? `${commander} deck` : '');
    setShowCreateModal(true);
  }, [searchParams]);

  const fetchDecks = async () => {
    try {
      const response = await axios.get(`${API}/decks`, {
        headers: getAuthHeaders()
      });
      setDecks(response.data);
    } catch (error) {
      toast.error('Failed to load decks');
    } finally {
      setLoading(false);
    }
  };

  const createDeck = async (e) => {
    e.preventDefault();
    if (!newDeckName.trim()) return;

    try {
      const response = await axios.post(
        `${API}/decks`,
        { name: newDeckName, commander: newDeckCommander },
        { headers: getAuthHeaders() }
      );
      toast.success('Deck created!');
      setDecks([response.data, ...decks]);
      setShowCreateModal(false);
      setNewDeckName('');
      setNewDeckCommander(null);
      navigate(`/deck/${response.data.id}/import`);
    } catch (error) {
      toast.error('Failed to create deck');
    }
  };

  const deleteDeck = async (deckId) => {
    if (!window.confirm('Delete this deck?')) return;

    try {
      await axios.delete(`${API}/decks/${deckId}`, {
        headers: getAuthHeaders()
      });
      setDecks(decks.filter(d => d.id !== deckId));
      toast.success('Deck deleted');
    } catch (error) {
      toast.error('Failed to delete deck');
    }
  };

  const openAnalyzeModal = (deck) => {
    if (!deck.cards || deck.cards.length === 0) {
      toast.error('Deck must have cards imported first');
      return;
    }
    setSelectedDeck(deck);
    setShowAnalyzeModal(true);
  };

  const analyzeDeck = async (categories, deep = false, intentProfile = null) => {
    if (!selectedDeck) return;

    try {
      setAnalysisLoadingMode(deep ? 'deep' : 'fast');
      toast.loading(deep ? 'Running expanded deterministic analysis...' : 'Analyzing deck with deterministic engine...');
      const response = await axios.post(
        `${API}/decks/${selectedDeck.id}/analyze${deep ? '/deep' : ''}`,
        {
          ...(categories ? { categories } : {}),
          ...(intentProfile ? { intent_profile: intentProfile } : {}),
        },
        { headers: getAuthHeaders() }
      );
      toast.dismiss();
      toast.success(deep ? 'Expanded analysis complete!' : 'Analysis complete!');
      navigate(`/analysis/${response.data.id}`);
    } catch (error) {
      toast.dismiss();
      toast.error(error.response?.data?.detail || 'Analysis failed');
    } finally {
      setAnalysisLoadingMode(null);
    }
  };

  return (
    <div className="app-shell">
      <AppTopbar showLogout />
      {analysisLoadingMode && (
        <div className="analysis-progress-banner" role="status" aria-live="polite">
          <strong>{analysisLoadingMode === 'deep' ? 'Expanded Analysis' : 'Deck Analysis'}</strong>
          <span>{analysisStatus}</span>
        </div>
      )}

      {/* Main Content */}
      <main className="container mx-auto px-6 py-12 max-w-7xl">
        <div className="workspace-heading mb-8">
          <div>
            <p className="page-eyebrow mb-2">Your Commander workspace</p>
            <h2 data-testid="dashboard-title" className="text-4xl font-bold mb-2 page-title">What are you working on?</h2>
            <p className="page-copy">Continue a deck, investigate a commander, or start with a fresh direction.</p>
          </div>
          <button
            data-testid="create-deck-btn"
            onClick={() => setShowCreateModal(true)}
            className="btn-primary"
          >
            <Plus className="w-5 h-5 inline mr-2" />
            New Deck
          </button>
        </div>

        <section className="workspace-tool-strip mb-12" aria-label="Commander tools">
          <button type="button" className="workspace-tool workspace-tool-amber" onClick={() => navigate('/commanders')}>
            <span>Commander Atlas</span>
            <strong>Browse the command zone</strong>
            <small>Filter legal commanders by identity, archetype, playstyle, and reviewed plan evidence.</small>
          </button>
          <button type="button" className="workspace-tool workspace-tool-blue" onClick={() => navigate('/commander-lookup')}>
            <span>Commander Lab</span>
            <strong>Study a game plan</strong>
            <small>Strategy, synergy, pilot notes, and focused card fits.</small>
          </button>
          <button type="button" className="workspace-tool workspace-tool-green" onClick={() => navigate('/random-commander')}>
            <span>Discover</span>
            <strong>Find a build-around</strong>
            <small>Filter by color, mana value, and the play pattern you want.</small>
          </button>
          <button type="button" className="workspace-tool workspace-tool-violet" onClick={() => navigate('/how-it-works')}>
            <span>Guide</span>
            <strong>Understand the evidence</strong>
            <small>See how the engine ranks fits and communicates uncertainty.</small>
          </button>
        </section>

        <div className="deck-library-heading">
          <p className="page-eyebrow">Deck library</p>
          <span>{decks.length} {decks.length === 1 ? 'deck' : 'decks'}</span>
        </div>

        {loading ? (
          <div className="text-center py-20">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500"></div>
          </div>
        ) : decks.length === 0 ? (
          <div data-testid="empty-state" className="text-center py-20 glass-panel">
            <div className="empty-deck-mark" aria-hidden="true"><span>99</span></div>
            <h3 className="text-2xl font-semibold mb-2">Start with a decklist</h3>
            <p className="page-copy mb-6">Create a deck, then import from Archidekt, Moxfield, or pasted text.</p>
            <button onClick={() => setShowCreateModal(true)} className="btn-primary">
              Create Deck
            </button>
          </div>
        ) : (
          <div data-testid="deck-list" className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {decks.map((deck) => (
              <div key={deck.id} data-testid={`deck-card-${deck.id}`} className="card deck-card-theme">
                <div className="deck-card-header mb-4">
                  <div className="deckbox-mini" aria-hidden="true"></div>
                  <div>
                    <h3 className="text-xl font-semibold mb-1">{deck.name}</h3>
                    {deck.commander && (
                      <p className="text-sm text-amber-300">{deck.commander}</p>
                    )}
                  </div>
                  <button
                    data-testid={`delete-deck-${deck.id}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteDeck(deck.id);
                    }}
                    className="text-red-400 hover:text-red-300 transition-colors"
                    aria-label={`Delete ${deck.name}`}
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>

                <div className="flex items-center gap-2 text-sm text-gray-200 mb-4">
                  <span>{deck.cards ? deck.cards.reduce((sum, c) => sum + (c.qty || 1), 0) : 0} cards</span>
                  {deck.color_identity?.length > 0 && (
                    <span className="flex gap-1">
                      {deck.color_identity.map((color) => (
                        <ManaPip key={color} color={color} />
                      ))}
                    </span>
                  )}
                </div>

                <div className="flex flex-col gap-2">
                  {(!deck.cards || deck.cards.length === 0) ? (
                    <button
                      data-testid={`import-deck-${deck.id}`}
                      onClick={() => navigate(`/deck/${deck.id}/import`)}
                      className="btn-primary py-2 text-sm"
                    >
                      Import Cards
                    </button>
                  ) : (
                    <>
                      <button
                        data-testid={`analyze-deck-${deck.id}`}
                        onClick={() => openAnalyzeModal(deck)}
                        className="btn-primary py-2 text-sm"
                      >
                        Analyze Deck
                      </button>
                      <div className="flex gap-2">
                        <button
                          data-testid={`view-cards-${deck.id}`}
                          onClick={() => navigate(`/deck/${deck.id}/view`)}
                          className="btn-secondary flex-1 py-2 text-sm"
                        >
                          View List
                        </button>
                        <button
                          data-testid={`reimport-deck-${deck.id}`}
                          onClick={() => navigate(`/deck/${deck.id}/import`)}
                          className="btn-secondary flex-1 py-2 text-sm"
                        >
                          Replace Import
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Create Deck Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 px-6">
          <div data-testid="create-deck-modal" className="glass-panel p-8 max-w-md w-full">
            <p className="page-eyebrow mb-2">New List</p>
            <h3 className="text-2xl font-bold mb-6 page-title">Create New Deck</h3>
            <form onSubmit={createDeck}>
              <div className="mb-6">
                <label className="block text-sm font-medium mb-2">Deck Name</label>
                <input
                  data-testid="deck-name-input"
                  type="text"
                  value={newDeckName}
                  onChange={(e) => setNewDeckName(e.target.value)}
                  className="input"
                  placeholder="My Awesome Commander Deck"
                  autoFocus
                  required
                />
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  data-testid="cancel-create-btn"
                  onClick={() => {
                    setShowCreateModal(false);
                    setNewDeckName('');
                    setNewDeckCommander(null);
                    if (searchParams.get('newDeck') === '1') {
                      setSearchParams(new URLSearchParams(), { replace: true });
                    }
                  }}
                  className="btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  data-testid="confirm-create-btn"
                  type="submit"
                  className="btn-primary flex-1"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Analyze Modal */}
      {showAnalyzeModal && (
        <AnalyzeModal
          isOpen={showAnalyzeModal}
          onClose={() => setShowAnalyzeModal(false)}
          onAnalyze={analyzeDeck}
          deck={selectedDeck}
        />
      )}
    </div>
  );
}
