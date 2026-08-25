import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  getReceipts,
  getAccounts,
  exportReceipts,
  deleteReceipt,
} from '../services/api';
import type { Receipt } from '../types';

export default function Receipts() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    account_id: '',
    vendor: '',
    category: '',
  });
  const [selectedReceipt, setSelectedReceipt] = useState<Receipt | null>(null);

  const { data: accounts } = useQuery({
    queryKey: ['accounts'],
    queryFn: getAccounts,
  });

  const { data: receipts, isLoading } = useQuery({
    queryKey: ['receipts', page, filters],
    queryFn: () =>
      getReceipts({
        page,
        page_size: 20,
        account_id: filters.account_id ? Number(filters.account_id) : undefined,
        vendor: filters.vendor || undefined,
        category: filters.category || undefined,
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteReceipt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receipts'] });
      queryClient.invalidateQueries({ queryKey: ['receipt-stats'] });
      setSelectedReceipt(null);
    },
  });

  const handleExport = async () => {
    try {
      const blob = await exportReceipts({
        account_id: filters.account_id ? Number(filters.account_id) : undefined,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `receipts_${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      alert('Failed to export receipts');
    }
  };

  const handleDelete = (receipt: Receipt) => {
    if (confirm(`Are you sure you want to delete this receipt from ${receipt.vendor_name}?`)) {
      deleteMutation.mutate(receipt.id);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString();
  };

  const formatAmount = (amount: string | null, currency: string) => {
    if (!amount) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
    }).format(Number(amount));
  };

  const totalPages = receipts ? Math.ceil(receipts.total / receipts.page_size) : 0;

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Receipts</h1>
        <button className="btn btn-primary" onClick={handleExport}>
          Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ marginBottom: 0, minWidth: '200px' }}>
            <label className="form-label">Account</label>
            <select
              className="form-input"
              value={filters.account_id}
              onChange={(e) => {
                setFilters({ ...filters, account_id: e.target.value });
                setPage(1);
              }}
            >
              <option value="">All Accounts</option>
              {accounts?.accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.email}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0, minWidth: '200px' }}>
            <label className="form-label">Vendor</label>
            <input
              type="text"
              className="form-input"
              placeholder="Search vendor..."
              value={filters.vendor}
              onChange={(e) => {
                setFilters({ ...filters, vendor: e.target.value });
                setPage(1);
              }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0, minWidth: '150px' }}>
            <label className="form-label">Category</label>
            <select
              className="form-input"
              value={filters.category}
              onChange={(e) => {
                setFilters({ ...filters, category: e.target.value });
                setPage(1);
              }}
            >
              <option value="">All Categories</option>
              <option value="food">Food</option>
              <option value="travel">Travel</option>
              <option value="office">Office</option>
              <option value="utilities">Utilities</option>
              <option value="subscription">Subscription</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <button
              className="btn btn-secondary"
              onClick={() => {
                setFilters({ account_id: '', vendor: '', category: '' });
                setPage(1);
              }}
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Receipts Table */}
      <div className="card">
        {isLoading ? (
          <div className="loading">
            <div className="spinner"></div>
          </div>
        ) : receipts?.receipts.length === 0 ? (
          <div className="empty-state">
            <p className="empty-state-title">No receipts found</p>
            <p>Connect an email account and sync to start extracting receipts.</p>
          </div>
        ) : (
          <>
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Vendor</th>
                  <th>Amount</th>
                  <th>Category</th>
                  <th>Confidence</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {receipts?.receipts.map((receipt) => (
                  <tr
                    key={receipt.id}
                    className="receipt-row"
                    onClick={() => setSelectedReceipt(receipt)}
                  >
                    <td>{formatDate(receipt.receipt_date)}</td>
                    <td className="receipt-vendor">{receipt.vendor_name || '-'}</td>
                    <td className="receipt-amount">
                      {formatAmount(receipt.total_amount, receipt.currency)}
                    </td>
                    <td>
                      <span
                        className="badge badge-info"
                        style={{ textTransform: 'capitalize' }}
                      >
                        {receipt.category || 'uncategorized'}
                      </span>
                    </td>
                    <td>
                      {receipt.confidence_score ? (
                        <span
                          className={`badge ${
                            Number(receipt.confidence_score) >= 0.7
                              ? 'badge-success'
                              : Number(receipt.confidence_score) >= 0.4
                              ? 'badge-warning'
                              : 'badge-danger'
                          }`}
                        >
                          {Math.round(Number(receipt.confidence_score) * 100)}%
                        </span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(receipt);
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="pagination-btn"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </button>
                {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                  const pageNum = i + 1;
                  return (
                    <button
                      key={pageNum}
                      className={`pagination-btn ${page === pageNum ? 'active' : ''}`}
                      onClick={() => setPage(pageNum)}
                    >
                      {pageNum}
                    </button>
                  );
                })}
                {totalPages > 5 && <span style={{ padding: '0.5rem' }}>...</span>}
                <button
                  className="pagination-btn"
                  disabled={page === totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </button>
              </div>
            )}

            <div style={{ textAlign: 'center', marginTop: '0.5rem', color: 'var(--gray-500)', fontSize: '0.875rem' }}>
              Showing {((page - 1) * 20) + 1}-{Math.min(page * 20, receipts?.total || 0)} of {receipts?.total || 0} receipts
            </div>
          </>
        )}
      </div>

      {/* Receipt Detail Modal */}
      {selectedReceipt && (
        <ReceiptDetailModal
          receipt={selectedReceipt}
          onClose={() => setSelectedReceipt(null)}
          onDelete={() => handleDelete(selectedReceipt)}
        />
      )}
    </div>
  );
}

function ReceiptDetailModal({
  receipt,
  onClose,
  onDelete,
}: {
  receipt: Receipt;
  onClose: () => void;
  onDelete: () => void;
}) {
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString();
  };

  const formatAmount = (amount: string | null, currency: string) => {
    if (!amount) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
    }).format(Number(amount));
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Receipt Details</h2>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">
          <div className="detail-row">
            <span className="detail-label">Vendor</span>
            <span className="detail-value">{receipt.vendor_name || '-'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Amount</span>
            <span className="detail-value" style={{ color: 'var(--primary)', fontWeight: 600 }}>
              {formatAmount(receipt.total_amount, receipt.currency)}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Date</span>
            <span className="detail-value">{formatDate(receipt.receipt_date)}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Category</span>
            <span className="detail-value" style={{ textTransform: 'capitalize' }}>
              {receipt.category || '-'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Receipt #</span>
            <span className="detail-value">{receipt.receipt_number || '-'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Tax</span>
            <span className="detail-value">
              {formatAmount(receipt.tax_amount, receipt.currency)}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Subtotal</span>
            <span className="detail-value">
              {formatAmount(receipt.subtotal, receipt.currency)}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Payment</span>
            <span className="detail-value">{receipt.payment_method || '-'}</span>
          </div>

          <h4 style={{ marginTop: '1.5rem', marginBottom: '0.75rem' }}>Email Info</h4>
          <div className="detail-row">
            <span className="detail-label">Subject</span>
            <span className="detail-value">{receipt.email_subject || '-'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">From</span>
            <span className="detail-value">{receipt.email_sender || '-'}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Received</span>
            <span className="detail-value">{formatDate(receipt.email_received_at)}</span>
          </div>

          {receipt.attachments.length > 0 && (
            <>
              <h4 style={{ marginTop: '1.5rem', marginBottom: '0.75rem' }}>Attachments</h4>
              {receipt.attachments.map((att) => (
                <div key={att.id} className="detail-row">
                  <span className="detail-label">
                    {att.content_type.split('/')[1]?.toUpperCase() || 'File'}
                  </span>
                  <span className="detail-value">
                    {att.filename} ({Math.round(att.size_bytes / 1024)}KB)
                  </span>
                </div>
              ))}
            </>
          )}

          <h4 style={{ marginTop: '1.5rem', marginBottom: '0.75rem' }}>Extraction</h4>
          <div className="detail-row">
            <span className="detail-label">Method</span>
            <span className="detail-value" style={{ textTransform: 'uppercase' }}>
              {receipt.extraction_method}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Confidence</span>
            <span className="detail-value">
              {receipt.confidence_score
                ? `${Math.round(Number(receipt.confidence_score) * 100)}%`
                : '-'}
            </span>
          </div>

          <div style={{ marginTop: '1.5rem', display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button className="btn btn-secondary" onClick={onClose}>
              Close
            </button>
            <button className="btn btn-danger" onClick={onDelete}>
              Delete Receipt
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
