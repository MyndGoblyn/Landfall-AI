import { useEffect, useState } from 'react';
import axios from 'axios';
import { Bookmark, BookmarkCheck } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { API } from '../lib/api';

export default function TrackCommanderButton({ commander, source }) {
  const [trackedRecord, setTrackedRecord] = useState(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const { getAuthHeaders } = useAuth();
  const oracleId = commander?.oracle_id;

  useEffect(() => {
    let cancelled = false;

    if (!oracleId) {
      setTrackedRecord(null);
      return () => {
        cancelled = true;
      };
    }

    setChecking(true);
    axios.get(`${API}/tracked-commanders/${encodeURIComponent(oracleId)}`, {
      headers: getAuthHeaders(),
    }).then((response) => {
      if (!cancelled) setTrackedRecord(response.data);
    }).catch((error) => {
      if (!cancelled && error.response?.status === 404) {
        setTrackedRecord(null);
      }
    }).finally(() => {
      if (!cancelled) setChecking(false);
    });

    return () => {
      cancelled = true;
    };
    // The current session header is read at request time; commander identity is
    // the only value that should restart this status check.
  }, [oracleId]);

  const toggleTracked = async () => {
    if (!commander?.name || saving) return;
    setSaving(true);

    try {
      if (trackedRecord) {
        await axios.delete(
          `${API}/tracked-commanders/${encodeURIComponent(trackedRecord.commander_oracle_id)}`,
          { headers: getAuthHeaders() }
        );
        setTrackedRecord(null);
        toast.success('Removed from Track List');
      } else {
        const response = await axios.post(
          `${API}/tracked-commanders`,
          {
            commander_name: commander.name,
            source,
          },
          { headers: getAuthHeaders() }
        );
        setTrackedRecord(response.data);
        toast.success('Added to Track List');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not update Track List');
    } finally {
      setSaving(false);
    }
  };

  const isTracked = Boolean(trackedRecord);

  return (
    <button
      type="button"
      className={`track-commander-button ${isTracked ? 'is-tracked' : ''}`}
      onClick={toggleTracked}
      disabled={checking || saving}
      aria-pressed={isTracked}
      data-testid="track-commander-btn"
    >
      {isTracked ? <BookmarkCheck aria-hidden="true" /> : <Bookmark aria-hidden="true" />}
      <span>{saving ? 'Saving...' : isTracked ? 'Tracked' : 'Track commander'}</span>
    </button>
  );
}
