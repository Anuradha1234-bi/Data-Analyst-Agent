import { useState, useEffect, useCallback } from 'react';
import { fetchHealth } from '../services/api';

/**
 * Hook to manage backend health check connection state.
 */
export function useHealthCheck(pollIntervalMs = 0) {
  const [status, setStatus] = useState('checking'); // 'checking' | 'connected' | 'disconnected'
  const [healthData, setHealthData] = useState(null);
  const [lastChecked, setLastChecked] = useState(null);
  const [errorDetails, setErrorDetails] = useState(null);

  const checkHealth = useCallback(async () => {
    try {
      const data = await fetchHealth();
      if (data && data.status === 'ok') {
        setStatus('connected');
        setHealthData(data);
        setErrorDetails(null);
      } else {
        setStatus('disconnected');
        setErrorDetails({ message: 'Unexpected response from server' });
      }
    } catch (err) {
      setStatus('disconnected');
      setHealthData(null);
      setErrorDetails(err);
    } finally {
      setLastChecked(new Date());
    }
  }, []);

  useEffect(() => {
    checkHealth();

    if (pollIntervalMs > 0) {
      const intervalId = setInterval(checkHealth, pollIntervalMs);
      return () => clearInterval(intervalId);
    }
  }, [checkHealth, pollIntervalMs]);

  return {
    status,
    isConnected: status === 'connected',
    isChecking: status === 'checking',
    healthData,
    lastChecked,
    errorDetails,
    checkHealth,
  };
}
