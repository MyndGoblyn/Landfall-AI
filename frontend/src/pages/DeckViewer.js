import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { ExternalLink } from 'lucide-react';
import { toast } from 'sonner';
import AppTopbar from '../components/AppTopbar';
import { API } from '../lib/api';

export default function DeckViewer() {
  const { deckId } = useParams();
  const [deckData, setDeckData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    fetchDeckCards();
  }, [deckId]);

  const fetchDeckCards = async () => {
    try {
      const response = await axios.get(`${API}/decks/${deckId}/cards`, {
        headers: getAuthHeaders()
      });
      setDeckData(response.data);
    } catch (error) {
      toast.error('Failed to load deck cards');
      navigate('/dashboard');
    } finally {
      setLoading(false);
    }
  };

  const filterCards = (cards) => {
    if (filter === 'all') return cards;

    return cards.filter(card => {
      const type = card.type_line || '';
      if (filter === 'creatures') return type.includes('Creature');
      if (filter === 'spells') return !type.includes('Creature') && !type.includes('Land');
      if (filter === 'lands') return type.includes('Land');
      return true;
    });
  };

  if (loading) {
    return (
      <div className="app-shell flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-400"></div>
      </div>
    );
  }

  const filteredCards = filterCards(deckData?.cards || []);
  const totalCards = deckData?.total_cards || 0;

  return (
    <div className="app-shell">
      <AppTopbar meta={`${totalCards} cards total`} />

      <main className="container mx-auto px-6 py-12 max-w-7xl">
        <div className="page-hero mb-8">
          <p className="page-eyebrow mb-2">Deck Library</p>
          <h2 data-testid="deck-title" className="text-4xl font-bold mb-2 page-title">{deckData?.deck_name}</h2>
          {deckData?.commander && (
            <p className="text-xl text-amber-300">Commander: {deckData.commander}</p>
          )}
        </div>

        <div className="tab-strip inline-flex gap-1 mb-8">
          {['all', 'creatures', 'spells', 'lands'].map((f) => (
            <button
              key={f}
              data-testid={`filter-${f}-btn`}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 transition-colors ${
                filter === f ? 'tab-button-active' : 'tab-button hover:bg-white/10'
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        <div data-testid="card-grid" className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {filteredCards.map((card, idx) => (
            <div key={idx} data-testid={`card-${idx}`} className="group relative">
              {card.image_url ? (
                <div className="relative">
                  <img
                    src={card.image_url}
                    alt={card.name}
                    className="w-full rounded-lg shadow-lg transition-transform group-hover:scale-105 group-hover:shadow-2xl"
                  />
                  {card.qty > 1 && (
                    <div className="absolute top-2 right-2 bg-amber-500 text-black px-2 py-1 rounded-full text-sm font-bold">
                      {card.qty}x
                    </div>
                  )}
                  {card.scryfall_uri && (
                    <a
                      href={card.scryfall_uri}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="absolute bottom-2 right-2 bg-black/70 hover:bg-black/90 text-white p-2 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                </div>
              ) : (
                <div className="card text-center">
                  <p className="font-semibold">{card.name}</p>
                  {card.qty > 1 && <p className="text-sm page-copy">{card.qty}x</p>}
                </div>
              )}
            </div>
          ))}
        </div>

        {filteredCards.length === 0 && (
          <div className="empty-zone text-center py-12">
            No cards found in this category.
          </div>
        )}
      </main>
    </div>
  );
}
