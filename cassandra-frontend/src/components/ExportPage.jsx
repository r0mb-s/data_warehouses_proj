import { useState, useEffect } from 'react';
import { exportApi, assetsApi } from '../services/api';

const FORMATS = [
  { value: 'jsonl', label: 'JSON Lines (.jsonl)' },
  { value: 'csv', label: 'CSV (.csv)' },
];

export default function ExportPage() {
  const [assets, setAssets] = useState([]);
  const [assetId, setAssetId] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [format, setFormat] = useState('jsonl');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [preview, setPreview] = useState(null);

  useEffect(() => { assetsApi.getAll().then(all => {
    const latest = {};
    all.forEach(a => {
      const prev = latest[a.asset_id];
      if (!prev || new Date(a.valid_from) > new Date(prev.valid_from)) latest[a.asset_id] = a;
    });
    setAssets(Object.values(latest).filter(a => !a.is_deleted));
  }).catch(() => {}); }, []);

  const opts = assets.map((a) => ({ id: a.asset_id, src: a.source_id, label: `${a.symbol || '?'} (${a.asset_id.slice(0, 8)}...)` }));

  const handleExport = async (download) => {
    if (!assetId || !sourceId) return;
    setLoading(true); setError(null); setPreview(null);
    try {
      const res = await exportApi.download({ asset_id: assetId, source_id: sourceId, format });
      const blob = await res.blob();
      if (download) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `export_${assetId.slice(0, 8)}.${format === 'csv' ? 'csv' : 'jsonl'}`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        setPreview((await blob.text()).slice(0, 5000));
      }
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const sparkCode = format === 'jsonl'
    ? `# PySpark\ndf = spark.read.json("export.jsonl")\ndf.show()\ndf.describe().show()`
    : `# PySpark\ndf = spark.read.csv("export.csv", header=True, inferSchema=True)\ndf.show()\ndf.describe().show()`;

  return (
    <div>
      <p className="page-desc">
        Export time-series data in formats compatible with Apache Spark and other ML/analytics tools.
        Metrics are flattened into top-level columns for direct DataFrame consumption.
      </p>

      <div className="form-row">
        <div className="form-field">
          <label>Asset</label>
          <select value={assetId} onChange={(e) => { const s = assets.find(a => a.asset_id === e.target.value); setAssetId(e.target.value); if (s) setSourceId(s.source_id); }}>
            <option value="">-- select --</option>
            {opts.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label>Format</label>
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            {FORMATS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </div>
        <button onClick={() => handleExport(false)} disabled={!assetId || loading}>
          {loading ? 'Loading...' : 'Preview'}
        </button>
        <button className="btn-primary" onClick={() => handleExport(true)} disabled={!assetId || loading}>
          {loading ? 'Exporting...' : 'Download'}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {preview && (
        <div className="card">
          <div className="card-title">Preview (first 5000 chars)</div>
          <pre className="code-block">{preview}</pre>
        </div>
      )}

      <div className="card">
        <div className="card-title">Spark Integration</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: '0 0 0.75rem 0' }}>
          Load the exported file directly into a Spark DataFrame:
        </p>
        <pre className="code-block">{sparkCode}</pre>
      </div>
    </div>
  );
}
