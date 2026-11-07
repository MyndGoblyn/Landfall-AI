import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, CheckCircle2, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import AppTopbar from '../components/AppTopbar';
import { CoverageNotice, RecommendedCardsPager, StrategyPager, ThemeEvidence } from '../components/CommanderAnalysisSections';
import { ManaPipRow } from '../components/ManaSymbols';
import TrackCommanderButton from '../components/TrackCommanderButton';
import { useAuth } from '../context/AuthContext';
import { API } from '../lib/api';
import { appendMoreRecommendedCards } from '../lib/recommendations';

const labelize = (value) => value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function CommanderProfile() {
  const { oracleId } = useParams();
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [moreLoading, setMoreLoading] = useState(false);
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const loadProfile = async () => {
      setLoading(true);
      try {
        const response = await axios.get(
          `${API}/commander-atlas/${encodeURIComponent(oracleId)}/profile`,
          { headers: getAuthHeaders() }
        );
        setPayload(response.data);
      } catch (error) {
        toast.error(error.response?.data?.detail || 'Could not load commander profile');
      } finally {
        setLoading(false);
      }
    };
    loadProfile();
  }, [oracleId]);

  const findMoreCards = async () => {
    const commander = payload?.analysis;
    if (!commander?.name || moreLoading) return;
    setMoreLoading(true);
    try {
      const existingCards = commander.suggested_cards || [];
      const response = await axios.post(
        `${API}/commander/recommendations/more`,
        {
          commander_name: commander.name,
          exclude_names: existingCards.map((card) => card.name),
          page: Math.floor(existingCards.length / 8) + 1,
        },
        { headers: getAuthHeaders() }
      );
      const newCards = response.data.suggested_cards || [];
      if (!newCards.length) {
        toast.info('No additional high-confidence cards found.');
        return;
      }
      setPayload((current) => ({
        ...current,
        analysis: appendMoreRecommendedCards(current.analysis, newCards),
      }));
      toast.success(`Found ${newCards.length} more cards.`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not find more cards');
    } finally {
      setMoreLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="app-shell">
        <AppTopbar />
        <main className="atlas-profile-loading" role="status">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-amber-300"></div>
          <span>Building the current commander profile...</span>
        </main>
      </div>
    );
  }

  if (!payload) {
    return (
      <div className="app-shell">
        <AppTopbar />
        <main className="atlas-profile-loading">
          <h2>Commander profile unavailable.</h2>
          <button className="btn-secondary" onClick={() => navigate('/commanders')}>Return to Atlas</button>
        </main>
      </div>
    );
  }

  const commander = payload.analysis;
  const profile = payload.reviewed_profile;
  const catalog = payload.catalog_entry;
  const discoverSimilar = () => {
    const params = new URLSearchParams();
    if (commander.color_identity?.length) {
      params.set('colors', commander.color_identity.join(''));
    }
    const strategyTerms = (profile?.supported_synergies || catalog.synergies || [])
      .slice(0, 2)
      .map((term) => term.replace(/_/g, ' '));
    if (strategyTerms.length) params.set('search_text', strategyTerms.join(' '));
    navigate(`/random-commander?${params.toString()}`);
  };
  const startDeck = () => {
    const params = new URLSearchParams({
      commander: commander.name,
      oracle_id: commander.oracle_id || catalog.oracle_id,
    });
    navigate(`/build?${params.toString()}`);
  };

  return (
    <div className="app-shell">
      <AppTopbar />
      <main className="container mx-auto px-6 py-10 max-w-7xl commander-profile-page" data-testid="commander-profile">
        <button className="profile-back-link" onClick={() => navigate('/commanders')}>
          <ArrowLeft aria-hidden="true" /> Back to Commander Atlas
        </button>

        <section className="commander-profile-hero">
          <div className="commander-profile-art">
            {commander.image_url && <img src={commander.image_url} alt={commander.name} />}
          </div>
          <div className="commander-profile-intro">
            <div className="commander-profile-kicker">
              <span>{profile ? 'Reviewed commander profile' : 'Live commander profile'}</span>
              {!profile && <span>{catalog.profile_status}</span>}
            </div>
            <div className="commander-profile-title-row">
              <h1>{commander.name}</h1>
              <TrackCommanderButton commander={commander} source="commander_atlas" />
            </div>
            <p className="commander-profile-type">{commander.type_line}</p>
            <div className="commander-profile-meta">
              <span>Mana value {commander.cmc}</span>
              <span className="commander-profile-colors">
                Color identity <ManaPipRow colors={commander.color_identity || []} compact />
              </span>
              <span>Deterministic analysis</span>
            </div>
            <p className="commander-oracle-text">{commander.oracle_text}</p>
            <div className="commander-profile-actions">
              <button
                className="btn-secondary"
                onClick={() => navigate(`/commander-lookup?commander=${encodeURIComponent(commander.name)}`)}
              >
                Open in Commander Lab
              </button>
              <button className="btn-secondary" onClick={discoverSimilar}>
                Discover similar
              </button>
              <button className="btn-primary" onClick={startDeck}>
                Start a deck
              </button>
            </div>
          </div>
        </section>

        <CoverageNotice data={commander} />

        {profile ? (
          <section className="reviewed-profile-section">
            <div className="reviewed-profile-heading">
              <div>
                <p className="page-eyebrow">Reviewed plan evidence</p>
                <h2>What the deck is trying to accomplish</h2>
              </div>
              <div className="reviewed-profile-confidence">
                <CheckCircle2 aria-hidden="true" />
                <span>{profile.confidence} confidence</span>
              </div>
            </div>

            <p className="reviewed-game-plan">{profile.game_plan}</p>

            <div className="reviewed-profile-grid">
              <article>
                <span>Win paths</span>
                <ul>{profile.win_paths.map((item) => <li key={item}>{item}</li>)}</ul>
              </article>
              <article>
                <span>Support needs</span>
                <ul>{profile.support_needs.map((item) => <li key={item}>{item}</li>)}</ul>
              </article>
              <article className="risk-card">
                <span><ShieldAlert aria-hidden="true" /> Common failure modes</span>
                <ul>{profile.common_failure_modes.map((item) => <li key={item}>{item}</li>)}</ul>
              </article>
            </div>

            {profile.packages?.length > 0 && (
              <div className="profile-package-row">
                {profile.packages.map((item) => (
                  <article key={item.name}>
                    <span>Package to preserve</span>
                    <h3>{item.name}</h3>
                    <p>{item.purpose}</p>
                  </article>
                ))}
              </div>
            )}

            <div className="profile-evidence-footer">
              <div>
                <span>Reviewed {profile.reviewed_at}</span>
                <span>Exact Oracle identity match</span>
              </div>
              <div className="profile-tag-row">
                {profile.playstyles.map((item) => <span key={item}>{labelize(item)}</span>)}
                {profile.archetype_ids.slice(0, 3).map((item) => <span key={item}>{labelize(item)}</span>)}
              </div>
            </div>
          </section>
        ) : null}

        <section className="profile-analysis-grid">
          <div className="glass-panel p-6">
            <h2>Strategy analysis</h2>
            <StrategyPager commanderData={commander} />
          </div>
          <div className="glass-panel p-6 profile-synergy-panel">
            <h2>Synergy themes</h2>
            <ThemeEvidence commanderData={commander} />
          </div>
        </section>

        <section className="glass-panel p-6 profile-recommendations">
          <div className="profile-section-heading">
            <div>
              <p className="page-eyebrow">Current engine output</p>
              <h2>Recommended cards</h2>
            </div>
            <span>Fit before popularity</span>
          </div>
          <RecommendedCardsPager
            commanderData={commander}
            emptyMessage="No theme-specific recommendations cleared the evidence floor."
            onFindMore={findMoreCards}
            findMoreLoading={moreLoading}
          />
        </section>

        {profile?.similar_commanders?.length > 0 && (
          <section className="similar-commander-section">
            <p className="page-eyebrow">Related plans</p>
            <h2>Similar commanders, with a reason</h2>
            <div>
              {profile.similar_commanders.map((item) => (
                <button
                  key={item.name}
                  onClick={() => navigate(`/commander-lookup?commander=${encodeURIComponent(item.name)}`)}
                >
                  <strong>{item.name}</strong>
                  <span>{item.reason}</span>
                </button>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
