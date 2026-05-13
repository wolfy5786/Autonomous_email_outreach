import { v4 as uuidv4 } from 'uuid';
import { Campaign, ICampaign } from '../../shared/models';
import { MessageBroker } from '../../local_infrastructure/rabbit_mq/broker.interface';
import {
  CreateCampaignPayload,
  PlanReadyPayload,
  SourcingCompletedPayload,
  SourcingPartialPayload,
  ProspectingCompletedPayload,
  CampaignCompletedPayload,
  CampaignStats,
  PipelineStage,
  CampaignStatus,
} from '../../shared/types';
import { config } from '../config';
import type { DraftWrittenPayload, DraftFailedPayload } from '../types/queue-payloads';
import { CampaignStatusRepository } from '../postgres';

/** Statuses where downstream events must not advance or mutate pipeline progress. */
const NONPROCESSING_STATUSES: CampaignStatus[] = ['paused', 'cancelled', 'completed', 'failed'];

function skipPipelineHandlers(status: CampaignStatus): boolean {
  return NONPROCESSING_STATUSES.includes(status);
}

/** Pipeline stages mirrored onto campaign `status` while work is in flight. */
const ACTIVE_STAGE_STATUSES: CampaignStatus[] = ['planning', 'sourcing', 'prospecting', 'messaging'];

/**
 * Inbound queues for this service only — mirrors `queues` entries in
 * {@link ../../local_infrastructure/rabbit_mq/definitions.json} (coordination queues, lines 48–54).
 */
const ORCHESTRATOR_INBOUND_QUEUE_NAMES = [
  'plan.ready',
  'sourcing.completed',
  'sourcing.partial',
  'prospecting.completed',
  'draft.written',
  'draft.failed',
  'campaign.completed',
] as const;

type OrchestratorInboundQueue = (typeof ORCHESTRATOR_INBOUND_QUEUE_NAMES)[number];

/**
 * PipelineService coordinates the entire campaign lifecycle.
 *
 * It publishes events to kick off each stage, then subscribes to
 * completion events from downstream services to advance the pipeline.
 * No business logic lives here — only coordination.
 */
export class PipelineService {
  constructor(
    private readonly broker: MessageBroker,
    private readonly statusRepo: CampaignStatusRepository
  ) {}

  // ── Subscriptions ────────────────────────────────────────────

