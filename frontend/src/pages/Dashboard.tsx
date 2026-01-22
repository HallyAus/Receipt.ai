import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getAccounts, getReceiptStats, syncAllAccounts } from '../services/api';
import { useState } from 'react';

export default function Dashboard() {
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const { data: accounts, isLoading: accountsLoading } = useQuery({
    queryKey: ['accounts'],
    queryFn: getAccounts,
  });

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['receipt-stats'],
    queryFn: () => getReceiptStats(),
  });

  const handleSyncAll = async () => {
    setSyncing(true);
    setSyncMessage(null);
    try {
      const result = await syncAllAccounts();
      setSyncMessage(result.message);
    } catch (error) {
      setSyncMessage('Failed to start sync');
    } finally {
      setSyncing(false);
    }
  };

  if (accountsLoading || statsLoading) {
    return (
      <div className="page">
        <div className="loading">
          <div className="spinner"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <button
          className="btn btn-primary"
          onClick={handleSyncAll}
          disabled={syncing || !accounts?.total}
        >
          {syncing ? 'Starting...' : 'Sync All Accounts'}
        </button>
      </div>

      {syncMessage && (
        <div className="alert alert-info">{syncMessage}</div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-4">
        <div className="card stat-card">
          <div className="stat-value">{accounts?.total || 0}</div>
          <div className="stat-label">Connected Accounts</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">{stats?.total_count || 0}</div>
          <div className="stat-label">Total Receipts</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">
            ${(stats?.total_amount || 0).toLocaleString('en-US', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </div>
          <div className="stat-label">Total Amount</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">
            {Object.keys(stats?.by_category || {}).length}
          </div>
          <div className="stat-label">Categories</div>
        </div>
      </div>

      {/* Quick Links */}
      <div className="grid grid-2" style={{ marginTop: '1rem' }}>
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Connected Accounts</h3>
            <Link to="/accounts" className="btn btn-sm btn-secondary">
              Manage
            </Link>
          </div>
          {accounts?.accounts.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state-title">No accounts connected</p>
              <p>Connect Gmail or Microsoft 365 to start extracting receipts</p>
              <Link to="/accounts" className="btn btn-primary" style={{ marginTop: '1rem' }}>
                Connect Account
              </Link>
            </div>
          ) : (
            <div>
              {accounts?.accounts.slice(0, 3).map((account) => (
                <div key={account.id} className="account-card" style={{ marginBottom: '0.75rem' }}>
                  <div className={`account-icon ${account.provider}`}>
                    {account.provider === 'gmail' ? 'G' : 'M'}
                  </div>
                  <div className="account-info">
                    <div className="account-email">{account.email}</div>
                    <div className="account-provider">
                      {account.provider === 'gmail' ? 'Gmail' : 'Microsoft 365'}
                    </div>
                  </div>
                  {account.sync_error ? (
                    <span className="badge badge-danger">Error</span>
                  ) : account.last_sync_at ? (
                    <span className="badge badge-success">Synced</span>
                  ) : (
                    <span className="badge badge-warning">Pending</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="card-title">By Category</h3>
            <Link to="/receipts" className="btn btn-sm btn-secondary">
              View All
            </Link>
          </div>
          {Object.keys(stats?.by_category || {}).length === 0 ? (
            <div className="empty-state">
              <p>No receipts yet</p>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Count</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(stats?.by_category || {}).map(([category, data]) => (
                  <tr key={category}>
                    <td style={{ textTransform: 'capitalize' }}>{category}</td>
                    <td>{data.count}</td>
                    <td>${data.amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
