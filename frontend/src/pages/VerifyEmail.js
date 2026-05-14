import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle, LayoutDashboard, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import BrandEmblem from '../components/BrandEmblem';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('Verifying your email...');
  const [failed, setFailed] = useState(false);
  const [verified, setVerified] = useState(false);
  const hasVerified = useRef(false);
  const { verifyEmail } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (hasVerified.current) return;
    hasVerified.current = true;

    const token = searchParams.get('token');
    if (!token) {
      setStatus('Verification link is missing a token.');
      setFailed(true);
      return;
    }

    const runVerification = async () => {
      const result = await verifyEmail(token);
      if (result.success) {
        toast.success('Email verified');
        setStatus('Your email has been verified. You can now continue to your dashboard.');
        setVerified(true);
      } else {
        setStatus(result.error);
        setFailed(true);
      }
    };

    runVerification();
  }, [navigate, searchParams, verifyEmail]);

  return (
    <div className="app-shell min-h-screen flex items-center justify-center px-6 py-12">
      <div className="glass-panel w-full max-w-md p-8 text-center">
        <BrandEmblem className="auth-brand-emblem mx-auto mb-5" />
        {failed ? (
          <XCircle className="w-10 h-10 mx-auto mb-4 text-red-300" />
        ) : (
          <CheckCircle className="w-10 h-10 mx-auto mb-4 text-emerald-300" />
        )}
        <p className="page-eyebrow mb-2">Account verification</p>
        <h1 className="text-3xl font-bold mb-3 brand-title">
          {verified ? 'Email Verified' : 'Email Check'}
        </h1>
        <p className="page-copy">{status}</p>
        {verified && (
          <button className="btn-primary mt-6 w-full" onClick={() => navigate('/dashboard')}>
            <LayoutDashboard className="w-4 h-4 inline mr-2" />
            Go to Dashboard
          </button>
        )}
        {failed && (
          <button className="btn-primary mt-6" onClick={() => navigate('/auth')}>
            Back to Login
          </button>
        )}
      </div>
    </div>
  );
}
