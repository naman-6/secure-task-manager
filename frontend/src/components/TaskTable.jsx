import React from 'react';
import { StatusPill, PriorityPill } from './StatusPill.jsx';

function formatDate(isoString) {
  if (!isoString) return '-';
  try {
    return new Date(isoString).toLocaleString();
  } catch {
    return isoString;
  }
}

export default function TaskTable({ tasks, loading, onEdit, onDelete }) {
  if (loading) {
    return <div className="loading-banner">Loading tasks...</div>;
  }

  if (!tasks || tasks.length === 0) {
    return (
      <div className="card empty-state">
        No tasks or assets found. Create one using the form above.
      </div>
    );
  }

  return (
    <div className="card" style={{ overflowX: 'auto' }}>
      <table className="task-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Owner</th>
            <th>Asset Tag</th>
            <th>Status</th>
            <th>Priority</th>
            <th>Updated</th>
            <th style={{ textAlign: 'right' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.id}>
              <td>
                <strong>{task.title}</strong>
                {task.description && (
                  <div style={{ color: 'var(--color-text-muted)', fontSize: '0.78rem', marginTop: '0.2rem' }}>
                    {task.description.length > 120
                      ? `${task.description.slice(0, 120)}...`
                      : task.description}
                  </div>
                )}
              </td>
              <td>{task.owner}</td>
              <td>{task.asset_tag || '-'}</td>
              <td>
                <StatusPill value={task.status} />
              </td>
              <td>
                <PriorityPill value={task.priority} />
              </td>
              <td style={{ color: 'var(--color-text-muted)', fontSize: '0.78rem' }}>
                {formatDate(task.updated_at)}
              </td>
              <td>
                <div className="row-actions" style={{ justifyContent: 'flex-end' }}>
                  <button className="btn btn-secondary" onClick={() => onEdit(task)}>
                    Edit
                  </button>
                  <button className="btn btn-danger" onClick={() => onDelete(task)}>
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
