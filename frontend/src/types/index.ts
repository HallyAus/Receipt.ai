export type MailProvider = 'gmail' | 'microsoft';

export interface Account {
  id: number;
  provider: MailProvider;
  email: string;
  last_sync_at: string | null;
  sync_error: string | null;
  created_at: string;
}

export interface AccountStats {
  account_id: number;
  email: string;
  provider: string;
  emails_synced: number;
  receipts_extracted: number;
  last_sync_at: string | null;
  sync_error: string | null;
}

export interface Attachment {
  id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
}

export interface Receipt {
  id: number;
  email_id: number;
  vendor_name: string | null;
  total_amount: string | null;
  currency: string;
  receipt_date: string | null;
  receipt_number: string | null;
  tax_amount: string | null;
  subtotal: string | null;
  payment_method: string | null;
  category: string | null;
  extraction_method: 'rules' | 'llm' | 'manual';
  confidence_score: string | null;
  created_at: string;
  email_subject: string | null;
  email_sender: string | null;
  email_received_at: string | null;
  attachments: Attachment[];
}

export interface ReceiptListResponse {
  receipts: Receipt[];
  total: number;
  page: number;
  page_size: number;
}

export interface AccountListResponse {
  accounts: Account[];
  total: number;
}

export interface SyncResponse {
  task_id: string;
  account_id: number;
  status: string;
  message: string;
}

export interface SyncStatusResponse {
  task_id: string;
  status: string;
  result: {
    emails_found?: number;
    emails_inserted?: number;
    receipts_extracted?: number;
  } | null;
  error: string | null;
}

export interface AuthStatus {
  google_configured: boolean;
  microsoft_configured: boolean;
  llm_enabled: boolean;
}

export interface ReceiptStats {
  total_count: number;
  total_amount: number;
  by_category: Record<string, { count: number; amount: number }>;
  by_month: Array<{ month: string; count: number; amount: number }>;
}
