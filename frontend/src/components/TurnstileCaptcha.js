import { useEffect, useRef } from 'react';

const TURNSTILE_SCRIPT_ID = 'turnstile-script';

export default function TurnstileCaptcha({ onVerify, onExpire, resetKey }) {
  const containerRef = useRef(null);
  const widgetRef = useRef(null);
  const siteKey = process.env.REACT_APP_TURNSTILE_SITE_KEY;

  useEffect(() => {
    if (!siteKey) return undefined;

    let cancelled = false;

    const renderWidget = () => {
      if (cancelled || !window.turnstile || !containerRef.current) return;
      if (widgetRef.current) {
        window.turnstile.remove(widgetRef.current);
      }
      widgetRef.current = window.turnstile.render(containerRef.current, {
        sitekey: siteKey,
        callback: onVerify,
        'expired-callback': onExpire,
        'error-callback': onExpire,
        theme: 'dark',
      });
    };

    if (window.turnstile) {
      renderWidget();
    } else {
      const existingScript = document.getElementById(TURNSTILE_SCRIPT_ID);
      if (existingScript) {
        existingScript.addEventListener('load', renderWidget, { once: true });
      } else {
        const script = document.createElement('script');
        script.id = TURNSTILE_SCRIPT_ID;
        script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
        script.async = true;
        script.defer = true;
        script.addEventListener('load', renderWidget, { once: true });
        document.body.appendChild(script);
      }
    }

    return () => {
      cancelled = true;
      if (window.turnstile && widgetRef.current) {
        window.turnstile.remove(widgetRef.current);
        widgetRef.current = null;
      }
    };
  }, [siteKey, onVerify, onExpire, resetKey]);

  if (!siteKey) return null;

  return (
    <div className="flex justify-center">
      <div ref={containerRef} />
    </div>
  );
}
