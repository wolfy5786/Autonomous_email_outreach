import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  Mail,
  RefreshCw,
  X,
  ExternalLink,
} from "lucide-react";

import { endpoints } from "@/api/endpoints";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { formatDateTime } from "@/lib/format";

export default function DraftDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: draft, isLoading, isError } = useQuery({
    queryKey: ["draft", id],
    queryFn: () => endpoints.getDraft(id!),
    enabled: !!id,
  });

  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");

  const update = useMutation({
    mutationFn: (patch: Partial<typeof draft>) =>
      endpoints.updateDraft(id!, patch ?? {}),
    onSuccess: (next) => {
      qc.setQueryData(["draft", id], next);
      qc.invalidateQueries({ queryKey: ["campaign-drafts"] });
      setEditing(false);
    },
  });

  function startEdit() {
    if (!draft) return;
    setSubject(draft.subject);
    setBody(draft.body);
    setEditing(true);
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (isError || !draft) {
    return (
      <div className="text-center py-16">
        <p className="text-black/50">Draft not found.</p>
        <Link
          to="/app/drafts"
          className="mt-3 inline-block text-sm underline text-black/60"
        >
          ← back to drafts
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <Link
          to="/app/drafts"
          className="inline-flex items-center gap-2 text-sm text-black/60 hover:text-black"
        >
          <ArrowLeft className="size-4" />
          All drafts
        </Link>
        <div className="mt-3 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <Badge
              variant={
                draft.status === "draft_created"
                  ? "success"
                  : draft.status === "failed"
                    ? "destructive"
                    : "warning"
              }
            >
              {draft.status.replace("_", " ")}
            </Badge>
            {draft.email_provider && (
              <Badge variant="outline">
                <Mail className="size-3 mr-1" />
                {draft.email_provider}
              </Badge>
            )}
            <span className="text-xs text-black/40">
              generated {formatDateTime(draft.generated_at)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {!editing && (
              <Button variant="outline" size="sm" onClick={startEdit}>
                Edit
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                update.mutate({ status: "failed" })
              }
              disabled={update.isPending || draft.status === "failed"}
            >
              <X className="size-4" />
              Reject
            </Button>
            <Button
              size="sm"
              onClick={() =>
                update.mutate({ status: "draft_created" })
              }
              disabled={update.isPending || draft.status === "draft_created"}
            >
              <Check className="size-4" />
              Approve
            </Button>
          </div>
        </div>
      </div>

      {/* Draft body card */}
      <div className="rounded-xl border border-black/10 bg-white">
        <div className="px-6 py-4 border-b border-black/5 grid grid-cols-[120px_1fr] gap-2 text-sm">
          <span className="text-black/40">To</span>
          <span className="font-mono text-xs">
            poc:{draft.poc_id} · company:{draft.company_id}
          </span>
          <span className="text-black/40 mt-1">Subject</span>
          {editing ? (
            <Input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          ) : (
            <span className="font-medium">{draft.subject}</span>
          )}
        </div>

        <div className="px-6 py-5">
          {editing ? (
            <Textarea
              rows={12}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="font-mono text-sm"
            />
          ) : (
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
              {draft.body}
            </pre>
          )}
        </div>

        {editing && (
          <div className="px-6 py-4 border-t border-black/5 flex items-center justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => update.mutate({ subject, body })}
              disabled={update.isPending}
            >
              {update.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        )}

        {draft.email_draft_ref && (
          <div className="px-6 py-3 border-t border-black/5 flex items-center justify-between text-xs text-black/50">
            <span>
              In your mailbox:{" "}
              <code className="bg-black/5 px-1.5 py-0.5 rounded">
                {draft.email_draft_ref}
              </code>
            </span>
            <a
              href="https://mail.google.com/mail/u/0/#drafts"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 hover:text-black"
            >
              Open in Gmail
              <ExternalLink className="size-3" />
            </a>
          </div>
        )}
      </div>

      {/* Personalization + LLM metadata */}
      <div className="grid md:grid-cols-2 gap-3">
        <Block title="Personalization hooks">
          {draft.personalization_hooks.length === 0 ? (
            <p className="text-sm text-black/40">No hooks attached.</p>
          ) : (
            <ul className="space-y-2">
              {draft.personalization_hooks.map((h) => (
                <li
                  key={h}
                  className="flex items-start gap-2 text-sm text-black/80"
                >
                  <span className="mt-1.5 size-1.5 rounded-full bg-black/30 shrink-0" />
                  {h}
                </li>
              ))}
            </ul>
          )}
        </Block>
        <Block title="Generation">
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-black/50">Model</dt>
            <dd className="font-mono text-xs">{draft.llm_model ?? "—"}</dd>
            <dt className="text-black/50">Retries</dt>
            <dd className="tabular-nums">{draft.retry_count}</dd>
            {draft.llm_usage && (
              <>
                <dt className="text-black/50">Prompt tokens</dt>
                <dd className="tabular-nums">
                  {draft.llm_usage.prompt_tokens.toLocaleString()}
                </dd>
                <dt className="text-black/50">Completion tokens</dt>
                <dd className="tabular-nums">
                  {draft.llm_usage.completion_tokens.toLocaleString()}
                </dd>
                <dt className="text-black/50">Total tokens</dt>
                <dd className="tabular-nums font-medium">
                  {draft.llm_usage.total_tokens.toLocaleString()}
                </dd>
              </>
            )}
          </dl>
        </Block>
      </div>

      {draft.error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <div className="flex items-center gap-2 font-medium">
            <RefreshCw className="size-4" />
            Generation error
          </div>
          <p className="mt-2 font-mono text-xs">{draft.error}</p>
        </div>
      )}
    </div>
  );
}

function Block({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-black/10 bg-white p-5">
      <h3 className="text-sm uppercase tracking-wide text-black/40 mb-3">
        {title}
      </h3>
      {children}
    </div>
  );
}
