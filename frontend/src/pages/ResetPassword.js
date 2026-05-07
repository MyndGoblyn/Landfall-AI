import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Lock } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import ForestManaIcon from '../components/ForestManaIcon';
import TurnstileCaptcha from '../components/TurnstileCaptcha';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const [password, setPassword] = useState('');
  const [captchaToken, setCaptchaToken] = useState('');
  const [captchaResetKey, setCaptchaResetKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const { resetPassword } = useAuth();
  const navigate = useNavigate();
  const captchaEnabled = Boolean(process.env.REACT_APP_TURNSTILE_SITE_KEY);
  const token = searchParams.get('token');

  const handleCaptchaVerify = useCallback((value) => {
    setCaptchaToken(value);
  }, []);

  const handleCaptchaExpire = useCallback(() => {
    setCaptchaToken('');
  }, []);

  const resetCaptcha = () => {
    setCaptchaToken('');
    setCaptchaResetKey((value) => value + 1);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!token) {
      toast.error('Reset link is missing a token');
      return;
    }

    setLoading(true);
    const result = await resetPassword(token, password, captchaToken);
    if (result.success) {
      toast.success('Password updated');
      navigate('/dashboard');
    } else {
      toast.error(result.error);
      resetCaptcha();
    }
    setLoading(false);
  };

  return (
    <div className="app-shell min-h-screen flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8 page-hero">
          <ForestManaIcon className="w-16 h-16 mx-auto mb-4" />
          <p className="page-eyebrow mb-2">Account recovery</p>
          <h1 className="text-4xl font-bold mb-2 brand-title">Reset Password</h1>
          <p className="page-copy">Choose a new password for your LandFall AI account.</p>
        </div>

        <div className="glass-panel p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium mb-2 text-amber-100" htmlFor="password">
                <Lock className="w-4 h-4 inline mr-2" />
                New password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="input"
                placeholder="New password"
                minLength={12}
                required
              />
              <p className="mt-2 text-xs text-amber-100/70">Use at least 12 characters.</p>
            </div>

            {captchaEnabled && (
              <TurnstileCaptcha
                onVerify={handleCaptchaVerify}
                onExpire={handleCaptchaExpire}
                resetKey={captchaResetKey}
              />
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? 'Updating...' : 'Update Password'}
            </button>
          </form>
        </div>

        <div className="text-center mt-6">
          <button onClick={() => navigate('/auth')} className="page-copy hover:text-white transition-colors">
            <ArrowLeft className="w-4 h-4 inline mr-2" />
            Back to Login
          </button>
        </div>
      </div>
    </div>
  );
}
