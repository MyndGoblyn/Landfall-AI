import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ManaBackground from './components/ManaBackground';
import Landing from './pages/Landing';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import DeckImport from './pages/DeckImport';
import DeckViewer from './pages/DeckViewer';
import AnalysisResults from './pages/AnalysisResults';
import CommanderLookup from './pages/CommanderLookup';
import RandomCommander from './pages/RandomCommander';
import VerifyEmail from './pages/VerifyEmail';
import VerifyEmailSent from './pages/VerifyEmailSent';
import ResetPassword from './pages/ResetPassword';
import './App.css';

const LandingRoute = () => {
  const [searchParams] = useSearchParams();
  const verifyToken = searchParams.get('verify_email_token');
  const resetToken = searchParams.get('reset_password_token');

  if (verifyToken) {
    return <Navigate to={`/verify-email?token=${encodeURIComponent(verifyToken)}`} replace />;
  }

  if (resetToken) {
    return <Navigate to={`/reset-password?token=${encodeURIComponent(resetToken)}`} replace />;
  }

  return <Landing />;
};

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }
  
  return user ? children : <Navigate to="/auth" />;
};

function App() {
  return (
    <AuthProvider>
      <ManaBackground />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingRoute />} />
          <Route path="/auth" element={<Auth />} />
          <Route path="/verify-email-sent" element={<VerifyEmailSent />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/dashboard" element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          } />
          <Route path="/deck/:deckId/import" element={
            <ProtectedRoute>
              <DeckImport />
            </ProtectedRoute>
          } />
          <Route path="/deck/:deckId/view" element={
            <ProtectedRoute>
              <DeckViewer />
            </ProtectedRoute>
          } />
          <Route path="/analysis/:analysisId" element={
            <ProtectedRoute>
              <AnalysisResults />
            </ProtectedRoute>
          } />
          <Route path="/commander-lookup" element={
            <ProtectedRoute>
              <CommanderLookup />
            </ProtectedRoute>
          } />
          <Route path="/random-commander" element={
            <ProtectedRoute>
              <RandomCommander />
            </ProtectedRoute>
          } />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
