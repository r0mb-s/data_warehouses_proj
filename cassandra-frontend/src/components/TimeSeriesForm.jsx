import { useState } from 'react';

const INITIAL = { asset_id: '', source_id: '', year_month: '', event_time: '', open: '', high: '', low: '', close: '', volume: '' };

export default function TimeSeriesForm({ onSubmit }) {
  const [formData, setFormData] = useState(INITIAL);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const metrics = {};
    if (formData.open) metrics.open = parseFloat(formData.open);
    if (formData.high) metrics.high = parseFloat(formData.high);
    if (formData.low) metrics.low = parseFloat(formData.low);
    if (formData.close) metrics.close = parseFloat(formData.close);
    if (formData.volume) metrics.volume = parseFloat(formData.volume);
    await onSubmit({ asset_id: formData.asset_id, source_id: formData.source_id, year_month: formData.year_month, event_time: formData.event_time, metrics });
    setFormData(INITIAL);
  };

  const set = (field) => (e) => setFormData({ ...formData, [field]: e.target.value });

  return (
    <form onSubmit={handleSubmit}>
      <div className="form-row">
        <div className="form-field"><label>Asset ID</label><input type="text" value={formData.asset_id} onChange={set('asset_id')} required /></div>
        <div className="form-field"><label>Source ID</label><input type="text" value={formData.source_id} onChange={set('source_id')} required /></div>
        <div className="form-field"><label>Year-Month</label><input type="date" value={formData.year_month} onChange={set('year_month')} required /></div>
        <div className="form-field"><label>Event Time</label><input type="datetime-local" value={formData.event_time} onChange={set('event_time')} required /></div>
      </div>
      <div className="form-row">
        <div className="form-field"><label>Open</label><input type="number" step="any" value={formData.open} onChange={set('open')} /></div>
        <div className="form-field"><label>High</label><input type="number" step="any" value={formData.high} onChange={set('high')} /></div>
        <div className="form-field"><label>Low</label><input type="number" step="any" value={formData.low} onChange={set('low')} /></div>
        <div className="form-field"><label>Close</label><input type="number" step="any" value={formData.close} onChange={set('close')} /></div>
        <div className="form-field"><label>Volume</label><input type="number" step="any" value={formData.volume} onChange={set('volume')} /></div>
        <button type="submit" className="btn-primary">Add Point</button>
      </div>
    </form>
  );
}
