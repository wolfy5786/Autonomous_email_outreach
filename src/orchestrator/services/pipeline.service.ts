import { v4 as uuidv4 } from 'uuid';
import { Campaign, ICampaign } from '../models';
import { MessageBroker } from '../../local_infrastructure/rabbit_mq/broker.interface';
import {
  CreateCampaignPayload,
  PlanReadyPayload,
  SourcingCompletedPayload,
  SourcingPartialPayload,
  ProspectingCompletedPayload,
  MessagingCompletedPayload,
  ReviewCompletedPayload,
  SendCompletedPayload,
  SendFailedPayload,
  CampaignStats,
  PipelineStage,
} from '../types';
import { config } from '../config';

/**
 * PipelineService coordinates the entire campaign lifecycle.
 *
 * It publishes events to kick off each stage, then subscribes to
 * completion events from downstream services to advance the pipeline.
 * No business logic lives here — only coordination.
 */
export class PipelineService {
  constructor(private readonly broker: MessageBroker) {}

  // ── Subscriptions ────────────────────────────────────────────

  async startListening(): Promise<void> {
    await this.broker.subscribe('plan.ready', (msg) =>
      this.onPlanReady(msg as PlanReadyPayload)
    );

    await this.broker.subscribe('sourcing.completed', (msg) =>
      this.onSourcingCompleted(msg as SourcingCompletedPayload)
    );

    await this.broker.subscribe('sourcing.partial', (msg) =>
      this.onSourcingPartial(msg as SourcingPartialPayload)
    );

    await this.broker.subscribe('prospecting.completed', (msg) =>
      this.onProspectingCompleted(msg as ProspectingCompletedPayload)
    );

    await this.broker.subscribe('messaging.completed', (msg) =>
      this.onMessagingCompleted(msg as MessagingCompletedPayload)
    );

    await this.broker.subscribe('review.completed', (msg) =>
      this.onReviewCompleted(msg as ReviewCompletedPayload)
    );

    await this.broker.subscribe('send.completed', (msg) =>
      this.onSendCompleted(msg as SendCompletedPayload)
    );

    await this.broker.subscribe('send.failed', (msg) =>
      this.onSendFailed(msg as SendFailedPayload)
    );

    console.log('[PipelineService] Listening on all downstream queues.');
  }

  // ── Campaign Creation ────────────────────────────────────────

  async createCampaign(payload: CreateCampaignPayload): Promise<ICampaign> {
    const campaignId = uuidv4();

    const campaign = await Campaign.create({
      campaign_id: campaignId,
      name: payload.name,
      icp: payload.icp,
      product_profile: payload.product_profile,
      config: payload.config,
      status: 'running',
      pipeline_state: {
        current_stage: 'planning',
        stage_timestamps: {
          planning: new Date().toISOString(),
        },
      },
    });

    // Kick off the pipeline by requesting a plan
    await this.broker.publish('plan.requested', { campaign_id: campaignId });
    console.log(`[PipelineService] Campaign ${campaignId} created → plan.requested`);

    return campaign;
  }

  // ── Stage Handlers ───────────────────────────────────────────

  private async onPlanReady(payload: PlanReadyPayload): Promise<void> {
    const { campaign_id, plan_id } = payload;
    console.log(`[PipelineService] plan.ready for campaign ${campaign_id}`);

    const campaign = await this.findCampaign(campaign_id);
    if (!campaign || campaign.status === 'paused') return;

    campaign.plan_id = plan_id;
    campaign.pipeline_state.plan_id = plan_id;
    await this.advanceStage(campaign, 'sourcing');

    // Fan out sourcing requests — the Planning Service determined targets,
    // but for now the orchestrator publishes a single sourcing event.
    // Target entities would come from the plan; using campaign_id as placeholder.
    await this.broker.publish('sourcing.requested', {
      campaign_id,
      plan_id,
      target_entities: [], // populated from plan document in real flow
    });
  }

  private async onSourcingCompleted(payload: SourcingCompletedPayload): Promise<void> {
    const { campaign_id, entity_ids } = payload;
    console.log(`[PipelineService] sourcing.completed for campaign ${campaign_id} — ${entity_ids.length} entities`);

    const campaign = await this.findCampaign(campaign_id);
    if (!campaign || campaign.status === 'paused') return;

    campaign.pipeline_state.sourced_entity_ids.push(...entity_ids);
    await this.advanceStage(campaign, 'prospecting');

    // Prospecting Service listens directly on sourcing.completed,
    // so no additional publish is needed here.
  }

  private async onSourcingPartial(payload: SourcingPartialPayload): Promise<void> {
    const { campaign_id, entity_id, missing_fields } = payload;
    console.log(
      `[PipelineService] sourcing.partial for ${entity_id} — missing: ${missing_fields.join(', ')}`
    );

    // Log partial sourcing — don't block pipeline but track it.
    // Could trigger a Layer 2 retry or manual review flag.
  }

