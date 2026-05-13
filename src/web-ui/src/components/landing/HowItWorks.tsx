import { motion } from "framer-motion";
import { Crosshair, Search, Microscope, PenLine, Inbox } from "lucide-react";

function MockICPForm() {
  const fields: Array<[string, string]> = [
    ["Industry", "B2B SaaS"],
    ["Employees", "4 – 500"],
    ["Geography", "United States"],
    ["Stack", "LangGraph · Pinecone · LLM"],
    ["Pain", "API gateway for AI agents"],
  ];
  return (
    <div className="rounded-2xl bg-white border border-black/10 shadow-sm p-5 text-[13px]">
      <div className="text-[10px] uppercase tracking-widest text-black/40 mb-3">
        New campaign — ICP
      </div>
      <div className="space-y-2">
        {fields.map(([k, v]) => (
          <div key={k} className="flex items-center gap-3">
            <div className="w-20 text-black/50">{k}</div>
            <div className="flex-1 rounded-md bg-neutral-100 border border-black/5 px-2.5 py-1.5 text-black/80">
              {v}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 flex justify-end">
        <div className="rounded-md bg-black text-white text-[11px] px-3 py-1.5">
          Create campaign
        </div>
      </div>
    </div>
  );
}

function MockCompanyGrid() {
  const cos = [
    { name: "Langfuse", domain: "langfuse.com", tag: "LLM Obs" },
    { name: "Modal", domain: "modal.com", tag: "AI Infra" },
    { name: "Pinecone", domain: "pinecone.io", tag: "Vector DB" },
    { name: "Replicate", domain: "replicate.com", tag: "Inference" },
    { name: "Weights & Biases", domain: "wandb.ai", tag: "Evals" },
    { name: "Temporal", domain: "temporal.io", tag: "Orchestration" },
  ];
  return (
    <div className="rounded-2xl bg-white border border-black/10 shadow-sm p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[10px] uppercase tracking-widest text-black/40">
          Discovered
        </div>
        <div className="text-[10px] text-black/40">147 companies · YC · PH · HN</div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {cos.map((c) => (
          <div
            key={c.name}
            className="flex items-center gap-2.5 rounded-lg border border-black/5 bg-neutral-50 px-2.5 py-2"
          >
            <div className="size-7 rounded-md bg-gradient-to-br from-neutral-300 to-neutral-400 text-white text-[10px] font-medium flex items-center justify-center">
              {c.name[0]}
            </div>
            <div className="min-w-0">
              <div className="text-[12px] font-medium truncate">{c.name}</div>
              <div className="text-[10px] text-black/45 truncate">{c.domain}</div>
            </div>
            <div className="ml-auto text-[9px] text-black/50 bg-white border border-black/10 rounded px-1.5 py-0.5">
              {c.tag}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MockSignalCard() {
  const signals: Array<[string, string]> = [
    ["Funding", "Series B · $30M · 3 weeks ago"],
    ["Hiring", "Senior MLE, Eval Infra"],
    ["Launch", "v2 agent gateway · ProductHunt"],
    ["Stack", "Python · LangGraph · Pinecone"],
  ];
  return (
    <div className="rounded-2xl bg-white border border-black/10 shadow-sm p-5 text-[12px]">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="size-6 rounded-md bg-gradient-to-br from-neutral-300 to-neutral-400 text-white text-[10px] font-medium flex items-center justify-center">
            L
          </div>
          <div className="font-medium">Langfuse</div>
        </div>
        <div className="text-[10px] rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100 px-2 py-0.5">
          score 0.91
        </div>
      </div>
      <div className="space-y-1.5">
        {signals.map(([k, v]) => (
          <div key={k} className="flex gap-3">
            <div className="w-16 text-black/45 text-[11px]">{k}</div>
            <div className="flex-1 text-black/80">{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MockDraftCard() {
  return (
    <div className="rounded-2xl bg-white border border-black/10 shadow-sm p-5 text-[12px]">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[10px] uppercase tracking-widest text-black/40">
          Draft · pending review
        </div>
        <div className="text-[10px] text-black/40">via Gemini</div>
      </div>
      <div className="text-[13px] font-medium leading-snug">
        Your Series B + the agent-gateway gap
      </div>
      <div className="mt-2 text-black/70 leading-relaxed">
        Hi Marc, congrats on the $30M Series B — saw the announcement three weeks back.
        Noticed you're hiring a Senior MLE for eval infra and just shipped the v2 agent
        gateway on PH. We help teams running LangGraph + Pinecone tighten the auth/load
        layer between agents…
      </div>
      <div className="mt-3 flex gap-2">
        <div className="text-[10px] rounded bg-neutral-100 border border-black/5 px-2 py-0.5 text-black/60">
          funding
        </div>
        <div className="text-[10px] rounded bg-neutral-100 border border-black/5 px-2 py-0.5 text-black/60">
          hiring
        </div>
        <div className="text-[10px] rounded bg-neutral-100 border border-black/5 px-2 py-0.5 text-black/60">
          launch
        </div>
      </div>
    </div>
  );
}

function MockGmailInbox() {
  const rows = [
    { from: "Drafts", subj: "Your Series B + the agent-gateway gap", to: "marc@langfuse.com", time: "9:14" },
    { from: "Drafts", subj: "Modal's inference scale + auth questions", to: "erik@modal.com", time: "9:14" },
    { from: "Drafts", subj: "Pinecone's eval pipeline gap", to: "edo@pinecone.io", time: "9:13" },
    { from: "Drafts", subj: "Replicate · gateway between agents", to: "ben@replicate.com", time: "9:13" },
  ];
  return (
    <div className="rounded-2xl bg-white border border-black/10 shadow-sm overflow-hidden text-[12px]">
      <div className="flex items-center gap-2 border-b border-black/5 px-4 py-2.5 bg-neutral-50">
        <Inbox className="size-3.5 text-black/50" />
        <div className="text-[11px] font-medium text-black/70">Drafts</div>
        <div className="ml-auto text-[10px] text-black/40">4 new</div>
      </div>
      {rows.map((r, i) => (
        <div
          key={i}
          className="flex items-center gap-3 px-4 py-2.5 border-b border-black/5 last:border-b-0 hover:bg-neutral-50"
        >
          <div className="w-14 shrink-0 text-[11px] text-black/50">{r.from}</div>
          <div className="min-w-0 flex-1">
            <div className="text-[12px] font-medium truncate">
              {r.subj}{" "}
              <span className="text-black/45 font-normal">— to {r.to}</span>
            </div>
          </div>
          <div className="text-[10px] text-black/40">{r.time}</div>
        </div>
      ))}
    </div>
  );
}

const steps = [
  {
    icon: Crosshair,
    title: "Describe your ICP",
    body: "Industry, company size, stack, geography, the pain you solve. 30 seconds.",
    visual: <MockICPForm />,
  },
  {
    icon: Search,
    title: "We discover companies",
    body: "Across YC, Product Hunt, Crunchbase, NIH, OpenCorporates, and 8+ sources — automatically.",
    visual: <MockCompanyGrid />,
  },
  {
    icon: Microscope,
    title: "We research each prospect",
    body: "Funding events, hiring signals, product launches, tech stack — fresh, per prospect.",
    visual: <MockSignalCard />,
  },
  {
    icon: PenLine,
    title: "We draft a personalized email",
    body: "Real signals, in your voice. No 'I saw your recent post' filler.",
    visual: <MockDraftCard />,
  },
  {
    icon: Inbox,
    title: "Drops into your Gmail",
    body: "Sits in your drafts folder. You review, edit, hit send. Done.",
    visual: <MockGmailInbox />,
  },
];

export function HowItWorks() {
  return (
    <section id="how" className="bg-white text-black py-28">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center max-w-2xl mx-auto">
          <p className="text-sm uppercase tracking-widest text-black/40 mb-4">
            How it works
          </p>
          <h2 className="text-4xl md:text-5xl font-semibold tracking-tight">
            We do the prospecting. <br className="hidden md:block" />
            You hit send.
          </h2>
          <p className="mt-6 text-lg text-black/60">
            A pipeline that runs once, every day, or on demand — and ends in
            your draft folder.
          </p>
        </div>

        <div className="mt-20 relative">
          {/* Connector line */}
          <div
            aria-hidden
            className="absolute left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-transparent via-black/10 to-transparent hidden md:block"
          />
          <div className="space-y-12 md:space-y-20">
            {steps.map((s, i) => (
              <motion.div
                key={s.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 0.5 }}
                className={`relative md:grid md:grid-cols-2 md:gap-16 items-center ${
                  i % 2 === 1 ? "md:[&>*:first-child]:order-2" : ""
                }`}
              >
                <div className="md:px-4">
                  <div className="inline-flex items-center gap-3">
                    <div className="size-10 rounded-full bg-black text-white flex items-center justify-center">
                      <s.icon className="size-5" />
                    </div>
                    <div className="text-xs uppercase tracking-widest text-black/40">
                      Step {i + 1}
                    </div>
                  </div>
                  <h3 className="mt-4 text-2xl font-semibold tracking-tight">
                    {s.title}
                  </h3>
                  <p className="mt-3 text-black/60 leading-relaxed">{s.body}</p>
                </div>

                <div className="hidden md:block">
                  <div className="rounded-2xl bg-gradient-to-br from-neutral-100 to-neutral-200 border border-black/5 p-6">
                    {s.visual}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
