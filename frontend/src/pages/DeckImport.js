import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { Link as LinkIcon, FileText, Upload } from 'lucide-react';
import { toast } from 'sonner';
import AppTopbar from '../components/AppTopbar';
import { API } from '../lib/api';
import useRotatingStatus from '../hooks/useRotatingStatus';

export default function DeckImport() {
  const { deckId } = useParams();
  const [deck, setDeck] = useState(null);
  const [sourceType, setSourceType] = useState('url');
  const [urlInput, setUrlInput] = useState('');
  const [textInput, setTextInput] = useState('');
  const [loading, setLoading] = useState(false);
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const importStatus = useRotatingStatus(loading, [
    'Fetching card data from Scryfall',
    'Validating names, faces, and color identity',
    'Reading oracle text and card types',
    'Saving the deck for analysis',
  ]);

  useEffect(() => {
    fetchDeck();
  }, [deckId]);

  const fetchDeck = async () => {
    try {
      const response = await axios.get(`${API}/decks/${deckId}`, {
        headers: getAuthHeaders()
      });
      setDeck(response.data);
    } catch (error) {
      toast.error('Failed to load deck');
      navigate('/dashboard');
    }
  };

  const handleImport = async (e) => {
    e.preventDefault();
    setLoading(true);

    const sourceData = sourceType === 'url' ? urlInput : textInput;

    if (!sourceData.trim()) {
      toast.error('Please enter deck data');
      setLoading(false);
      return;
    }

    try {
      const response = await axios.post(
        `${API}/decks/${deckId}/import`,
        { source_type: sourceType, source_data: sourceData },
        { headers: getAuthHeaders() }
      );
      toast.success(`Imported ${response.data.cards_count} cards!`);
      setTimeout(() => navigate('/dashboard'), 1500);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Import failed');
    } finally {
      setLoading(false);
    }
  };

  if (!deck) {
    return (
      <div className="app-shell flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-400"></div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <AppTopbar />

      <main className="container mx-auto px-6 py-12 max-w-4xl">
        <div className="page-hero mb-8">
          <p className="page-eyebrow mb-2">Deck Intake</p>
          <h2 data-testid="import-title" className="text-4xl font-bold mb-2 page-title">Import Deck</h2>
          <p className="page-copy">Loading cards into <span className="text-amber-300 font-semibold">{deck.name}</span></p>
        </div>

        <div className="glass-panel p-8">
          <div className="tab-strip flex mb-8">
            <button
              data-testid="url-tab-btn"
              onClick={() => setSourceType('url')}
              className={`flex-1 py-3 transition-colors flex items-center justify-center gap-2 ${
                sourceType === 'url' ? 'tab-button-active' : 'tab-button'
              }`}
            >
              <LinkIcon className="w-4 h-4" />
              URL Import
            </button>
            <button
              data-testid="text-tab-btn"
              onClick={() => setSourceType('text')}
              className={`flex-1 py-3 transition-colors flex items-center justify-center gap-2 ${
                sourceType === 'text' ? 'tab-button-active' : 'tab-button'
              }`}
            >
              <FileText className="w-4 h-4" />
              Text Import
            </button>
          </div>

          <form onSubmit={handleImport}>
            {sourceType === 'url' ? (
              <div className="mb-6">
                <label className="block text-sm font-medium mb-2">
                  Deck URL (Archidekt or Moxfield)
                </label>
                <input
                  data-testid="url-input"
                  type="url"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  className="input"
                  placeholder="https://archidekt.com/decks/123456 or https://moxfield.com/decks/..."
                  required
                />
                <p className="text-xs page-copy mt-2">
                  Make sure your deck is set to public before importing.
                </p>
              </div>
            ) : (
              <div className="mb-6">
                <label className="block text-sm font-medium mb-2">
                  Paste Decklist
                </label>
                <textarea
                  data-testid="text-input"
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  className="input"
                  placeholder={"1 Sol Ring\n1 Command Tower\n1 Arcane Signet\n..."}
                  required
                />
                <p className="text-xs page-copy mt-2">
                  Format: "1 Card Name" or "1x Card Name" (one card per line).
                </p>
              </div>
            )}

            <button
              data-testid="import-submit-btn"
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3"
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                  Importing...
                </span>
              ) : (
                <span className="flex items-center justify-center">
                  <Upload className="w-5 h-5 mr-2" />
                  Import Deck
                </span>
              )}
            </button>
            {loading && (
              <div className="loading-status-panel mt-4" aria-live="polite">
                <strong>{importStatus}</strong>
                <p>First imports can take up to 1-2 minutes while the backend fetches uncached card data.</p>
              </div>
            )}
          </form>

          <div className="tip-panel mt-8 p-4">
            <h4 className="font-semibold mb-2 text-amber-300">Import Tips</h4>
            <ul className="text-sm text-gray-100 space-y-1 list-disc pl-5">
              <li>Archidekt: Copy the full deck URL from your browser.</li>
              <li>Moxfield: Copy the deck URL and make sure the list is public.</li>
              <li>Text: Use format "1 Card Name" or "1x Card Name".</li>
              <li>Commander: Add *CMDR* or COMMANDER after the card name.</li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}