  async startListening(): Promise<void> {
    const handlers: {
      readonly [Q in OrchestratorInboundQueue]: (msg: unknown) => Promise<void>;
    } = {
      'plan.ready': (msg) => this.onPlanReady(msg as PlanReadyPayload),
      'sourcing.completed': (msg) => this.onSourcingCompleted(msg as SourcingCompletedPayload),
      'sourcing.partial': (msg) => this.onSourcingPartial(msg as SourcingPartialPayload),
      'prospecting.completed': (msg) =>
        this.onProspectingCompleted(msg as ProspectingCompletedPayload),
      'draft.written': (msg) => this.onDraftWritten(msg as DraftWrittenPayload),
      'draft.failed': (msg) => this.onDraftFailed(msg as DraftFailedPayload),
      'campaign.completed': (msg) => this.onCampaignCompleted(msg as CampaignCompletedPayload),
    };

    for (const queueName of ORCHESTRATOR_INBOUND_QUEUE_NAMES) {
      await this.broker.subscribe(queueName, handlers[queueName]);
    }

    console.log(
      `[PipelineService] Listening on coordination queues only: ${ORCHESTRATOR_INBOUND_QUEUE_NAMES.join(', ')}.`
    );
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
      status: 'planning',
      pipeline_state: {
        current_stage: 'planning',
        stage_timestamps: {
          planning: new Date().toISOString(),
        },
      },
    });

    // Mirror initial status into Postgres (orchestrator_service_role.md §2.1).
    await this.statusRepo.insert({
      campaign_id: campaignId,
      status: 'planning',
      current_stage: 'planning',
      plan_id: null,
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
    if (!campaign || skipPipelineHandlers(campaign.status)) return;

    campaign.plan_id = plan_id;
    campaign.pipeline_state.plan_id = plan_id;
    await this.advanceStage(campaign, 'sourcing');

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
    if (!campaign || skipPipelineHandlers(campaign.status)) return;

    campaign.pipeline_state.sourced_entity_ids.push(...entity_ids);
    await this.advanceStage(campaign, 'prospecting');

    const plan_id = campaign.pipeline_state.plan_id ?? campaign.plan_id ?? '';
    await this.broker.publish('prospecting.requested', {
      campaign_id,
      plan_id,
      entity_ids: [...campaign.pipeline_state.sourced_entity_ids],
    });
    console.log(`[PipelineService] prospecting.requested for campaign ${campaign_id}`);
  }

  private async onSourcingPartial(payload: SourcingPartialPayload): Promise<void> {
    const { campaign_id, entity_id, missing_fields } = payload;
    console.log(
      `[PipelineService] sourcing.partial for ${entity_id} — missing: ${missing_fields.join(', ')}`
    );

    // Log partial sourcing — don't block pipeline but track it.
  }

  private async onProspectingCompleted(payload: ProspectingCompletedPayload): Promise<void> {
    const { campaign_id, ranked_prospects } = payload;
    console.log(
      `[PipelineService] prospecting.completed for campaign ${campaign_id} — ${ranked_prospects.length} ranked`
    );

    const campaign = await this.findCampaign(campaign_id);
    if (!campaign || skipPipelineHandlers(campaign.status)) return;

    const qualified = ranked_prospects.filter(
      (p) => p.total_score >= campaign.config.min_icp_score
    );
    const qualifiedIds = qualified.map((p) => p.poc_id);

    campaign.pipeline_state.ranked_prospect_ids = qualifiedIds;
    const scores: Record<string, number> =
      campaign.pipeline_state.ranked_prospect_scores ?? {};
    for (const p of qualified) scores[p.poc_id] = p.total_score;
    campaign.pipeline_state.ranked_prospect_scores = scores;

    const cap = Math.floor(campaign.config.max_drafts);
    const cappedIds = cap > 0 ? qualifiedIds.slice(0, cap) : qualifiedIds;

    campaign.pipeline_state.messaging_target_ids = cappedIds;

    await this.advanceStage(campaign, 'messaging');
    for (const poc_id of cappedIds) {
      await this.broker.publish('messaging.requested', {
        campaign_id,
        poc_id,
      });
    }

    console.log(
      `[PipelineService] Published messaging.requested for ${cappedIds.length} prospects`
    );
  }

  private async onDraftWritten(payload: DraftWrittenPayload): Promise<void> {
    const { campaign_id, draft_id } = payload;
    console.log(`[PipelineService] draft.written — draft ${draft_id}`);

    const campaign = await this.findCampaign(campaign_id);
    if (!campaign || skipPipelineHandlers(campaign.status)) return;

    campaign.pipeline_state.draft_ids.push(draft_id);
    await this.checkMessagingTerminal(campaign);
  }

  private async onCampaignCompleted(payload: CampaignCompletedPayload): Promise<void> {
    const {
      campaign_id,
      stats: { drafts_generated, drafts_rejected },
    } = payload;
    console.log(
      `[PipelineService] campaign.completed (observed) for ${campaign_id} — drafts OK: ${drafts_generated}, terminal failures: ${drafts_rejected}`
    );
  }

  private async onDraftFailed(payload: DraftFailedPayload): Promise<void> {
    const { campaign_id, poc_id, draft_id, error, retry_count } = payload;
    console.log(
      `[PipelineService] draft.failed — poc ${poc_id} (attempt ${retry_count}): ${error}`
    );

    const campaign = await this.findCampaign(campaign_id);
    if (!campaign || skipPipelineHandlers(campaign.status)) return;

    if (retry_count < config.retryLimit) {
      await this.broker.publish('messaging.requested', {
        campaign_id,
        poc_id,
      });
      console.log(`[PipelineService] Retrying messaging.requested for poc ${poc_id}`);
      return;
    }

    const marker = draft_id ?? `poc:${poc_id}`;
    if (!campaign.pipeline_state.failed_draft_ids.includes(marker)) {
      campaign.pipeline_state.failed_draft_ids.push(marker);
    }
    await this.statusRepo.setLastError(
      campaign_id,
      `draft.failed poc=${poc_id}: ${error}`
    );
    await this.checkMessagingTerminal(campaign);
  }

  // ── Helpers ──────────────────────────────────────────────────

  private async findCampaign(campaignId: string): Promise<ICampaign | null> {
    return Campaign.findOne({ campaign_id: campaignId });
  }

  private async advanceStage(campaign: ICampaign, stage: PipelineStage): Promise<void> {
    campaign.pipeline_state.current_stage = stage;
    campaign.pipeline_state.stage_timestamps[stage] = new Date().toISOString();
    if (ACTIVE_STAGE_STATUSES.includes(stage as CampaignStatus)) {
      campaign.status = stage as CampaignStatus;
    }
    await campaign.save();

    // Mirror transition into Postgres so list/status APIs can read cheaply (§2.1).
    await this.statusRepo.updateStage(
      campaign.campaign_id,
      campaign.status,
      stage,
      campaign.pipeline_state.plan_id ?? campaign.plan_id ?? null
    );

    console.log(`[PipelineService] Campaign ${campaign.campaign_id} → stage: ${stage}`);
  }

  /** All messaging targets have a draft or a terminal draft failure. */
  private async checkMessagingTerminal(campaign: ICampaign): Promise<void> {
    const ps = campaign.pipeline_state;
    const targetCount =
      ps.messaging_target_ids !== undefined
        ? ps.messaging_target_ids.length
        : ps.ranked_prospect_ids.length;

    if (targetCount === 0) {
      if (ps.current_stage === 'messaging') {
        await this.finalizeCampaignCompleted(campaign);
      } else {
        await campaign.save();
      }
      return;
    }

    const settled = ps.draft_ids.length + ps.failed_draft_ids.length;
    if (settled < targetCount) {
      await campaign.save();
      return;
    }

    await this.finalizeCampaignCompleted(campaign);
  }

  private async finalizeCampaignCompleted(campaign: ICampaign): Promise<void> {
    campaign.status = 'completed';
    campaign.pipeline_state.current_stage = 'completed';
    campaign.pipeline_state.stage_timestamps.completed = new Date().toISOString();
    await campaign.save();

    // Reflect terminal state in Postgres (§2.1).
    await this.statusRepo.updateStage(campaign.campaign_id, 'completed', 'completed');

    const stats = this.computeStats(campaign);
    await this.broker.publish('campaign.completed', {
      campaign_id: campaign.campaign_id,
      stats,
    });

    console.log(
      `[PipelineService] Campaign ${campaign.campaign_id} COMPLETED. Drafts written: ${stats.drafts_generated}, draft failures: ${stats.drafts_rejected}`
    );
  }

  /**
   * Shared CampaignStats still uses legacy field names; we treat drafts_generated as written
   * drafts and drafts_rejected as terminal messaging failures (see shared-types follow-up).
   */
  private computeStats(campaign: ICampaign): CampaignStats {
    const ps = campaign.pipeline_state;
    const totalProspects = ps.ranked_prospect_ids.length;
    const draftsGenerated = ps.draft_ids.length;
    const draftsFailed = ps.failed_draft_ids.length;

    return {
      total_prospects: totalProspects,
      drafts_generated: draftsGenerated,
      drafts_approved: draftsGenerated,
      drafts_rejected: draftsFailed,
      emails_sent: 0,
      emails_failed: 0,
      approval_rate: totalProspects > 0 ? draftsGenerated / totalProspects : 0,
      bounce_rate: 0,
    };
  }
}
