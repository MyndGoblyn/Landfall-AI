import { NavLink, useNavigate } from 'react-router-dom';
import { HelpCircle, LayoutDashboard, LogOut } from 'lucide-react';
import BrandEmblem from './BrandEmblem';
import { useAuth } from '../context/AuthContext';

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
      <div className="container mx-auto px-6 py-4 flex flex-col lg:flex-row gap-4 lg:justify-between lg:items-center">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="topbar-brand"
          data-testid="topbar-brand"
        >
          <BrandEmblem className="topbar-brand-mark" />
          <span className="text-2xl font-bold brand-title">LandFall AI</span>
        </button>

        <div className="topbar-actions">
          <nav className="topbar-nav" aria-label="Primary">
            <NavLink to="/dashboard" className={navLinkClass} data-testid="topbar-dashboard-tab">
              <LayoutDashboard className="w-4 h-4" />
              Dashboard
            </NavLink>
            <NavLink to="/how-it-works" className={navLinkClass} data-testid="topbar-how-it-works-tab">
              <HelpCircle className="w-4 h-4" />
              How It Works
            </NavLink>
          </nav>

          {meta && <span className="topbar-meta">{meta}</span>}
          {actions}

          {showLogout && (
            <>
              {user?.email && <span data-testid="user-email" className="topbar-meta max-w-[220px] truncate">{user.email}</span>}
              <button
                data-testid="logout-btn"
                onClick={handleLogout}
                className="btn-secondary py-2 px-4"
              >
                <LogOut className="w-4 h-4 inline mr-2" />
                Logout
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
