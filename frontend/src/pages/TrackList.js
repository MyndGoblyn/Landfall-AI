import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Bookmark, Search, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import AppTopbar from '../components/AppTopbar';
import { ManaPipRow } from '../components/ManaSymbols';
import { useAuth } from '../context/AuthContext';
import { API } from '../lib/api';

const formatSavedDate = (value) => {
  if (!value) return '';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value));
};

export default function TrackList() {
  const [trackedCommanders, setTrackedCommanders] = useState([]);
  const [notes, setNotes] = useState({});
  const [loading, setLoading] = useState(true);
  const [savingNote, setSavingNote] = useState(null);
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchTrackedCommanders = async () => {
      try {
        const response = await axios.get(`${API}/tracked-commanders`, {
          headers: getAuthHeaders(),
        });
        setTrackedCommanders(response.data);
        setNotes(Object.fromEntries(
          response.data.map((item) => [item.commander_oracle_id, item.note || ''])
        ));
      } catch (error) {
        toast.error(error.response?.data?.detail || 'Could not load Track List');
      } finally {
        setLoading(false);
      }
    };

    fetchTrackedCommanders();
  }, []);

  const openAnalysis = (commanderName) => {
    navigate(`/commander-lookup?commander=${encodeURIComponent(commanderName)}`);
  };

  const saveNote = async (item) => {
    const note = notes[item.commander_oracle_id] || '';
    setSavingNote(item.commander_oracle_id);
    try {
      const response = await axios.patch(
        `${API}/tracked-commanders/${encodeURIComponent(item.commander_oracle_id)}`,
        { note },
        { headers: getAuthHeaders() }
      );
      setTrackedCommanders((current) => current.map((entry) => (
        entry.commander_oracle_id === item.commander_oracle_id
          ? response.data
          : entry
      )));
      setNotes((current) => ({
        ...current,
        [item.commander_oracle_id]: response.data.note || '',
      }));
      toast.success('Note saved');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not save note');
    } finally {
      setSavingNote(null);
    }
  };

  const removeTracked = async (item) => {
    if (!window.confirm(`Remove ${item.name} from your Track List?`)) return;

    try {
      await axios.delete(
        `${API}/tracked-commanders/${encodeURIComponent(item.commander_oracle_id)}`,
        { headers: getAuthHeaders() }
      );
      setTrackedCommanders((current) => current.filter(
        (entry) => entry.commander_oracle_id !== item.commander_oracle_id
      ));
      toast.success('Removed from Track List');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not remove commander');
    }
  };

  return (
    <div className="app-shell">
      <AppTopbar />

      <main className="container mx-auto px-6 py-12 max-w-7xl" data-testid="track-list">
        <section className="track-list-hero mb-10">
          <div>
            <p className="page-eyebrow mb-3">Track List</p>
            <h2 className="page-title">Keep the commanders<br /><span>worth returning to.</span></h2>
            <p className="page-copy">
              Save discoveries without freezing their results. Reopen any commander to run the current analysis, synergy, and recommendation systems.
            </p>
          </div>
          <div className="track-list-count" aria-live="polite">
            <Bookmark aria-hidden="true" />
            <strong>{trackedCommanders.length}</strong>
            <span>{trackedCommanders.length === 1 ? 'commander' : 'commanders'}</span>
          </div>
        </section>

        {loading ? (
          <div className="track-list-loading" role="status">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-amber-300"></div>
            <span>Loading your Track List...</span>
          </div>
        ) : trackedCommanders.length === 0 ? (
          <section className="track-list-empty glass-panel">
            <Bookmark aria-hidden="true" />
            <p className="page-eyebrow">Nothing tracked yet</p>
            <h3>Save a commander when one catches your attention.</h3>
            <p className="page-copy">
              Track controls now appear beside Commander Lab and Discover results.
            </p>
            <div className="track-list-empty-actions">
              <button className="btn-primary" onClick={() => navigate('/random-commander')}>
                Discover commanders
              </button>
              <button className="btn-secondary" onClick={() => navigate('/commander-lookup')}>
                Open Commander Lab
              </button>
            </div>
          </section>
        ) : (
          <section className="track-list-grid" aria-label="Tracked commanders">
            {trackedCommanders.map((item) => {
              const draftNote = notes[item.commander_oracle_id] || '';
              const savedNote = item.note || '';
              const noteChanged = draftNote !== savedNote;

              return (
                <article className="tracked-commander-card" key={item.commander_oracle_id}>
                  <button
                    type="button"
                    className="tracked-commander-art"
                    onClick={() => openAnalysis(item.name)}
                    aria-label={`Open current analysis for ${item.name}`}
                  >
                    {item.image_url ? (
                      <img src={item.image_url} alt={item.name} />
                    ) : (
                      <span><Search aria-hidden="true" /></span>
                    )}
                  </button>

                  <div className="tracked-commander-body">
                    <div className="tracked-commander-heading">
                      <div>
                        <p className="page-eyebrow">Tracked {formatSavedDate(item.created_at)}</p>
                        <h3>{item.name}</h3>
                      </div>
                      <ManaPipRow colors={item.color_identity || []} compact />
                    </div>

                    {item.type_line && <p className="tracked-commander-type">{item.type_line}</p>}

                    <label className="tracked-note-field">
                      <span>Your note</span>
                      <textarea
                        value={draftNote}
                        maxLength={400}
                        rows={2}
                        placeholder="Budget direction, preferred theme, or what made this one interesting."
                        onChange={(event) => setNotes((current) => ({
                          ...current,
                          [item.commander_oracle_id]: event.target.value,
                        }))}
                      />
                    </label>

                    <div className="tracked-commander-actions">
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => openAnalysis(item.name)}
                      >
                        Open current analysis
                      </button>
                      <button
                        type="button"
                        className="btn-secondary"
                        disabled={!noteChanged || savingNote === item.commander_oracle_id}
                        onClick={() => saveNote(item)}
                      >
                        {savingNote === item.commander_oracle_id ? 'Saving...' : 'Save note'}
                      </button>
                      <button
                        type="button"
                        className="tracked-remove-button"
                        onClick={() => removeTracked(item)}
                        aria-label={`Remove ${item.name} from Track List`}
                      >
                        <Trash2 aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </section>
        )}
      </main>
    </div>
  );
}
