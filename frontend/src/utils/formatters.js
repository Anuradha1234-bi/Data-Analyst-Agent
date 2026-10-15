/**
 * Formatting utilities for AI Data Analyst Agent.
 */

export function formatTimestamp(date) {
  if (!date) return 'Never';
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
