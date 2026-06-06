import { useState } from 'react';

export default function DataSourceForm({ onSubmit }) {
  const [formData, setFormData] = useState({ name: '', api_url: '', description: '' });

  const handleSubmit = async (e) => {
    e.preventDefault();
    await onSubmit(formData);
    setFormData({ name: '', api_url: '', description: '' });
  };

  const set = (field) => (e) => setFormData({ ...formData, [field]: e.target.value });

  return (
    <form onSubmit={handleSubmit}>
      <div className="form-row">
        <div className="form-field">
          <label>Name</label>
          <input type="text" placeholder="e.g. Binance" value={formData.name} onChange={set('name')} required />
        </div>
        <div className="form-field">
          <label>API URL</label>
          <input type="text" placeholder="https://..." value={formData.api_url} onChange={set('api_url')} />
        </div>
        <div className="form-field">
          <label>Description</label>
          <input type="text" placeholder="Optional" value={formData.description} onChange={set('description')} />
        </div>
        <button type="submit" className="btn-primary">Add Source</button>
      </div>
    </form>
  );
}
