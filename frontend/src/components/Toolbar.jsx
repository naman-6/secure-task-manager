import React from 'react';

const STATUS_OPTIONS = ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'ARCHIVED'];
const PRIORITY_OPTIONS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

export default function Toolbar({ filters, onFilterChange, onRefresh }) {
  return (
    <div className="toolbar">
      <input
        type="text"
        placeholder="Search by title..."
        value={filters.search}
        onChange={(e) => onFilterChange({ ...filters, search: e.target.value })}
      />

      <select
        value={filters.status}
        onChange={(e) => onFilterChange({ ...filters, status: e.target.value })}
      >
        <option value="">All statuses</option>
        {STATUS_OPTIONS.map((opt) => (
          <option key={opt} value={opt}>
            {opt.replace('_', ' ')}
          </option>
        ))}
      </select>

      <select
        value={filters.priority}
        onChange={(e) => onFilterChange({ ...filters, priority: e.target.value })}
      >
        <option value="">All priorities</option>
        {PRIORITY_OPTIONS.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>

      <button className="btn btn-secondary" onClick={onRefresh} type="button">
        Refresh
      </button>
    </div>
  );
}
