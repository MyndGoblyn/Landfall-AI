import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, MailCheck } from 'lucide-react';
import ForestManaIcon from '../components/ForestManaIcon';

export default function VerifyEmailSent() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const email = searchParams.get('email');

  return (
    <div className="app-shell min-h-screen flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-lg">
        <div className="glass-panel p-8 text-center">
          <ForestManaIcon className="w-14 h-14 mx-auto mb-5" />
          <MailCheck className="w-12 h-12 mx-auto mb-4 text-emerald-300" />
          <p className="page-eyebrow mb-2">Verification sent</p>
          <h1 className="text-3xl font-bold mb-3 brand-title">Check Your Email</h1>
          <p className="page-copy">
            We sent a verification link{email ? ` to ${email}` : ''}. Open that link to finish creating your account.
          </p>
          <p className="mt-4 text-sm text-amber-100/70">
            If it does not arrive soon, check spam or return to login and resend the verification email.
          </p>
          <button className="btn-primary mt-7 w-full" onClick={() => navigate('/auth')}>
            Back to Login
          </button>
        </div>

        <div className="text-center mt-6">
          <button onClick={() => navigate('/')} className="page-copy hover:text-white transition-colors">
            <ArrowLeft className="w-4 h-4 inline mr-2" />
            Back to Home
          </button>
        </div>
      </div>
    </div>
  );
}
