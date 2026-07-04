import React, { useCallback, useEffect, useState } from 'react';
import { TaskAPI } from './api.js';
import TaskForm from './components/TaskForm.jsx';
import TaskTable from './components/TaskTable.jsx';
import Toolbar from './components/Toolbar.jsx';

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [editingTask, setEditingTask] = useState(null);
  const [filters, setFilters] = useState({ search: '', status: '', priority: '' });

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = {
        search: filters.search || undefined,
        status: filters.status || undefined,
        priority: filters.priority || undefined,
      };
      const data = await TaskAPI.list(params);
      setTasks(data || []);
    } catch (err) {
      setError(err.message || 'Failed to load tasks.');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    const debounceHandle = setTimeout(() => {
      fetchTasks();
    }, 250);
    return () => clearTimeout(debounceHandle);
  }, [fetchTasks]);

  const handleCreateOrUpdate = async (payload) => {
    setSubmitting(true);
    setError('');
    try {
      if (editingTask) {
        await TaskAPI.update(editingTask.id, payload);
      } else {
        await TaskAPI.create(payload);
      }
      setEditingTask(null);
      await fetchTasks();
    } catch (err) {
      setError(err.message || 'Failed to save task.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (task) => {
    const confirmed = window.confirm(`Delete "${task.title}"? This cannot be undone.`);
    if (!confirmed) return;

    setError('');
    try {
      await TaskAPI.remove(task.id);
      if (editingTask && editingTask.id === task.id) {
        setEditingTask(null);
      }
      await fetchTasks();
    } catch (err) {
      setError(err.message || 'Failed to delete task.');
    }
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Secure Task &amp; Asset Manager</h1>
          <div className="subtitle">React (Vite) + FastAPI + PostgreSQL — on-prem Kubernetes</div>
        </div>
        <span className="badge-env">3-Tier / Bare-Metal K8s</span>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <TaskForm
        key={editingTask ? editingTask.id : 'new'}
        initialTask={editingTask}
        onSubmit={handleCreateOrUpdate}
        onCancel={() => setEditingTask(null)}
        submitting={submitting}
      />

      <Toolbar filters={filters} onFilterChange={setFilters} onRefresh={fetchTasks} />

      <TaskTable
        tasks={tasks}
        loading={loading}
        onEdit={(task) => setEditingTask(task)}
        onDelete={handleDelete}
      />
    </div>
  );
}
