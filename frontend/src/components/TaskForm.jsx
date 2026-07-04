import React, { useEffect, useState } from 'react';

const STATUS_OPTIONS = ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'ARCHIVED'];
const PRIORITY_OPTIONS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

const EMPTY_FORM = {
  title: '',
  description: '',
  asset_tag: '',
  status: 'PENDING',
  priority: 'MEDIUM',
  owner: '',
};

export default function TaskForm({ initialTask, onSubmit, onCancel, submitting }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [validationError, setValidationError] = useState('');

  const isEditMode = Boolean(initialTask);

  useEffect(() => {
    if (initialTask) {
      setForm({
        title: initialTask.title || '',
        description: initialTask.description || '',
        asset_tag: initialTask.asset_tag || '',
        status: initialTask.status || 'PENDING',
        priority: initialTask.priority || 'MEDIUM',
        owner: initialTask.owner || '',
      });
    } else {
      setForm(EMPTY_FORM);
    }
  }, [initialTask]);

  const handleChange = (field) => (event) => {
    setForm((prev) => ({ ...prev, [field]: event.target.value }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    setValidationError('');

    if (!form.title.trim()) {
      setValidationError('Title is required.');
      return;
    }
    if (!form.owner.trim()) {
      setValidationError('Owner is required.');
      return;
    }

    onSubmit({
      ...form,
      title: form.title.trim(),
      owner: form.owner.trim(),
      description: form.description.trim() || null,
      asset_tag: form.asset_tag.trim() || null,
    });
  };

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h3 style={{ marginTop: 0 }}>{isEditMode ? 'Edit Task / Asset' : 'Create New Task / Asset'}</h3>

      {validationError && <div className="error-banner">{validationError}</div>}

      <div className="form-grid">
        <div>
          <label htmlFor="title">Title *</label>
          <input
            id="title"
            type="text"
            value={form.title}
            onChange={handleChange('title')}
            maxLength={200}
            placeholder="e.g. Patch web-server-03 kernel"
            required
          />
        </div>

        <div>
          <label htmlFor="owner">Owner *</label>
          <input
            id="owner"
            type="text"
            value={form.owner}
            onChange={handleChange('owner')}
            maxLength={150}
            placeholder="e.g. jane.doe"
            required
          />
        </div>

        <div>
          <label htmlFor="asset_tag">Asset Tag</label>
          <input
            id="asset_tag"
            type="text"
            value={form.asset_tag}
            onChange={handleChange('asset_tag')}
            maxLength={100}
            placeholder="e.g. SRV-00231"
          />
        </div>

        <div>
          <label htmlFor="status">Status</label>
          <select id="status" value={form.status} onChange={handleChange('status')}>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt.replace('_', ' ')}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="priority">Priority</label>
          <select id="priority" value={form.priority} onChange={handleChange('priority')}>
            {PRIORITY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>

        <div className="full-width">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={form.description}
            onChange={handleChange('description')}
            maxLength={5000}
            placeholder="Additional details about this task or asset..."
          />
        </div>
      </div>

      <div className="btn-row">
        {isEditMode && (
          <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </button>
        )}
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Saving...' : isEditMode ? 'Update Task' : 'Create Task'}
        </button>
      </div>
    </form>
  );
}
