import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import ForestManaIcon from '../components/ForestManaIcon';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('Verifying your email...');
  const [failed, setFailed] = useState(false);
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
        navigate('/dashboard');
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
        <ForestManaIcon className="w-14 h-14 mx-auto mb-5" />
        {failed ? (
          <XCircle className="w-10 h-10 mx-auto mb-4 text-red-300" />
        ) : (
          <CheckCircle className="w-10 h-10 mx-auto mb-4 text-emerald-300" />
        )}
        <p className="page-eyebrow mb-2">Account verification</p>
        <h1 className="text-3xl font-bold mb-3 brand-title">Email Check</h1>
        <p className="page-copy">{status}</p>
        {failed && (
          <button className="btn-primary mt-6" onClick={() => navigate('/auth')}>
            Back to Login
          </button>
        )}
      </div>
    </div>
  );
}
