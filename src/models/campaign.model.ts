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
      enum: ['draft', 'running', 'review', 'completed', 'paused'],
      default: 'draft',
    },
    config: {
      email_channel: {
        type: String,
        enum: ['smtp', 'sendgrid', 'postmark', 'ses'],
        required: true,
      },
      email_channel_config: { type: Schema.Types.Mixed, default: {} },
      min_icp_score: { type: Number, required: true },
      freshness_days: { type: Number, required: true },
      send_window: {
        start_hour: { type: Number, required: true },
        end_hour: { type: Number, required: true },
        timezone: { type: String, required: true },
      },
    },
    pipeline_state: { type: PipelineStateSchema, default: () => ({}) },
  },
  {
    timestamps: { createdAt: 'created_at', updatedAt: 'updated_at' },
  }
);

// Compound index for listing campaigns by status
CampaignSchema.index({ status: 1, created_at: -1 });

export const Campaign = mongoose.model<ICampaign>('Campaign', CampaignSchema);
