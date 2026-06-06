export default function DataSourceTable({ sources, onDelete }) {
  if (sources.length === 0) return <div className="empty-state">No data sources found.</div>;

  return (
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>API URL</th>
              <th>Description</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sources.map(s => (
              <tr key={s.source_id}>
                <td className="cell-mono">{s.source_id?.slice(0, 8)}...</td>
                <td>{s.name}</td>
                <td className="cell-mono">{s.api_url}</td>
                <td>{s.description}</td>
                <td>{s.is_deleted ? <span className="badge-down">deleted</span> : <span className="badge-up">active</span>}</td>
                <td>
                  {!s.is_deleted && (
                    <button
                      className="btn-delete"
                      onClick={() => onDelete(s.source_id)}
                      title="Soft-delete this source"
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
