import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { ChevronLeft, ChevronRight, Compass, Search, SlidersHorizontal } from 'lucide-react';
import { toast } from 'sonner';
import AppTopbar from '../components/AppTopbar';
import { ManaPipRow } from '../components/ManaSymbols';
import { useAuth } from '../context/AuthContext';
import { API } from '../lib/api';

const COLOR_OPTIONS = ['W', 'U', 'B', 'R', 'G', 'C'];
const ARCHETYPE_OPTIONS = [
  'artifact', 'combat', 'combo', 'control', 'enchantment', 'graveyard', 'lands',
  'spells', 'stax', 'tokens', 'typal', 'value', 'voltron',
];
const PLAYSTYLE_OPTIONS = ['aggressive', 'value', 'control', 'combo'];
const DEFAULT_FILTERS = {
  query: '',
  colors: [],
  color_mode: 'exact',
  max_cmc: '',
  archetype: '',
  playstyle: '',
};

const labelize = (value) => value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

const filtersFromSearchParams = (params) => {
  const requestedColors = (params.get('colors') || '').toUpperCase();
  const requestedCmc = Number.parseInt(params.get('max_cmc') || '', 10);
  const colors = requestedColors.includes('C')
    ? ['C']
    : COLOR_OPTIONS.filter((color) => color !== 'C' && requestedColors.includes(color));
  const colorMode = params.get('color_mode');
  const requestedArchetype = params.get('archetype') || '';
  const requestedPlaystyle = params.get('playstyle') || '';
  return {
    query: params.get('query') || '',
    colors,
    color_mode: colorMode === 'inclusive' ? 'inclusive' : 'exact',
    max_cmc: Number.isFinite(requestedCmc) && requestedCmc >= 0 && requestedCmc <= 20
      ? String(requestedCmc)
      : '',
    archetype: ARCHETYPE_OPTIONS.includes(requestedArchetype) ? requestedArchetype : '',
    playstyle: PLAYSTYLE_OPTIONS.includes(requestedPlaystyle) ? requestedPlaystyle : '',
  };
};

const pageFromSearchParams = (params) => {
  const page = Number.parseInt(params.get('page') || '1', 10);
  return Number.isFinite(page) && page > 0 ? page : 1;
};

const atlasSearchParams = (filters, page = 1) => {
  const params = new URLSearchParams();
  if (filters.query.trim()) params.set('query', filters.query.trim());
  if (filters.colors.length) params.set('colors', filters.colors.join(''));
  if (filters.colors.length && filters.color_mode !== 'exact') {
    params.set('color_mode', filters.color_mode);
  }
  if (filters.max_cmc !== '') params.set('max_cmc', filters.max_cmc);
  if (filters.archetype) params.set('archetype', filters.archetype);
  if (filters.playstyle) params.set('playstyle', filters.playstyle);
  if (page > 1) params.set('page', String(page));
  return params;
};

