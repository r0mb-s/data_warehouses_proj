import { useState } from 'react';

const INITIAL = { asset_id: '', asset_class: '', description: '', region: '', source_id: '', symbol: '' };

export default function AssetDetailsForm({ onSubmit }) {
  const [formData, setFormData] = useState(INITIAL);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = { ...formData };
    if (!payload.asset_id) delete payload.asset_id;
    if (!payload.source_id) delete payload.source_id;
    await onSubmit(payload);
    setFormData(INITIAL);
  };

  const set = (field) => (e) => setFormData({ ...formData, [field]: e.target.value });

  return (
    <form onSubmit={handleSubmit}>
      <div className="form-row">
        <div className="form-field"><label>Symbol</label><input type="text" placeholder="BTCUSDT" value={formData.symbol} onChange={set('symbol')} required /></div>
        <div className="form-field"><label>Asset Class</label><input type="text" placeholder="crypto" value={formData.asset_class} onChange={set('asset_class')} /></div>
        <div className="form-field"><label>Region</label><input type="text" placeholder="global" value={formData.region} onChange={set('region')} /></div>
        <div className="form-field"><label>Description</label><input type="text" placeholder="Optional" value={formData.description} onChange={set('description')} /></div>
        <button type="submit" className="btn-primary">Add Asset</button>
      </div>
    </form>
  );
}
