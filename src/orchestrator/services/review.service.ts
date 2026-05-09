import { EmailDraft, IEmailDraft } from '../../shared/models';
import { MessageBroker } from '../../local_infrastructure/rabbit_mq/broker.interface';

/**
 * ReviewService handles draft email review operations.
 *
 * Per the Repository_structure.md: "The Review Service is removed;
 * its API endpoints are absorbed into orchestrator."
 */
export class ReviewService {
  constructor(private readonly broker: MessageBroker) {}

  async startListening(): Promise<void> {
    await this.broker.subscribe('review.requested', async (msg) => {
      const { draft_id } = msg as { draft_id: string };
      console.log(`[ReviewService] review.requested — draft ${draft_id} added to queue`);
      // Draft is already in NoSQL with status pending_review.
      // The Review UI polls the review queue endpoint.
    });
  }

  // ── Query Methods ────────────────────────────────────────────

  async getReviewQueue(): Promise<IEmailDraft[]> {
    return EmailDraft.find({ status: 'pending_review' }).sort({ generated_at: 1 });
  }

  async getDraft(draftId: string): Promise<IEmailDraft | null> {
    return EmailDraft.findOne({ draft_id: draftId });
  }

  async getDraftsByCampaign(
    campaignId: string,
    status?: string
  ): Promise<IEmailDraft[]> {
    const filter: Record<string, unknown> = { campaign_id: campaignId };
    if (status) filter.status = status;
    return EmailDraft.find(filter).sort({ generated_at: -1 });
  }

  // ── Action Methods ───────────────────────────────────────────

  async updateDraft(
    draftId: string,
    updates: { subject?: string; body?: string }
  ): Promise<IEmailDraft | null> {
    return EmailDraft.findOneAndUpdate(
      { draft_id: draftId },
      { $set: updates },
      { new: true }
    );
  }

  async approveDraft(draftId: string): Promise<IEmailDraft | null> {
    const draft = await EmailDraft.findOneAndUpdate(
      { draft_id: draftId, status: { $in: ['pending_review'] } },
      {
        $set: {
          status: 'approved',
          reviewed_at: new Date(),
        },
      },
      { new: true }
    );

    if (draft) {
      await this.broker.publish('send.requested', { draft_id: draftId });
      await this.broker.publish('review.completed', {
        draft_id: draftId,
        decision: 'approve',
      });
      console.log(`[ReviewService] Draft ${draftId} approved → send.requested`);
    }

    return draft;
  }

  async rejectDraft(
    draftId: string,
    notes?: string,
    regenerate = false
  ): Promise<IEmailDraft | null> {
    const draft = await EmailDraft.findOneAndUpdate(
      { draft_id: draftId, status: 'pending_review' },
      {
        $set: {
          status: 'rejected',
          reviewer_notes: notes ?? null,
          reviewed_at: new Date(),
        },
      },
      { new: true }
    );

    if (draft) {
      await this.broker.publish('review.completed', {
        draft_id: draftId,
        decision: 'reject',
        notes,
      });

      if (regenerate) {
        await this.broker.publish('messaging.requested', {
          campaign_id: draft.campaign_id,
          poc_id: draft.poc_id,
          regeneration_prompt: notes,
        });
        console.log(`[ReviewService] Draft ${draftId} rejected → regeneration requested`);
      } else {
        console.log(`[ReviewService] Draft ${draftId} rejected (no regeneration)`);
      }
    }

    return draft;
  }

  async bulkApprove(draftIds: string[]): Promise<{ approved: number; failed: string[] }> {
    const failed: string[] = [];
    let approved = 0;

    for (const id of draftIds) {
      const result = await this.approveDraft(id);
      if (result) {
        approved++;
      } else {
        failed.push(id);
      }
    }

    return { approved, failed };
  }

  async regenerateDraft(
    draftId: string,
    prompt?: string
  ): Promise<IEmailDraft | null> {
    const draft = await this.getDraft(draftId);
    if (!draft) return null;

    // Mark current draft as rejected and request regeneration
    draft.status = 'rejected';
    draft.reviewer_notes = prompt ?? 'Regeneration requested';
    draft.reviewed_at = new Date();
    await draft.save();

    await this.broker.publish('messaging.requested', {
      campaign_id: draft.campaign_id,
      poc_id: draft.poc_id,
      regeneration_prompt: prompt,
    });

    console.log(`[ReviewService] Draft ${draftId} → regeneration requested`);
    return draft;
  }
}
