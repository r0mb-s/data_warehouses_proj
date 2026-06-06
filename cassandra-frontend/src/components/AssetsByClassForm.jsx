import { useState } from 'react';

const INITIAL = { asset_class: '', asset_id: '', description: '', region: '', symbol: '' };

export default function AssetsByClassForm({ onSubmit }) {
  const [formData, setFormData] = useState(INITIAL);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = { ...formData };
    if (!payload.asset_id) delete payload.asset_id;
    await onSubmit(payload);
    setFormData(INITIAL);
  };

  const set = (field) => (e) => setFormData({ ...formData, [field]: e.target.value });

  return (
    <form onSubmit={handleSubmit}>
      <div className="form-row">
        <div className="form-field"><label>Asset Class</label><input type="text" placeholder="crypto" value={formData.asset_class} onChange={set('asset_class')} required /></div>
        <div className="form-field"><label>Symbol</label><input type="text" placeholder="BTCUSDT" value={formData.symbol} onChange={set('symbol')} /></div>
        <div className="form-field"><label>Region</label><input type="text" placeholder="global" value={formData.region} onChange={set('region')} /></div>
        <div className="form-field"><label>Description</label><input type="text" placeholder="Optional" value={formData.description} onChange={set('description')} /></div>
        <button type="submit" className="btn-primary">Add Entry</button>
      </div>
    </form>
  );
}
