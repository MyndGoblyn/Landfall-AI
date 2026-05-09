import { useEffect, useState } from 'react';

export default function useRotatingStatus(active, messages, intervalMs = 2200) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!active) {
      setIndex(0);
      return undefined;
    }

    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % messages.length);
    }, intervalMs);

    return () => window.clearInterval(timer);
  }, [active, intervalMs, messages.length]);

  return messages[index] || messages[0] || '';
}
