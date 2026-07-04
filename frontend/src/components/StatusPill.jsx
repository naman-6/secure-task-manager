import React from 'react';

export function StatusPill({ value }) {
  const normalized = String(value || '').toLowerCase();
  return <span className={`pill pill-${normalized}`}>{normalized.replace('_', ' ')}</span>;
}

export function PriorityPill({ value }) {
  const normalized = String(value || '').toLowerCase();
  return <span className={`pill pill-${normalized}`}>{normalized}</span>;
}

export default StatusPill;
