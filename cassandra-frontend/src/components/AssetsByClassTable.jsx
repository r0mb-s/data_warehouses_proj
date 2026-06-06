export default function AssetsByClassTable({ items }) {
  if (items.length === 0) return <div className="empty-state">No assets by class found.</div>;

  return (
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Asset Class</th>
              <th>Asset ID</th>
              <th>Symbol</th>
              <th>Region</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a, i) => (
              <tr key={`${a.asset_class}-${a.asset_id}-${i}`}>
                <td><strong>{a.asset_class}</strong></td>
                <td className="cell-mono">{a.asset_id?.slice(0, 8)}...</td>
                <td>{a.symbol}</td>
                <td>{a.region}</td>
                <td>{a.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
