import { motion } from "framer-motion";
import { Zap, Mail, Database, Eye } from "lucide-react";

const pillars = [
  {
    icon: Zap,
    title: "Real personalization, not Mad Libs",
    body: "Each draft references something specific — funding, hiring, a launch, a public talk. Things a researcher would find, not template tokens.",
  },
  {
    icon: Mail,
    title: "Drafts in your Gmail",
    body: "We don't host another inbox. Drafts appear in your account. Deliverability is yours; your reputation is yours.",
  },
  {
    icon: Database,
    title: "Ten sources, one pipeline",
    body: "Y Combinator, Product Hunt, Crunchbase, OpenCorporates, NIH Reporter, Hacker News, LinkedIn, SerpAPI, and more — wired up.",
  },
  {
    icon: Eye,
    title: "Full pipeline visibility",
    body: "Every campaign is traced end-to-end. See exactly where a prospect is, what we found, and why a draft looks the way it does.",
  },
];

export function Features() {
  return (
    <section id="features" className="bg-white text-black py-28">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center max-w-2xl mx-auto">
          <p className="text-sm uppercase tracking-widest text-black/40 mb-4">
            What's different
          </p>
          <h2 className="text-4xl md:text-5xl font-semibold tracking-tight">
            Built for outbound that earns a reply.
          </h2>
        </div>

        <div className="mt-20 grid md:grid-cols-2 gap-6">
          {pillars.map((p, i) => (
            <motion.div
              key={p.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="rounded-2xl border border-black/10 p-8 bg-gradient-to-br from-white to-neutral-50"
            >
              <div className="size-10 rounded-lg bg-black text-white flex items-center justify-center">
                <p.icon className="size-5" />
              </div>
              <h3 className="mt-5 text-xl font-semibold tracking-tight">
                {p.title}
              </h3>
              <p className="mt-3 text-black/60 leading-relaxed">{p.body}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
