/** Queue payloads for events not yet mirrored in shared types (draft-terminal messaging). */

export interface DraftWrittenPayload {
  campaign_id: string;
  draft_id: string;
  poc_id: string;
  email_draft_ref?: string;
}

export interface DraftFailedPayload {
  campaign_id: string;
  poc_id: string;
  draft_id?: string;
  error: string;
  retry_count: number;
}
