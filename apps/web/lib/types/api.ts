/* Auto-generated TypeScript types from CircleCue OpenAPI schema */

export type AccessLevel = 'none' | 'status' | 'details';
export type Calls = 'ok' | 'prefer_not' | 'no';
export type Messages = 'ok' | 'later';
export type ProvenanceSource = 'user_shared' | 'ai_parsed_user_confirmed' | 'system_inferred' | 'system_collected';

export interface ViewerState {
  owner: string;
  as_of: string;
  activity?: Record<string, any> | null;
  reachability?: {
    calls: Calls;
    messages: Messages;
    reason?: string | null;
    until?: string | null;
    free_in_min?: number | null;
  } | null;
  phone?: Record<string, any> | null;
  travel?: Record<string, any> | null;
  exam?: Record<string, any> | null;
  last_shared_context?: {
    snapshot: Record<string, any>;
    shared_at: string;
  } | null;
  next_boundary_at?: string | null;
  sharing_paused: boolean;
}
