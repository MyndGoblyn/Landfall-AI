import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ArrowLeft, Lock, Mail } from 'lucide-react';
import { toast } from 'sonner';
import BrandLogo from '../components/BrandLogo';
import TurnstileCaptcha from '../components/TurnstileCaptcha';

export default function Auth() {
  const [isLogin, setIsLogin] = useState(true);
  const [isForgotPassword, setIsForgotPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [captchaToken, setCaptchaToken] = useState('');
  const [captchaResetKey, setCaptchaResetKey] = useState(0);
  const [devLink, setDevLink] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, register, resendVerification, forgotPassword } = useAuth();
  const navigate = useNavigate();
  const captchaEnabled = Boolean(process.env.REACT_APP_TURNSTILE_SITE_KEY);
  const requiresCaptchaToken = captchaEnabled && !captchaToken;

  const resetCaptcha = () => {
    setCaptchaToken('');
    setCaptchaResetKey((value) => value + 1);
  };

  const handleCaptchaVerify = useCallback((token) => {
    setCaptchaToken(token);
  }, []);

  const handleCaptchaExpire = useCallback(() => {
    setCaptchaToken('');
  }, []);

  const handleCaptchaError = useCallback((errorCode) => {
    toast.error(errorCode ? `CAPTCHA error: ${errorCode}` : 'CAPTCHA verification failed.');
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (requiresCaptchaToken) {
      toast.error('Please complete the CAPTCHA before continuing.');
      return;
    }
    setLoading(true);
    setDevLink('');

    const result = isForgotPassword
      ? await forgotPassword(email, captchaToken)
      : isLogin
        ? await login(email, password, captchaToken)
        : await register(email, password, captchaToken);

    if (result.success) {
      toast.success(result.message || (isLogin ? 'Welcome back!' : 'Account created!'));
      if (result.devLink) {
        setDevLink(result.devLink);
      }
      if (isForgotPassword) {
        setIsForgotPassword(false);
        setIsLogin(true);
      } else if (result.user || isLogin) {
        navigate('/dashboard');
      } else {
        navigate(`/verify-email-sent?email=${encodeURIComponent(email)}`);
      }
    } else {
      toast.error(result.error);
      resetCaptcha();
    }
    setLoading(false);
  };

  const handleResendVerification = async () => {
    if (requiresCaptchaToken) {
      toast.error('Please complete the CAPTCHA before resending verification.');
      return;
    }
    setLoading(true);
    setDevLink('');
    const result = await resendVerification(email, captchaToken);
    if (result.success) {
      toast.success(result.message);
      if (result.devLink) {
        setDevLink(result.devLink);
      }
    } else {
      toast.error(result.error);
      resetCaptcha();
    }
    setLoading(false);
  };

  const switchMode = (nextIsLogin) => {
    setIsLogin(nextIsLogin);
    setIsForgotPassword(false);
    setDevLink('');
    resetCaptcha();
  };

  return (
    <div className="app-shell min-h-screen flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8 page-hero">
          <BrandLogo className="auth-brand-logo mx-auto mb-4" />
          <h1 className="sr-only">LandFall AI</h1>
          <p className="page-eyebrow mb-2">Command zone access</p>
          <p className="page-copy">Sign in to import, tune, and track your Commander decks.</p>
        </div>

        <div className="glass-panel p-8">
          <div className="flex mb-6 tab-strip">
            <button
              data-testid="login-tab-btn"
              onClick={() => switchMode(true)}
              className={`flex-1 py-2 tab-button transition-colors ${isLogin && !isForgotPassword ? 'tab-button-active' : ''}`}
            >
              Login
            </button>
            <button
              data-testid="register-tab-btn"
              onClick={() => switchMode(false)}
              className={`flex-1 py-2 tab-button transition-colors ${!isLogin && !isForgotPassword ? 'tab-button-active' : ''}`}
            >
              Register
            </button>
          </div>

          <form data-testid="auth-form" onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium mb-2 text-amber-100" htmlFor="email">
                <Mail className="w-4 h-4 inline mr-2" />
                Email
              </label>
              <input
                id="email"
                data-testid="email-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                placeholder="your@email.com"
                required
              />
            </div>

            {!isForgotPassword && (
              <div>
              <label className="block text-sm font-medium mb-2 text-amber-100" htmlFor="password">
                <Lock className="w-4 h-4 inline mr-2" />
                Password
              </label>
              <input
                id="password"
                data-testid="password-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="Password"
                minLength={isLogin ? undefined : 12}
                required
              />
              {!isLogin && (
                <p className="mt-2 text-xs text-amber-100/70">
                  Use at least 12 characters.
                </p>
              )}
              </div>
            )}

            {captchaEnabled && (
              <TurnstileCaptcha
                onVerify={handleCaptchaVerify}
                onExpire={handleCaptchaExpire}
                onError={handleCaptchaError}
                resetKey={captchaResetKey}
              />
            )}

            {devLink && (
              <a className="block text-sm text-emerald-200 underline break-all" href={devLink}>
                Development link
              </a>
            )}

            <button data-testid="submit-btn" type="submit" disabled={loading || requiresCaptchaToken} className="btn-primary w-full">
              {loading
                ? 'Processing...'
                : requiresCaptchaToken
                  ? 'Complete CAPTCHA'
                  : (isForgotPassword ? 'Send Reset Link' : isLogin ? 'Enter Dashboard' : 'Create Account')}
            </button>
          </form>

          <div className="mt-5 flex flex-col gap-3 text-center">
            {isLogin && !isForgotPassword && (
              <button
                type="button"
                onClick={() => {
                  setIsForgotPassword(true);
                  setDevLink('');
                  resetCaptcha();
                }}
                className="page-copy hover:text-white transition-colors"
              >
                Forgot password?
              </button>
            )}
            {!isForgotPassword && email && (
              <button
                type="button"
                onClick={handleResendVerification}
                disabled={loading}
                className="page-copy hover:text-white transition-colors"
              >
                Resend verification email
              </button>
            )}
            {isForgotPassword && (
              <button
                type="button"
                onClick={() => {
                  setIsForgotPassword(false);
                  setDevLink('');
                  resetCaptcha();
                }}
                className="page-copy hover:text-white transition-colors"
              >
                Back to login
              </button>
            )}
          </div>
        </div>

        <div className="text-center mt-6">
          <button data-testid="back-home-btn" onClick={() => navigate('/')} className="page-copy hover:text-white transition-colors">
            <ArrowLeft className="w-4 h-4 inline mr-2" />
            Back to Home
          </button>
        </div>
      </div>
    </div>
  );
}
