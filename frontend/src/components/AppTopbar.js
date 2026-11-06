import { NavLink, useNavigate } from 'react-router-dom';
import BrandEmblem from './BrandEmblem';
import { useAuth } from '../context/AuthContext';

const primaryNavigation = [
  { to: '/dashboard', label: 'Decks' },
  { to: '/commander-lookup', label: 'Commander Lab' },
  { to: '/random-commander', label: 'Discover' },
  { to: '/track-list', label: 'Track List' },
];

export default function AppTopbar({ actions = null, meta = null, showLogout = false }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const navLinkClass = ({ isActive }) => (
    `topbar-nav-button ${isActive ? 'topbar-nav-button-active' : ''}`
  );

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <header className="app-topbar">
      <div className="container mx-auto px-6 py-3 app-topbar-layout">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="topbar-brand"
          data-testid="topbar-brand"
        >
          <BrandEmblem className="topbar-brand-mark" />
          <span className="text-2xl font-bold brand-title">LandFall AI</span>
        </button>

        <nav className="topbar-nav" aria-label="Primary">
          {primaryNavigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={navLinkClass}
              data-testid={item.to === '/dashboard' ? 'topbar-dashboard-tab' : undefined}
              end={item.to === '/dashboard'}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="topbar-actions">
          {(meta || actions) && (
            <div className="topbar-context">
              {meta && <span className="topbar-meta">{meta}</span>}
              {actions}
            </div>
          )}

          {showLogout && (
            <div className="topbar-account">
              {user?.email && (
                <span data-testid="user-email" className="topbar-meta max-w-[220px] truncate">
                  {user.email}
                </span>
              )}
              <button
                data-testid="logout-btn"
                onClick={handleLogout}
                className="topbar-account-action"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
