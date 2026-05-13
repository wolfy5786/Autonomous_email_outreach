import mongoose, { Schema, Document } from 'mongoose';
import {
  CampaignStatus,
  CampaignConfig,
  ICPDefinition,
  ProductProfile,
  PipelineState,
} from '../types';

export interface ICampaign extends Document {
  campaign_id: string;
  name: string;
  icp: ICPDefinition;
  product_profile: ProductProfile;
  plan_id: string | null;
  status: CampaignStatus;
  config: CampaignConfig;
  pipeline_state: PipelineState;
  rerun: boolean;
  created_at: Date;
  updated_at: Date;
}

const PipelineStateSchema = new Schema(
  {
    current_stage: {
      type: String,
      enum: ['planning', 'sourcing', 'prospecting', 'messaging', 'review', 'sending', 'completed'],
      default: 'planning',
    },
    plan_id: { type: String, default: null },
    sourced_entity_ids: { type: [String], default: [] },
    ranked_prospect_ids: { type: [String], default: [] },
    ranked_prospect_scores: { type: Schema.Types.Mixed, default: {} },
    messaging_target_ids: { type: [String] },
    draft_ids: { type: [String], default: [] },
    sent_draft_ids: { type: [String], default: [] },
    failed_draft_ids: { type: [String], default: [] },
    stage_timestamps: { type: Schema.Types.Mixed, default: {} },
  },
  { _id: false }
);

const CampaignSchema = new Schema(
  {
    campaign_id: { type: String, required: true, unique: true, index: true },
    name: { type: String, required: true },
    icp: { type: Schema.Types.Mixed, required: true },
    product_profile: { type: Schema.Types.Mixed, required: true },
    plan_id: { type: String, default: null },
    status: {
      type: String,
      enum: [
        'pending',
        'planning',
        'sourcing',
        'prospecting',
        'messaging',
        'paused',
        'completed',
        'failed',
        'cancelled',
      ],
      default: 'pending',
    },
    config: {
      email_account: {
        provider: { type: String, enum: ['gmail', 'microsoft'], required: true },
        credentials_ref: { type: String, required: true },
      },
      min_icp_score: { type: Number, required: true },
      freshness_days: { type: Number, required: true },
      max_drafts: { type: Number, required: true },
      send_window: {
        type: new Schema(
          {
            start_hour: { type: Number },
            end_hour: { type: Number },
            timezone: { type: String },
          },
          { _id: false }
        ),
        required: false,
        default: undefined,
      },
    },
    pipeline_state: { type: PipelineStateSchema, default: () => ({}) },
    rerun: { type: Boolean, default: false },
  },
  {
    timestamps: { createdAt: 'created_at', updatedAt: 'updated_at' },
  }
);

// Compound index for listing campaigns by status
CampaignSchema.index({ status: 1, created_at: -1 });

export const Campaign = mongoose.model<ICampaign>('Campaign', CampaignSchema);
