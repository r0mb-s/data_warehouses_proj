import { useState, useEffect } from 'react';
import { analyticsApi, assetsApi } from '../services/api';

const METRICS = ['close', 'open', 'high', 'low', 'volume'];

function KV({ label, value }) {
  return <tr><td className="kv-label">{label}</td><td className="kv-value">{value}</td></tr>;
}

function AggTable({ data }) {
  if (!data) return null;
  return (
    <table className="kv-table">
      <tbody>
        <KV label="Count" value={data.count} />
        <KV label="Min" value={data.min?.toFixed(4)} />
        <KV label="Max" value={data.max?.toFixed(4)} />
        <KV label="Mean" value={data.mean?.toFixed(4)} />
        <KV label="Sum" value={data.sum?.toFixed(2)} />
        <KV label="Std Dev" value={data.stddev?.toFixed(6)} />
      </tbody>
    </table>
  );
}

export default function AnalyticsPage() {
  const [assets, setAssets] = useState([]);
  const [assetId, setAssetId] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [metric, setMetric] = useState('close');
  const [periods, setPeriods] = useState(7);

  const [agg, setAgg] = useState(null);
  const [trend, setTrend] = useState(null);
  const [fc, setFc] = useState(null);
  const [risk, setRisk] = useState(null);

  const [cmpId, setCmpId] = useState('');
  const [cmpSrc, setCmpSrc] = useState('');
  const [cmpResult, setCmpResult] = useState(null);

  const [loading, setLoading] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => { assetsApi.getAll().then(all => {
    const latest = {};
    all.forEach(a => {
      const prev = latest[a.asset_id];
      if (!prev || new Date(a.valid_from) > new Date(prev.valid_from)) latest[a.asset_id] = a;
    });
    setAssets(Object.values(latest).filter(a => !a.is_deleted));
  }).catch(() => {}); }, []);

  const base = { asset_id: assetId, source_id: sourceId, metric };

  const opts = assets.map((a) => ({ id: a.asset_id, src: a.source_id, label: `${a.symbol || '?'} (${a.asset_id.slice(0, 8)}...)` }));

  const runAll = async () => {
    if (!assetId || !sourceId) return;
    setError(null); setLoading('all');
    try {
      const [a, t, f, r] = await Promise.all([
        analyticsApi.aggregate(base),
        analyticsApi.trend(base),
        analyticsApi.forecast({ ...base, periods }),
        analyticsApi.risk(base),
      ]);
      setAgg(a); setTrend(t); setFc(f); setRisk(r);
    } catch (err) { setError(err.message); }
    finally { setLoading(''); }
  };

  const runCompare = async () => {
    if (!assetId || !cmpId) return;
    setError(null); setLoading('cmp');
    try {
      setCmpResult(await analyticsApi.compare({
        asset_a_id: assetId, asset_a_source_id: sourceId,
        asset_b_id: cmpId, asset_b_source_id: cmpSrc, metric,
      }));
    } catch (err) { setError(err.message); }
    finally { setLoading(''); }
  };

  const dirBadge = (d) => d === 'up' ? 'badge badge-up' : d === 'down' ? 'badge badge-down' : 'badge badge-flat';
  const dirLabel = (d) => d === 'up' ? 'Upward' : d === 'down' ? 'Downward' : 'Flat';

  return (
    <div>
      <p className="page-desc">
        Select an ingested asset to run aggregations, trend detection, forecasting, and risk analysis.
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
          <label>Metric</label>
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            {METRICS.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label>Forecast Periods</label>
          <input type="number" min="1" max="365" value={periods} onChange={(e) => setPeriods(parseInt(e.target.value) || 1)} />
        </div>
        <button className="btn-primary" onClick={runAll} disabled={!assetId || !!loading}>
          {loading === 'all' ? 'Analyzing...' : 'Run All Analytics'}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {/* Results grid */}
      <div className="card-grid">
        {agg && (
          <div className="card">
            <div className="card-title">Aggregations</div>
            <AggTable data={agg} />
          </div>
        )}

        {trend && (
          <div className="card">
            <div className="card-title">Trend</div>
            <table className="kv-table">
              <tbody>
                <KV label="Direction" value={<span className={dirBadge(trend.direction)}>{dirLabel(trend.direction)}</span>} />
                <KV label="Change" value={`${trend.pct_change >= 0 ? '+' : ''}${trend.pct_change?.toFixed(2)}%`} />
                <KV label="Start" value={trend.start_value?.toFixed(4)} />
                <KV label="End" value={trend.end_value?.toFixed(4)} />
              </tbody>
            </table>
          </div>
        )}

        {risk && (
          <div className="card">
            <div className="card-title">Risk Signals</div>
            <table className="kv-table">
              <tbody>
                <KV label="Volatility" value={risk.volatility?.toFixed(6)} />
                <KV label="Max Drawdown" value={`${risk.max_drawdown_pct?.toFixed(2)}%`} />
                <KV label="Avg Return" value={`${risk.avg_daily_return_pct?.toFixed(4)}%`} />
                <KV label="Sharpe" value={risk.sharpe_approx?.toFixed(4)} />
              </tbody>
            </table>
          </div>
        )}

        {fc && fc.predictions?.length > 0 && (
          <div className="card">
            <div className="card-title">Forecast ({fc.predictions.length} periods)</div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>#</th><th>Date</th><th>Value</th></tr></thead>
                <tbody>
                  {fc.predictions.map(p => (
                    <tr key={p.period}>
                      <td>{p.period}</td>
                      <td className="cell-mono">{new Date(p.event_time).toLocaleDateString()}</td>
                      <td className="cell-number">{p.predicted_value?.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Comparison */}
      <div className="card">
        <div className="card-title">Compare Two Assets</div>
        <div className="form-row">
          <div className="form-field">
            <label>Asset B</label>
            <select value={cmpId} onChange={(e) => { const s = assets.find(a => a.asset_id === e.target.value); setCmpId(e.target.value); if (s) setCmpSrc(s.source_id); }}>
              <option value="">-- select --</option>
              {opts.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
            </select>
          </div>
          <button onClick={runCompare} disabled={!assetId || !cmpId || !!loading}>
            {loading === 'cmp' ? 'Comparing...' : 'Compare'}
          </button>
        </div>

        {cmpResult && (
          <div className="card-grid">
            <div>
              <div className="card-title">Asset A</div>
              <AggTable data={cmpResult.asset_a} />
            </div>
            <div>
              <div className="card-title">Asset B</div>
              <AggTable data={cmpResult.asset_b} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
