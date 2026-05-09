import mongoose, { Schema, Document } from 'mongoose';
import { DraftStatus } from '../types';

export interface IEmailDraft extends Document {
  draft_id: string;
  campaign_id: string;
  company_id: string;
  poc_id: string;
  subject: string;
  body: string;
  personalization_hooks: string[];
  generated_at: Date;
  status: DraftStatus;
  reviewer_notes: string | null;
  reviewed_at: Date | null;
  sent_at: Date | null;
  send_message_id: string | null;
}

const EmailDraftSchema = new Schema({
  draft_id: { type: String, required: true, unique: true, index: true },
  campaign_id: { type: String, required: true, index: true },
  company_id: { type: String, required: true },
  poc_id: { type: String, required: true },
  subject: { type: String, required: true },
  body: { type: String, required: true },
  personalization_hooks: { type: [String], default: [] },
  generated_at: { type: Date, default: Date.now },
  status: {
    type: String,
    enum: ['pending_review', 'approved', 'edited_approved', 'rejected', 'sent', 'failed'],
    default: 'pending_review',
    index: true,
  },
  reviewer_notes: { type: String, default: null },
  reviewed_at: { type: Date, default: null },
  sent_at: { type: Date, default: null },
  send_message_id: { type: String, default: null },
});

// Compound index for review queue queries
EmailDraftSchema.index({ campaign_id: 1, status: 1 });

export const EmailDraft = mongoose.model<IEmailDraft>('EmailDraft', EmailDraftSchema);
