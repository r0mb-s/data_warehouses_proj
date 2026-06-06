export default function TimeSeriesTable({ items }) {
  if (items.length === 0) return <div className="empty-state">No time series data found.</div>;

  return (
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Asset ID</th>
              <th>Event Time</th>
              <th>Open</th>
              <th>High</th>
              <th>Low</th>
              <th>Close</th>
              <th>Volume</th>
            </tr>
          </thead>
          <tbody>
            {items.map((t, i) => (
              <tr key={`${t.asset_id}-${t.event_time}-${i}`}>
                <td className="cell-mono">{t.asset_id?.slice(0, 8)}...</td>
                <td className="cell-mono">{new Date(t.event_time).toLocaleDateString()}</td>
                <td className="cell-number">{t.metrics?.open?.toFixed(2)}</td>
                <td className="cell-number">{t.metrics?.high?.toFixed(2)}</td>
                <td className="cell-number">{t.metrics?.low?.toFixed(2)}</td>
                <td className="cell-number">{t.metrics?.close?.toFixed(2)}</td>
                <td className="cell-number">{t.metrics?.volume?.toFixed(0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
