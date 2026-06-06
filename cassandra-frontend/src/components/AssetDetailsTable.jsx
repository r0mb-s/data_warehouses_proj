import { useState } from 'react';

export default function AssetDetailsTable({ items, onDelete }) {
  const [expanded, setExpanded] = useState({});

  if (items.length === 0) return <div className="empty-state">No asset details found.</div>;

  // Build latest version per asset_id
  const latest = {};
  items.forEach(a => {
    const prev = latest[a.asset_id];
    if (!prev || new Date(a.valid_from) > new Date(prev.valid_from)) {
      latest[a.asset_id] = a;
    }
  });

  // Group all versions per asset_id (sorted newest first)
  const groups = {};
  items.forEach(a => {
    if (!groups[a.asset_id]) groups[a.asset_id] = [];
    groups[a.asset_id].push(a);
  });
  Object.values(groups).forEach(g => g.sort((a, b) => new Date(b.valid_from) - new Date(a.valid_from)));

  const toggleExpand = (asset_id) =>
    setExpanded(prev => ({ ...prev, [asset_id]: !prev[asset_id] }));

  // Render one asset: either just its latest row, or all versions if expanded
  const rows = [];
  Object.entries(groups).forEach(([asset_id, versions]) => {
    const isExpanded = expanded[asset_id];
    const latestRow = latest[asset_id];
    const hasHistory = versions.length > 1;
    const displayRows = isExpanded ? versions : [latestRow];

    displayRows.forEach((a, i) => {
      const isLatestRow = a === latestRow;
      rows.push(
        <tr key={`${a.asset_id}-${i}`} style={{ opacity: a.is_deleted ? 0.6 : 1 }}>
          <td className="cell-mono">
            {isLatestRow && hasHistory && (
              <button
                className="btn-expand"
                onClick={() => toggleExpand(asset_id)}
                title={isExpanded ? 'Collapse history' : `Show ${versions.length} versions`}
              >
                {isExpanded ? '▾' : '▸'}
              </button>
            )}
            {a.asset_id?.slice(0, 8)}...
          </td>
          <td className="cell-mono">{new Date(a.valid_from).toLocaleDateString()}</td>
          <td><strong>{a.symbol}</strong></td>
          <td>{a.asset_class}</td>
          <td>{a.region}</td>
          <td>{a.description}</td>
          <td>{a.is_deleted ? <span className="badge-down">deleted</span> : <span className="badge-up">active</span>}</td>
          <td>
            {isLatestRow && !a.is_deleted && (
              <button
                className="btn-delete"
                onClick={() => onDelete(a.asset_id)}
                title="Soft-delete this asset"
              >
                Delete
              </button>
            )}
          </td>
        </tr>
      );
    });
  });

  return (
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Asset ID</th>
              <th>Valid From</th>
              <th>Symbol</th>
              <th>Class</th>
              <th>Region</th>
              <th>Description</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>
  );
}
