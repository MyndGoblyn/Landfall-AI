import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { Plus, FileText, Trash2, Play, LogOut } from 'lucide-react';
import { toast } from 'sonner';
import ForestManaIcon from '../components/ForestManaIcon';
import AnalyzeModal from '../components/AnalyzeModal';
import { ManaPip } from '../components/ManaSymbols';
import { API } from '../lib/api';

export default function Dashboard() {
  const [decks, setDecks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showAnalyzeModal, setShowAnalyzeModal] = useState(false);
  const [selectedDeck, setSelectedDeck] = useState(null);
  const [newDeckName, setNewDeckName] = useState('');
  const { user, logout, getAuthHeaders } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    fetchDecks();
  }, []);

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
        { name: newDeckName, commander: null },
        { headers: getAuthHeaders() }
      );
      toast.success('Deck created!');
      setDecks([response.data, ...decks]);
      setShowCreateModal(false);
      setNewDeckName('');
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

  const analyzeDeck = async (categories) => {
    if (!selectedDeck) return;

    try {
      toast.loading('Analyzing deck with enhanced engine...');
      const response = await axios.post(
        `${API}/decks/${selectedDeck.id}/analyze`,
        categories ? { categories } : {},
        { headers: getAuthHeaders() }
      );
      toast.dismiss();
      toast.success('Analysis complete!');
      navigate(`/analysis/${response.data.id}`);
    } catch (error) {
      toast.dismiss();
      toast.error(error.response?.data?.detail || 'Analysis failed');
    }
  };

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-topbar">
        <div className="container mx-auto px-6 py-4 flex flex-col md:flex-row gap-4 md:justify-between md:items-center">
          <div className="flex items-center space-x-2">
            <ForestManaIcon className="w-8 h-8" />
            <h1 className="text-2xl font-bold brand-title">LandFall AI</h1>
          </div>
          <div className="flex w-full md:w-auto items-center justify-between md:justify-end gap-4">
            <span data-testid="user-email" className="text-sm text-gray-200 truncate">{user?.email}</span>
            <button
              data-testid="logout-btn"
              onClick={() => {
                logout();
                navigate('/');
              }}
              className="btn-secondary py-2 px-4"
            >
              <LogOut className="w-4 h-4 inline mr-2" />
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-12 max-w-7xl">
        {/* Quick Tools */}
        <div className="grid md:grid-cols-3 gap-4 mb-12">
          <button
            onClick={() => navigate('/commander-lookup')}
            className="card tool-card zone-card transition-all"
            data-zone="COMMAND"
            data-testid="commander-lookup-btn"
          >
            <div className="zone-rune">C</div>
            <h3 className="text-xl font-semibold mb-2">Commander Lookup</h3>
            <p className="text-sm page-copy">Search any commander for strategy tips</p>
          </button>
          <button
            onClick={() => navigate('/random-commander')}
            className="card tool-card zone-card transition-all"
            data-zone="DRAFT"
            data-testid="random-commander-btn"
          >
            <div className="zone-rune">?</div>
            <h3 className="text-xl font-semibold mb-2">Random Commander</h3>
            <p className="text-sm page-copy">Generate a random commander to build</p>
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="card tool-card zone-card transition-all"
            data-zone="LIBRARY"
            data-testid="create-deck-shortcut-btn"
          >
            <div className="zone-rune">99</div>
            <h3 className="text-xl font-semibold mb-2 text-amber-300">Deck Analysis</h3>
            <p className="text-sm page-copy">Build and analyze your decks</p>
          </button>
        </div>

        <div className="flex justify-between items-center mb-8 page-hero">
          <div>
            <p className="page-eyebrow mb-2">Library</p>
            <h2 data-testid="dashboard-title" className="text-4xl font-bold mb-2 page-title">Your Decks</h2>
            <p className="page-copy">Import and analyze your Commander decks</p>
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

        {loading ? (
          <div className="text-center py-20">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500"></div>
          </div>
        ) : decks.length === 0 ? (
          <div data-testid="empty-state" className="text-center py-20 glass-panel">
            <FileText className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <h3 className="text-2xl font-semibold mb-2">No decks yet</h3>
            <p className="page-copy mb-6">Create your first deck to get started</p>
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
                        data-testid={`view-cards-${deck.id}`}
                        onClick={() => navigate(`/deck/${deck.id}/view`)}
                        className="btn-primary py-2 text-sm"
                      >
                        View Cards
                      </button>
                      <div className="flex gap-2">
                        <button
                          data-testid={`reimport-deck-${deck.id}`}
                          onClick={() => navigate(`/deck/${deck.id}/import`)}
                          className="btn-secondary flex-1 py-2 text-sm"
                        >
                          Re-import
                        </button>
                        <button
                          data-testid={`analyze-deck-${deck.id}`}
                          onClick={() => openAnalyzeModal(deck)}
                          className="btn-primary flex-1 py-2 text-sm"
                        >
                          <Play className="w-4 h-4 inline mr-1" />
                          Analyze
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
