import { useState, useEffect } from 'react';
import { ingestApi, sourcesApi } from '../services/api';

const INTERVALS_BINANCE = [
  { value: '1m', label: '1 Minute' },
  { value: '5m', label: '5 Minutes' },
  { value: '15m', label: '15 Minutes' },
  { value: '1h', label: '1 Hour' },
  { value: '4h', label: '4 Hours' },
  { value: '1d', label: '1 Day' },
  { value: '1w', label: '1 Week' },
  { value: '1M', label: '1 Month' },
];

const INTERVALS_YAHOO = [
  { value: '1d', label: '1 Day' },
  { value: '1wk', label: '1 Week' },
  { value: '1mo', label: '1 Month' },
  { value: '1h', label: '1 Hour' },
  { value: '5m', label: '5 Minutes' },
];

const PROVIDERS = [
  { value: 'binance', label: 'Binance (crypto)', hint: 'e.g. BTCUSDT, ETHUSDT' },
  { value: 'yahoo',   label: 'Yahoo Finance (stocks/forex/ETFs)', hint: 'e.g. AAPL, EURUSD=X, GC=F' },
];

const INITIAL = { symbol: '', source_id: '', interval: '1d', asset_class: 'crypto', region: 'global', description: '', provider: 'binance' };

export default function IngestPage() {
  const [formData, setFormData] = useState(INITIAL);
  const [sources, setSources] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => { sourcesApi.getAll().then(setSources).catch(() => {}); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError(null); setResult(null);
    try {
      setResult(await ingestApi.run(formData));
    } catch (err) {
      setError(err.message || 'Ingestion failed.');
    } finally {
      setLoading(false);
    }
  };

  const set = (field) => (e) => setFormData({ ...formData, [field]: e.target.value });
  const setProvider = (e) => {
    const provider = e.target.value;
    const defaultClass = provider === 'yahoo' ? 'stock' : 'crypto';
    setFormData({ ...formData, provider, asset_class: defaultClass, interval: '1d' });
  };

  const intervals = formData.provider === 'yahoo' ? INTERVALS_YAHOO : INTERVALS_BINANCE;
  const hint = PROVIDERS.find(p => p.value === formData.provider)?.hint || '';

  return (
    <div>
      <p className="page-desc">
        Fetch candlestick data from a financial data provider and load it into the warehouse.
        Supports Binance (crypto) and Yahoo Finance (stocks, forex, ETFs, commodities).
      </p>

      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <div className="form-field">
            <label>Provider</label>
            <select value={formData.provider} onChange={setProvider}>
              {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </div>
          <div className="form-field">
            <label>Symbol</label>
            <input type="text" placeholder={hint} value={formData.symbol} onChange={set('symbol')} required />
          </div>
          <div className="form-field">
            <label>Source</label>
            <select value={formData.source_id} onChange={set('source_id')} required>
              <option value="">-- select source --</option>
              {sources.map((s) => <option key={s.source_id} value={s.source_id}>{s.name || s.source_id}</option>)}
            </select>
          </div>
          <div className="form-field">
            <label>Interval</label>
            <select value={formData.interval} onChange={set('interval')}>
              {intervals.map((i) => <option key={i.value} value={i.value}>{i.label}</option>)}
            </select>
          </div>
        </div>
        <div className="form-row">
          <div className="form-field">
            <label>Asset Class</label>
            <input type="text" value={formData.asset_class} onChange={set('asset_class')} />
          </div>
          <div className="form-field">
            <label>Region</label>
            <input type="text" value={formData.region} onChange={set('region')} />
          </div>
          <div className="form-field">
            <label>Description</label>
            <input type="text" placeholder="Optional" value={formData.description} onChange={set('description')} />
          </div>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Ingesting...' : 'Run Ingestion'}
          </button>
        </div>
      </form>

      {error && <div className="error-banner">{error}</div>}

      {result && (
        <div className="card">
          <div className="card-title">Ingestion Complete</div>
          <table className="kv-table">
            <tbody>
              <tr><td className="kv-label">Asset ID</td><td className="kv-value">{result.asset_id}</td></tr>
              <tr><td className="kv-label">Symbol</td><td className="kv-value">{result.symbol}</td></tr>
              <tr><td className="kv-label">Provider</td><td className="kv-value">{formData.provider}</td></tr>
              <tr><td className="kv-label">Fetched</td><td className="kv-value">{result.fetched}</td></tr>
              <tr><td className="kv-label">Transformed</td><td className="kv-value">{result.transformed}</td></tr>
              <tr><td className="kv-label">Stored</td><td className="kv-value">{result.stored}</td></tr>
              <tr><td className="kv-label">Skipped</td><td className="kv-value">{result.skipped}</td></tr>
              <tr><td className="kv-label">Failures</td><td className="kv-value">{result.failures}</td></tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