  private async onProspectingCompleted(payload: ProspectingCompletedPayload): Promise<void> {
    const { campaign_id, ranked_prospects } = payload;
    console.log(
      `[PipelineService] prospecting.completed for campaign ${campaign_id} — ${ranked_prospects.length} ranked`
    );

    const campaign = await this.findCampaign(campaign_id);
    if (!campaign || campaign.status === 'paused') return;

    const qualifiedIds = ranked_prospects
      .filter((p) => p.score >= campaign.config.min_icp_score)
      .map((p) => p.poc_id);

    campaign.pipeline_state.ranked_prospect_ids = qualifiedIds;
    await this.advanceStage(campaign, 'messaging');

    // Fan out one messaging.requested per qualified prospect
    for (const poc_id of qualifiedIds) {
      await this.broker.publish('messaging.requested', {
        campaign_id,
        poc_id,
      });
    }

    console.log(
      `[PipelineService] Published messaging.requested for ${qualifiedIds.length} prospects`
    );
  }

  private async onMessagingCompleted(payload: MessagingCompletedPayload): Promise<void> {
    const { campaign_id, draft_id } = payload;
    console.log(`[PipelineService] messaging.completed — draft ${draft_id}`);

    const campaign = await this.findCampaign(campaign_id);
    if (!campaign) return;

    campaign.pipeline_state.draft_ids.push(draft_id);

    // Check if all messaging is done → move to review stage
    if (
      campaign.pipeline_state.draft_ids.length >=
      campaign.pipeline_state.ranked_prospect_ids.length
    ) {
      await this.advanceStage(campaign, 'review');
      campaign.status = 'review';
    }

    await campaign.save();
  }

  private async onReviewCompleted(payload: ReviewCompletedPayload): Promise<void> {
    const { draft_id, decision } = payload;
    console.log(`[PipelineService] review.completed — draft ${draft_id}: ${decision}`);

    // If approved, the Review Service already published send.requested.
    // If rejected, a regeneration may have been published as messaging.requested.
    // The orchestrator simply tracks the decision for stats.
  }

  private async onSendCompleted(payload: SendCompletedPayload): Promise<void> {
    const { draft_id, message_id, sent_at } = payload;
    console.log(`[PipelineService] send.completed — draft ${draft_id}`);

    // Find the campaign that owns this draft and update state
    const campaigns = await Campaign.find({
      'pipeline_state.draft_ids': draft_id,
    });

    for (const campaign of campaigns) {
      campaign.pipeline_state.sent_draft_ids.push(draft_id);
      await this.checkCompletion(campaign);
    }
  }

  private async onSendFailed(payload: SendFailedPayload): Promise<void> {
    const { draft_id, error, retry_count } = payload;
    console.log(
      `[PipelineService] send.failed — draft ${draft_id} (attempt ${retry_count}): ${error}`
    );

    if (retry_count < config.retryLimit) {
      // Re-publish for retry
      await this.broker.publish('send.requested', { draft_id });
      console.log(`[PipelineService] Retrying send for draft ${draft_id}`);
    } else {
      // Mark as permanently failed
      const campaigns = await Campaign.find({
        'pipeline_state.draft_ids': draft_id,
      });

      for (const campaign of campaigns) {
        campaign.pipeline_state.failed_draft_ids.push(draft_id);
        await this.checkCompletion(campaign);
      }
    }
  }

  // ── Helpers ──────────────────────────────────────────────────

  private async findCampaign(campaignId: string): Promise<ICampaign | null> {
    return Campaign.findOne({ campaign_id: campaignId });
  }

  private async advanceStage(campaign: ICampaign, stage: PipelineStage): Promise<void> {
    campaign.pipeline_state.current_stage = stage;
    campaign.pipeline_state.stage_timestamps[stage] = new Date().toISOString();
    await campaign.save();
    console.log(`[PipelineService] Campaign ${campaign.campaign_id} → stage: ${stage}`);
  }

  private async checkCompletion(campaign: ICampaign): Promise<void> {
    const { draft_ids, sent_draft_ids, failed_draft_ids } = campaign.pipeline_state;
    const processed = sent_draft_ids.length + failed_draft_ids.length;

    if (processed >= draft_ids.length && draft_ids.length > 0) {
      campaign.status = 'completed';
      campaign.pipeline_state.current_stage = 'completed';
      campaign.pipeline_state.stage_timestamps.completed = new Date().toISOString();
      await campaign.save();

      const stats = this.computeStats(campaign);
      await this.broker.publish('campaign.completed', {
        campaign_id: campaign.campaign_id,
        stats,
      });

      console.log(
        `[PipelineService] Campaign ${campaign.campaign_id} COMPLETED. Sent: ${stats.emails_sent}, Failed: ${stats.emails_failed}`
      );
    } else {
      await campaign.save();
    }
  }

  private computeStats(campaign: ICampaign): CampaignStats {
    const ps = campaign.pipeline_state;
    const totalProspects = ps.ranked_prospect_ids.length;
    const draftsGenerated = ps.draft_ids.length;
    const emailsSent = ps.sent_draft_ids.length;
    const emailsFailed = ps.failed_draft_ids.length;
    const draftsApproved = emailsSent + emailsFailed; // approximation
    const draftsRejected = draftsGenerated - draftsApproved;

    return {
      total_prospects: totalProspects,
      drafts_generated: draftsGenerated,
      drafts_approved: draftsApproved,
      drafts_rejected: Math.max(0, draftsRejected),
      emails_sent: emailsSent,
      emails_failed: emailsFailed,
      approval_rate: draftsGenerated > 0 ? draftsApproved / draftsGenerated : 0,
      bounce_rate: emailsSent > 0 ? emailsFailed / (emailsSent + emailsFailed) : 0,
    };
  }
}
