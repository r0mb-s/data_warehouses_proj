import { useState, useEffect, useCallback } from 'react';
import { sourcesApi, assetsApi, assetsByClassApi, timeSeriesApi } from './services/api';
import DataSourceForm from './components/DataSourceForm';
import DataSourceTable from './components/DataSourceTable';
import AssetDetailsForm from './components/AssetDetailsForm';
import AssetDetailsTable from './components/AssetDetailsTable';
import AssetsByClassForm from './components/AssetsByClassForm';
import AssetsByClassTable from './components/AssetsByClassTable';
import TimeSeriesForm from './components/TimeSeriesForm';
import TimeSeriesTable from './components/TimeSeriesTable';
import IngestPage from './components/IngestPage';
import AnalyticsPage from './components/AnalyticsPage';
import ExportPage from './components/ExportPage';
import AssistantPage from './components/AssistantPage';

const TABS = [
  { key: 'ingest',       label: 'Ingest',         icon: '\u2B07' },
  { key: 'analytics',    label: 'Analytics',       icon: '\u2728' },
  { key: 'export',       label: 'Export',          icon: '\u2197' },
  { key: 'assistant',    label: 'Assistant',       icon: '\u25CE' },
  { key: 'sources',      label: 'Sources',         icon: '\u26A1' },
  { key: 'assets',       label: 'Assets',          icon: '\u25C6' },
  { key: 'assetsByClass',label: 'By Class',        icon: '\u2630' },
  { key: 'timeSeries',   label: 'Time Series',     icon: '\u2593' },
];

function App() {
  const [activeTab, setActiveTab] = useState('ingest');
  const [data, setData] = useState({ sources: [], assets: [], assetsByClass: [], timeSeries: [] });
  const [error, setError] = useState(null);
  const [assistantMessages, setAssistantMessages] = useState([]);
  const [assistantHistory, setAssistantHistory] = useState([]);
  const [theme, setTheme] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('theme') || 'dark';
    }
    return 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const loaders = {
    sources: sourcesApi.getAll,
    assets: assetsApi.getAll,
    assetsByClass: assetsByClassApi.getAll,
    timeSeries: timeSeriesApi.getAll,
  };

  const loadTab = useCallback(async (tab) => {
    if (!loaders[tab]) return;
    try {
      const result = await loaders[tab]();
      setData((prev) => ({ ...prev, [tab]: result }));
      setError(null);
    } catch (err) {
      console.error(err);
      setError(`Failed to load ${tab}.`);
    }
  }, []);

  useEffect(() => { loadTab(activeTab); }, [activeTab, loadTab]);

  const handleCreate = async (tab, apiCreate, formData) => {
    try {
      await apiCreate(formData);
      await loadTab(tab);
      setError(null);
    } catch (err) {
      console.error(err);
      setError(`Failed to create record in ${tab}.`);
    }
  };

  const handleDelete = async (tab, apiDelete, id) => {
    try {
      await apiDelete(id);
      await loadTab(tab);
      setError(null);
    } catch (err) {
      console.error(err);
      setError(`Failed to delete record in ${tab}.`);
    }
  };

  const pageTitle = TABS.find(t => t.key === activeTab)?.label || '';

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>DataWarehouse</h1>
          <div className="subtitle">Stock Analytics Platform</div>
        </div>

        <nav className="sidebar-nav">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={activeTab === t.key ? 'active' : ''}
              onClick={() => setActiveTab(t.key)}
            >
              <span className="nav-icon">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button className="theme-toggle" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
            <span>{theme === 'dark' ? '\u2600' : '\u263E'}</span>
            {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="main-content">
        <h2 className="page-title">{pageTitle}</h2>

        {error && <div className="error-banner">{error}</div>}

        {activeTab === 'ingest' && <IngestPage />}
        {activeTab === 'analytics' && <AnalyticsPage />}
        {activeTab === 'export' && <ExportPage />}
        {activeTab === 'assistant' && (
          <AssistantPage
            messages={assistantMessages}
            setMessages={setAssistantMessages}
            history={assistantHistory}
            setHistory={setAssistantHistory}
          />
        )}

        {activeTab === 'sources' && (
          <>
            <DataSourceForm onSubmit={(d) => handleCreate('sources', sourcesApi.create, d)} />
            <DataSourceTable sources={data.sources} onDelete={(id) => handleDelete('sources', sourcesApi.delete, id)} />
          </>
        )}

        {activeTab === 'assets' && (
          <>
            <AssetDetailsForm onSubmit={(d) => handleCreate('assets', assetsApi.create, d)} />
            <AssetDetailsTable items={data.assets} onDelete={(id) => handleDelete('assets', assetsApi.delete, id)} />
          </>
        )}

        {activeTab === 'assetsByClass' && (
          <>
            <AssetsByClassForm onSubmit={(d) => handleCreate('assetsByClass', assetsByClassApi.create, d)} />
            <AssetsByClassTable items={data.assetsByClass} />
          </>
        )}

        {activeTab === 'timeSeries' && (
          <>
            <TimeSeriesForm onSubmit={(d) => handleCreate('timeSeries', timeSeriesApi.create, d)} />
            <TimeSeriesTable items={data.timeSeries} />
          </>
        )}
      </main>
    </div>
  );
}

export default App;
