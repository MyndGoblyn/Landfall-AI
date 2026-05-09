import { useEffect, useState } from 'react';

export default function useRotatingStatus(active, messages = [], intervalMs = 2200) {
  const [index, setIndex] = useState(0);
  const messageCount = messages.length;

  useEffect(() => {
    if (!active || messageCount === 0) {
      setIndex(0);
      return undefined;
    }

    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % messageCount);
    }, intervalMs);

    return () => window.clearInterval(timer);
  }, [active, intervalMs, messageCount]);

  return messages[index] || messages[0] || '';
}
