import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Library,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
} from 'lucide-react';
import { toast } from 'sonner';
import AppTopbar from '../components/AppTopbar';
import { useAuth } from '../context/AuthContext';
import { API } from '../lib/api';

const parseCollectionText = (value) => {
  const entries = [];
  for (const rawLine of value.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#') || /^(sideboard|commander|deck)$/i.test(line)) continue;
    const match = line.match(/^(\d+)\s*[xX]?\s+(.+)$/);
    entries.push({
      card_name: (match ? match[2] : line).trim(),
      quantity: match ? Number(match[1]) : 1,
    });
  }
  return entries.filter((entry) => entry.card_name && entry.quantity > 0);
};

const errorMessage = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail[0]?.msg || fallback;
  return fallback;
};

export default function Collection() {
  const [cards, setCards] = useState([]);
  const [summary, setSummary] = useState(null);
  const [feedback, setFeedback] = useState([]);
  const [policy, setPolicy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importText, setImportText] = useState('');
  const [importMode, setImportMode] = useState('merge');
  const [query, setQuery] = useState('');
  const { getAuthHeaders } = useAuth();

  const load = async () => {
    try {
      const [cardsResponse, summaryResponse, feedbackResponse, policyResponse] = await Promise.all([
        axios.get(`${API}/card-collection`, { headers: getAuthHeaders() }),
        axios.get(`${API}/card-collection/summary`, { headers: getAuthHeaders() }),
        axios.get(`${API}/feedback-history`, { headers: getAuthHeaders() }),
        axios.get(`${API}/feedback-policy`, { headers: getAuthHeaders() }),
      ]);
      setCards(cardsResponse.data);
      setSummary(summaryResponse.data);
      setFeedback(feedbackResponse.data);
      setPolicy(policyResponse.data);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not load your collection'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const filteredCards = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return cards;
    return cards.filter((card) => [card.name, card.type_line]
      .filter(Boolean)
      .some((value) => value.toLowerCase().includes(needle)));
  }, [cards, query]);

  const importCards = async () => {
    const entries = parseCollectionText(importText);
    if (!entries.length) {
      toast.error('Add at least one card name before importing.');
      return;
    }
    if (importMode === 'replace' && !window.confirm(
      'Replace the saved collection with only these cards? Existing collection records not in this list will be removed.'
    )) return;

    setImporting(true);
    try {
      const response = await axios.post(
        `${API}/card-collection/import`,
        { entries, mode: importMode },
        { headers: getAuthHeaders() }
      );
      setCards(response.data);
      setImportText('');
      const nextSummary = await axios.get(`${API}/card-collection/summary`, {
        headers: getAuthHeaders(),
      });
      setSummary(nextSummary.data);
      toast.success(importMode === 'replace'
        ? 'Saved collection replaced.'
        : 'Collection quantities updated.');
    } catch (error) {
      toast.error(errorMessage(error, 'Collection import failed'));
    } finally {
      setImporting(false);
    }
  };

  const updateQuantity = async (card, quantity) => {
    const normalized = Math.max(1, Math.min(999, Number(quantity) || 1));
    if (normalized === card.quantity) return;
    try {
      const response = await axios.patch(
        `${API}/card-collection/${encodeURIComponent(card.oracle_id)}`,
        { quantity: normalized },
        { headers: getAuthHeaders() }
      );
      setCards((current) => current.map((item) => (
        item.oracle_id === card.oracle_id ? response.data : item
      )));
      setSummary((current) => current ? {
        ...current,
        total_copies: current.total_copies - card.quantity + normalized,
      } : current);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not update this quantity'));
    }
  };

  const removeCard = async (card) => {
    if (!window.confirm(`Remove ${card.name} from your saved collection?`)) return;
    try {
      await axios.delete(`${API}/card-collection/${encodeURIComponent(card.oracle_id)}`, {
        headers: getAuthHeaders(),
      });
      setCards((current) => current.filter((item) => item.oracle_id !== card.oracle_id));
      setSummary((current) => current ? {
        ...current,
        unique_cards: current.unique_cards - 1,
        total_copies: current.total_copies - card.quantity,
      } : current);
      toast.success(`${card.name} removed.`);
    } catch (error) {
      toast.error(errorMessage(error, 'Could not remove this card'));
    }
  };

  const clearFeedback = async () => {
    if (!feedback.length) return;
    if (!window.confirm('Delete your private recommendation feedback history? This does not change your decks or collection.')) return;
    try {
      await axios.delete(`${API}/feedback-history`, { headers: getAuthHeaders() });
      setFeedback([]);
      toast.success('Private feedback history deleted.');
    } catch (error) {
      toast.error(errorMessage(error, 'Could not delete feedback history'));
    }
  };

  return (
    <div className="app-shell collection-page" data-testid="collection-page">
      <AppTopbar />
      <main className="container mx-auto px-6 py-10 max-w-7xl">
        <section className="collection-hero">
          <div>
            <p className="page-eyebrow">Collection-aware building</p>
            <h1>Build from what you own.</h1>
            <p>
              Save card quantities once, then use them as a visible preference or a hard
              candidate boundary in Guided Build. Ownership never becomes a popularity signal.
            </p>
          </div>
          <div className="collection-summary" aria-live="polite">
            <Library aria-hidden="true" />
            <div><strong>{summary?.unique_cards || 0}</strong><span>unique cards</span></div>
            <div><strong>{summary?.total_copies || 0}</strong><span>total copies</span></div>
          </div>
        </section>

        <section className="collection-workspace">
          <div className="collection-import-panel">
            <div className="collection-section-heading">
              <div><p className="page-eyebrow">Bulk import</p><h2>Paste a simple card list.</h2></div>
              <Upload aria-hidden="true" />
            </div>
            <p>Use one card per line, optionally prefixed by a quantity such as “12 Forest”.</p>
            <textarea
              className="input"
              rows={10}
              value={importText}
              onChange={(event) => setImportText(event.target.value)}
              placeholder={'1 Sol Ring\n12 Forest\n1 Victimize'}
              data-testid="collection-import-input"
            />
            <div className="collection-import-actions">
              <label>
                <span>Import behavior</span>
                <select className="input" value={importMode} onChange={(event) => setImportMode(event.target.value)}>
                  <option value="merge">Update these cards; keep the rest</option>
                  <option value="replace">Replace the entire saved collection</option>
                </select>
              </label>
              <button className="btn-primary" onClick={importCards} disabled={importing} data-testid="collection-import-button">
                <Upload aria-hidden="true" /> {importing ? 'Resolving cards...' : 'Import collection'}
              </button>
            </div>
          </div>

          <aside className="collection-policy-card">
            <ShieldCheck aria-hidden="true" />
            <p className="page-eyebrow">Private by design</p>
            <h2>Your choices are context, not truth.</h2>
            <p>
              Owned cards affect only builds where you select a collection mode. Feedback is
              stored as private review history and cannot tune production ranking automatically.
            </p>
            <dl>
              <div><dt>Feedback events</dt><dd>{feedback.length}</dd></div>
              <div><dt>Automatic learning</dt><dd>{policy?.automatic_learning ? 'On' : 'Off'}</dd></div>
              <div><dt>Ranking influence</dt><dd>{policy?.production_ranking_influence ? 'On' : 'None'}</dd></div>
            </dl>
            <button className="collection-clear-feedback" onClick={clearFeedback} disabled={!feedback.length}>
              Delete private feedback history
            </button>
          </aside>
        </section>

        <section className="collection-library">
          <div className="collection-library-heading">
            <div><p className="page-eyebrow">Saved collection</p><h2>Current candidate inventory</h2></div>
            <label className="collection-search">
              <Search aria-hidden="true" />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search saved cards" />
            </label>
          </div>

          {loading ? (
            <div className="collection-empty" role="status">Loading your saved collection...</div>
          ) : filteredCards.length ? (
            <div className="collection-card-grid">
              {filteredCards.map((card) => (
                <article className="collection-card" key={card.oracle_id}>
                  <div className="collection-card-art">
                    {card.image_url ? <img src={card.image_url} alt="" loading="lazy" /> : <Library aria-hidden="true" />}
                  </div>
                  <div className="collection-card-copy">
                    <h3>{card.name}</h3>
                    <p>{card.type_line || 'Card details unavailable'}</p>
                    <label>
                      <span>Owned copies</span>
                      <input
                        type="number"
                        min="1"
                        max="999"
                        defaultValue={card.quantity}
                        onBlur={(event) => updateQuantity(card, event.target.value)}
                        aria-label={`${card.name} owned copies`}
                      />
                    </label>
                    <button type="button" onClick={() => removeCard(card)} aria-label={`Remove ${card.name}`}>
                      <Trash2 aria-hidden="true" /> Remove
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="collection-empty">
              <Library aria-hidden="true" />
              <h3>{cards.length ? 'No cards match this search.' : 'No saved cards yet.'}</h3>
              <p>{cards.length ? 'Try a different name or type.' : 'Paste a list above to make collection-aware building available.'}</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
