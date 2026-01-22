import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import {
  getAccounts,
  getAuthStatus,
  deleteAccount,
  startSync,
  getSyncStatus,
  getAccountStats,
} from '../services/api';
import type { Account, SyncStatusResponse } from '../types';

export default function Accounts() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [alert, setAlert] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [syncTasks, setSyncTasks] = useState<Record<number, string>>({});
  const [syncStatuses, setSyncStatuses] = useState<Record<number, SyncStatusResponse>>({});

  const { data: authStatus, isLoading: authLoading } = useQuery({
    queryKey: ['auth-status'],
    queryFn: getAuthStatus,
  });

  const { data: accounts, isLoading: accountsLoading } = useQuery({
    queryKey: ['accounts'],
    queryFn: getAccounts,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      setAlert({ type: 'success', message: 'Account disconnected successfully' });
    },
    onError: () => {
      setAlert({ type: 'error', message: 'Failed to disconnect account' });
    },
  });

  // Handle OAuth callback alerts
  useEffect(() => {
    const success = searchParams.get('success');
    const error = searchParams.get('error');

    if (success) {
      setAlert({
        type: 'success',
        message: `Successfully connected ${success === 'gmail' ? 'Gmail' : 'Microsoft 365'} account!`,
      });
    } else if (error) {
      setAlert({ type: 'error', message: `OAuth error: ${error}` });
    }
  }, [searchParams]);

  // Poll sync status
  useEffect(() => {
    const interval = setInterval(async () => {
      for (const [accountId, taskId] of Object.entries(syncTasks)) {
        try {
          const status = await getSyncStatus(taskId);
          setSyncStatuses((prev) => ({ ...prev, [Number(accountId)]: status }));

          if (status.status === 'completed' || status.status === 'failed') {
            setSyncTasks((prev) => {
              const next = { ...prev };
              delete next[Number(accountId)];
              return next;
            });
            queryClient.invalidateQueries({ queryKey: ['accounts'] });
            queryClient.invalidateQueries({ queryKey: ['receipt-stats'] });
          }
        } catch (error) {
          // Ignore polling errors
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [syncTasks, queryClient]);

  const handleSync = async (accountId: number) => {
    try {
      const response = await startSync(accountId);
      setSyncTasks((prev) => ({ ...prev, [accountId]: response.task_id }));
      setAlert({ type: 'success', message: 'Sync started!' });
    } catch (error) {
      setAlert({ type: 'error', message: 'Failed to start sync' });
    }
  };

  const handleDelete = (account: Account) => {
    if (confirm(`Are you sure you want to disconnect ${account.email}?`)) {
      deleteMutation.mutate(account.id);
    }
  };

  if (authLoading || accountsLoading) {
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
        <h1 className="page-title">Connected Accounts</h1>
      </div>

      {alert && (
        <div className={`alert alert-${alert.type}`}>
          {alert.message}
          <button
            onClick={() => setAlert(null)}
            style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            ×
          </button>
        </div>
      )}

      {/* Connect New Account */}
      <div className="card">
        <h3 className="card-title" style={{ marginBottom: '1rem' }}>
          Connect New Account
        </h3>
        <div style={{ display: 'flex', gap: '1rem' }}>
          {authStatus?.google_configured ? (
            <a href="/api/auth/google" className="btn btn-secondary">
              <span className="account-icon gmail" style={{ width: '1.5rem', height: '1.5rem', fontSize: '0.75rem' }}>
                G
              </span>
              Connect Gmail
            </a>
          ) : (
            <button className="btn btn-secondary" disabled title="Google OAuth not configured">
              <span className="account-icon gmail" style={{ width: '1.5rem', height: '1.5rem', fontSize: '0.75rem', opacity: 0.5 }}>
                G
              </span>
              Gmail (Not Configured)
            </button>
          )}

          {authStatus?.microsoft_configured ? (
            <a href="/api/auth/microsoft" className="btn btn-secondary">
              <span className="account-icon microsoft" style={{ width: '1.5rem', height: '1.5rem', fontSize: '0.75rem' }}>
                M
              </span>
              Connect Microsoft 365
            </a>
          ) : (
            <button className="btn btn-secondary" disabled title="Microsoft OAuth not configured">
              <span className="account-icon microsoft" style={{ width: '1.5rem', height: '1.5rem', fontSize: '0.75rem', opacity: 0.5 }}>
                M
              </span>
              Microsoft 365 (Not Configured)
            </button>
          )}
        </div>

        {!authStatus?.google_configured && !authStatus?.microsoft_configured && (
          <p style={{ marginTop: '1rem', color: 'var(--gray-500)', fontSize: '0.875rem' }}>
            Configure OAuth credentials in environment variables to enable account connections.
          </p>
        )}
      </div>

      {/* Account List */}
      {accounts?.accounts.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p className="empty-state-title">No accounts connected</p>
            <p>Connect a Gmail or Microsoft 365 account to start extracting receipts from your emails.</p>
          </div>
        </div>
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Account</th>
                <th>Provider</th>
                <th>Last Sync</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {accounts?.accounts.map((account) => (
                <AccountRow
                  key={account.id}
                  account={account}
                  syncStatus={syncStatuses[account.id]}
                  isSyncing={!!syncTasks[account.id]}
                  onSync={() => handleSync(account.id)}
                  onDelete={() => handleDelete(account)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* LLM Status */}
      <div className="card">
        <h3 className="card-title" style={{ marginBottom: '0.5rem' }}>
          LLM Extraction
        </h3>
        {authStatus?.llm_enabled ? (
          <p style={{ color: 'var(--success)' }}>
            Enabled - LLM will be used as fallback when rules-based extraction has low confidence.
          </p>
        ) : (
          <p style={{ color: 'var(--gray-500)' }}>
            Disabled - Set OPENAI_API_KEY and LLM_ENABLED=true to enable LLM-based extraction fallback.
          </p>
        )}
      </div>
    </div>
  );
}

function AccountRow({
  account,
  syncStatus,
  isSyncing,
  onSync,
  onDelete,
}: {
  account: Account;
  syncStatus?: SyncStatusResponse;
  isSyncing: boolean;
  onSync: () => void;
  onDelete: () => void;
}) {
  const { data: stats } = useQuery({
    queryKey: ['account-stats', account.id],
    queryFn: () => getAccountStats(account.id),
  });

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleString();
  };

  const getStatusBadge = () => {
    if (isSyncing) {
      const status = syncStatus?.status || 'pending';
      if (status === 'in_progress') {
        return <span className="badge badge-info">Syncing...</span>;
      }
      return <span className="badge badge-warning">Pending</span>;
    }

    if (account.sync_error) {
      return <span className="badge badge-danger" title={account.sync_error}>Error</span>;
    }

    if (account.last_sync_at) {
      return <span className="badge badge-success">Synced</span>;
    }

    return <span className="badge badge-warning">Not Synced</span>;
  };

  return (
    <tr>
      <td>
        <div className="account-card" style={{ margin: 0 }}>
          <div className={`account-icon ${account.provider}`}>
            {account.provider === 'gmail' ? 'G' : 'M'}
          </div>
          <div className="account-info">
            <div className="account-email">{account.email}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--gray-500)' }}>
              {stats ? `${stats.emails_synced} emails, ${stats.receipts_extracted} receipts` : '...'}
            </div>
          </div>
        </div>
      </td>
      <td>{account.provider === 'gmail' ? 'Gmail' : 'Microsoft 365'}</td>
      <td>{formatDate(account.last_sync_at)}</td>
      <td>{getStatusBadge()}</td>
      <td>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className="btn btn-sm btn-primary"
            onClick={onSync}
            disabled={isSyncing}
          >
            {isSyncing ? 'Syncing...' : 'Sync'}
          </button>
          <button
            className="btn btn-sm btn-danger"
            onClick={onDelete}
            disabled={isSyncing}
          >
            Disconnect
          </button>
        </div>
      </td>
    </tr>
  );
}