export default function CommanderAtlas() {
  const [searchParams, setSearchParams] = useSearchParams();
  const searchKey = searchParams.toString();
  const [filters, setFilters] = useState(() => filtersFromSearchParams(searchParams));
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();

  const loadCommanders = async (requestedPage = 1, requestedFilters = filters) => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/commander-atlas`, {
        params: {
          query: requestedFilters.query.trim() || undefined,
          colors: requestedFilters.colors.join('') || undefined,
          color_mode: requestedFilters.color_mode,
          max_cmc: requestedFilters.max_cmc || undefined,
          archetype: requestedFilters.archetype || undefined,
          playstyle: requestedFilters.playstyle || undefined,
          page: requestedPage,
          page_size: 24,
        },
        headers: getAuthHeaders(),
      });
      setResult(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not load Commander Atlas');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(searchKey);
    const nextFilters = filtersFromSearchParams(params);
    setFilters(nextFilters);
    loadCommanders(pageFromSearchParams(params), nextFilters);
  }, [searchKey]);

  const toggleColor = (color) => {
    setFilters((current) => {
      if (color === 'C') {
        return {
          ...current,
          colors: current.colors.includes('C') ? [] : ['C'],
        };
      }
      const colors = current.colors.includes(color)
        ? current.colors.filter((value) => value !== color)
        : [...current.colors.filter((value) => value !== 'C'), color];
      return { ...current, colors };
    });
  };

  const submitFilters = (event) => {
    event.preventDefault();
    const nextParams = atlasSearchParams(filters, 1);
    if (nextParams.toString() === searchKey) {
      loadCommanders(1, filters);
    } else {
      setSearchParams(nextParams);
    }
  };

  const clearFilters = () => {
    setFilters(DEFAULT_FILTERS);
    if (searchKey) {
      setSearchParams(new URLSearchParams());
    } else {
      loadCommanders(1, DEFAULT_FILTERS);
    }
  };

  const changePage = (page) => {
    setSearchParams(atlasSearchParams(filters, page));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const sourceDate = result?.catalog?.source_updated_at
    ? new Date(result.catalog.source_updated_at).toLocaleDateString()
    : null;

  return (
    <div className="app-shell">
      <AppTopbar />

      <main className="container mx-auto px-6 py-12 max-w-7xl" data-testid="commander-atlas">
        <section className="atlas-hero mb-10">
          <div>
            <p className="page-eyebrow mb-3">Commander Atlas</p>
            <h2 className="page-title">Browse the command zone.<br /><span>Filter by the plan.</span></h2>
            <p className="page-copy">
              Search LandFall's local commander catalog by identity, mana value, archetype, and playstyle. Results rank for your filters—not global popularity.
            </p>
          </div>
          <button className="atlas-discover-link" onClick={() => navigate('/random-commander')}>
            <Compass aria-hidden="true" />
            <span>Want a surprise?</span>
            <strong>Open Discover</strong>
          </button>
        </section>

        <form className="atlas-filter-panel" onSubmit={submitFilters}>
          <div className="atlas-search-field">
            <label htmlFor="atlas-search">Commander name</label>
            <div>
              <Search aria-hidden="true" />
              <input
                id="atlas-search"
                value={filters.query}
                onChange={(event) => setFilters({ ...filters, query: event.target.value })}
                placeholder="Meren, Atraxa, Yuriko..."
                data-testid="atlas-search-input"
              />
            </div>
          </div>

          <div className="atlas-color-filter">
            <span>Color identity</span>
            <div className="atlas-color-row">
              {COLOR_OPTIONS.map((color) => (
                <button
                  key={color}
                  type="button"
                  className={filters.colors.includes(color) ? 'selected' : ''}
                  onClick={() => toggleColor(color)}
                  aria-pressed={filters.colors.includes(color)}
                  aria-label={color === 'C' ? 'Colorless' : `${color} color identity`}
                >
                  <ManaPipRow colors={[color]} compact />
                </button>
              ))}
            </div>
          </div>

          <label className="atlas-select-field">
            <span>Color match</span>
            <select
              value={filters.color_mode}
              onChange={(event) => setFilters({ ...filters, color_mode: event.target.value })}
            >
              <option value="exact">Exact identity</option>
              <option value="inclusive">Contains selected</option>
            </select>
          </label>

          <label className="atlas-select-field">
            <span>Archetype</span>
            <select
              value={filters.archetype}
              onChange={(event) => setFilters({ ...filters, archetype: event.target.value })}
            >
              <option value="">Any archetype</option>
              {(result?.filters?.archetypes || []).map((option) => (
                <option value={option} key={option}>{labelize(option)}</option>
              ))}
            </select>
          </label>

          <label className="atlas-select-field">
            <span>Playstyle</span>
            <select
              value={filters.playstyle}
              onChange={(event) => setFilters({ ...filters, playstyle: event.target.value })}
            >
              <option value="">Any playstyle</option>
              {(result?.filters?.playstyles || []).map((option) => (
                <option value={option} key={option}>{labelize(option)}</option>
              ))}
            </select>
          </label>

          <label className="atlas-select-field">
            <span>Maximum mana value</span>
            <input
              type="number"
              min="0"
              max="20"
              value={filters.max_cmc}
              onChange={(event) => setFilters({ ...filters, max_cmc: event.target.value })}
              placeholder="Any"
            />
          </label>

          <div className="atlas-filter-actions">
            <button className="btn-primary" type="submit" disabled={loading}>
              <SlidersHorizontal aria-hidden="true" />
              Apply filters
            </button>
            <button className="btn-secondary" type="button" onClick={clearFilters} disabled={loading}>
              Clear
            </button>
          </div>
        </form>

        <div className="atlas-result-heading">
          <div>
            <p className="page-eyebrow">Catalog results</p>
            <h3>{loading && !result ? 'Building commander index...' : `${result?.total || 0} matches`}</h3>
          </div>
          {result?.catalog && (
            <p>
              {result.catalog.commander_count.toLocaleString()} legal commanders
              {sourceDate ? ` · card data ${sourceDate}` : ''}
            </p>
          )}
        </div>

        {loading ? (
          <div className="atlas-loading" role="status">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-amber-300"></div>
            <span>Filtering the local commander catalog...</span>
          </div>
        ) : result?.commanders?.length ? (
          <>
            <section className="atlas-grid" aria-label="Commander catalog results">
              {result.commanders.map((commander) => (
                <article className="atlas-card" key={commander.oracle_id}>
                  <button
                    type="button"
                    className="atlas-card-art"
                    onClick={() => navigate(`/commanders/${commander.oracle_id}`)}
                    aria-label={`Open ${commander.name} profile`}
                  >
                    {commander.image_url && <img src={commander.image_url} alt={commander.name} />}
                    <span className={`atlas-profile-status ${commander.profile_status}`}>
                      {commander.profile_status === 'reviewed' ? 'Reviewed profile' : commander.profile_status}
                    </span>
                  </button>
                  <div className="atlas-card-body">
                    <div className="atlas-card-title">
                      <h3>{commander.name}</h3>
                      <ManaPipRow colors={commander.color_identity || []} compact />
                    </div>
                    <p>{commander.type_line}</p>
                    <div className="atlas-card-tags">
                      {[...new Set([
                        ...commander.archetype_families.slice(0, 2),
                        ...commander.playstyles.slice(0, 1),
                      ])].map((tag) => (
                        <span key={tag}>{labelize(tag)}</span>
                      ))}
                      <span>MV {commander.cmc}</span>
                    </div>
                    <button
                      type="button"
                      className="atlas-open-profile"
                      onClick={() => navigate(`/commanders/${commander.oracle_id}`)}
                    >
                      Study this commander <span aria-hidden="true">→</span>
                    </button>
                  </div>
                </article>
              ))}
            </section>

            <nav className="atlas-pagination" aria-label="Commander catalog pages">
              <button
                className="btn-secondary"
                disabled={result.page <= 1 || loading}
                onClick={() => changePage(result.page - 1)}
              >
                <ChevronLeft aria-hidden="true" /> Previous
              </button>
              <span>Page {result.page} of {result.total_pages}</span>
              <button
                className="btn-secondary"
                disabled={result.page >= result.total_pages || loading}
                onClick={() => changePage(result.page + 1)}
              >
                Next <ChevronRight aria-hidden="true" />
              </button>
            </nav>
          </>
        ) : (
          <section className="atlas-empty glass-panel">
            <Search aria-hidden="true" />
            <h3>No commanders match those filters.</h3>
            <p className="page-copy">Try inclusive colors, a higher mana value, or one fewer strategy filter.</p>
            <button className="btn-secondary" onClick={clearFilters}>Clear filters</button>
          </section>
        )}
      </main>
    </div>
  );
}
