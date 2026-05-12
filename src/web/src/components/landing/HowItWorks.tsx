import { motion } from "framer-motion";
import { Crosshair, Search, Microscope, PenLine, Inbox } from "lucide-react";

const steps = [
  {
    icon: Crosshair,
    title: "Describe your ICP",
    body: "Industry, company size, stack, geography, the pain you solve. 30 seconds.",
  },
  {
    icon: Search,
    title: "We discover companies",
    body: "Across YC, Product Hunt, Crunchbase, NIH, OpenCorporates, and 8+ sources — automatically.",
  },
  {
    icon: Microscope,
    title: "We research each prospect",
    body: "Funding events, hiring signals, product launches, tech stack — fresh, per prospect.",
  },
  {
    icon: PenLine,
    title: "We draft a personalized email",
    body: "Real signals, in your voice. No 'I saw your recent post' filler.",
  },
  {
    icon: Inbox,
    title: "Drops into your Gmail",
    body: "Sits in your drafts folder. You review, edit, hit send. Done.",
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
                  <div className="aspect-[5/3] rounded-2xl bg-gradient-to-br from-neutral-100 to-neutral-200 border border-black/5" />
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
