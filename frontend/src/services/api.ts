import axios from 'axios';
import type {
  Account,
  AccountListResponse,
  AccountStats,
  AuthStatus,
  Receipt,
  ReceiptListResponse,
  ReceiptStats,
  SyncResponse,
  SyncStatusResponse,
} from '../types';

const api = axios.create({
  baseURL: '/api',
});

// Auth
export const getAuthStatus = async (): Promise<AuthStatus> => {
  const { data } = await api.get('/auth/status');
  return data;
};

// Accounts
export const getAccounts = async (): Promise<AccountListResponse> => {
  const { data } = await api.get('/accounts');
  return data;
};

export const getAccount = async (id: number): Promise<Account> => {
  const { data } = await api.get(`/accounts/${id}`);
  return data;
};

export const getAccountStats = async (id: number): Promise<AccountStats> => {
  const { data } = await api.get(`/accounts/${id}/stats`);
  return data;
};

export const deleteAccount = async (id: number): Promise<void> => {
  await api.delete(`/accounts/${id}`);
};

// Receipts
export const getReceipts = async (params: {
  page?: number;
  page_size?: number;
  account_id?: number;
  vendor?: string;
  category?: string;
  date_from?: string;
  date_to?: string;
}): Promise<ReceiptListResponse> => {
  const { data } = await api.get('/receipts', { params });
  return data;
};

export const getReceipt = async (id: number): Promise<Receipt> => {
  const { data } = await api.get(`/receipts/${id}`);
  return data;
};

export const deleteReceipt = async (id: number): Promise<void> => {
  await api.delete(`/receipts/${id}`);
};

export const getReceiptStats = async (account_id?: number): Promise<ReceiptStats> => {
  const { data } = await api.get('/receipts/stats/summary', {
    params: account_id ? { account_id } : {},
  });
  return data;
};

export const exportReceipts = async (params?: {
  account_id?: number;
  date_from?: string;
  date_to?: string;
}): Promise<Blob> => {
  const { data } = await api.get('/receipts/export', {
    params,
    responseType: 'blob',
  });
  return data;
};

// Sync
export const startSync = async (account_id: number): Promise<SyncResponse> => {
  const { data } = await api.post('/sync/start', { account_id });
  return data;
};

export const getSyncStatus = async (task_id: string): Promise<SyncStatusResponse> => {
  const { data } = await api.get(`/sync/status/${task_id}`);
  return data;
};

export const syncAllAccounts = async (): Promise<{ message: string; tasks: SyncResponse[] }> => {
  const { data } = await api.post('/sync/all');
  return data;
};
