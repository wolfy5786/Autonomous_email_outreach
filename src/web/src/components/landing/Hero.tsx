import { motion } from "framer-motion";
import { ArrowRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Hero() {
  return (
    <section
      id="top"
      className="relative overflow-hidden bg-[#070710] text-white pt-32 pb-24"
    >
      {/* Backdrop gradients */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(60% 60% at 50% 0%, rgba(99,102,241,0.35) 0%, rgba(7,7,16,0) 60%), radial-gradient(40% 40% at 80% 30%, rgba(236,72,153,0.25) 0%, rgba(7,7,16,0) 70%)",
        }}
      />
      <div
        aria-hidden
        className="absolute inset-0 opacity-[0.04] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />

      <div className="relative max-w-5xl mx-auto px-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-white/70"
        >
          <Sparkles className="size-3.5" />
          AI cold email outreach for B2B SaaS founders
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05 }}
          className="mt-6 text-5xl md:text-7xl font-semibold tracking-tight leading-[1.05]"
        >
          Personalized cold emails,{" "}
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-300 via-fuchsia-300 to-amber-200">
            drafted into your Gmail.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="mt-6 text-lg md:text-xl text-white/70 max-w-2xl mx-auto"
        >
          Tell us your ideal customer. We find prospects, research each one,
          and write a personalized cold email — straight into your Gmail
          drafts folder. You review and hit send.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.25 }}
          className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3"
        >
          <Button variant="glow" size="xl" asChild>
            <a href="#access">
              Get early access
              <ArrowRight className="size-4" />
            </a>
          </Button>
          <Button variant="invertedOutline" size="xl" asChild>
            <a href="#how">See how it works</a>
          </Button>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="mt-8 text-xs text-white/40"
        >
          No credit card. Connects to Gmail. Drafts are yours to edit.
        </motion.p>
      </div>

      <HeroVisual />
    </section>
  );
}

function HeroVisual() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, delay: 0.4 }}
      className="relative max-w-4xl mx-auto px-6 mt-16"
    >
      <div className="rounded-xl border border-white/10 bg-white/[0.03] backdrop-blur p-6 shadow-2xl">
        <div className="flex items-center gap-2 pb-4 border-b border-white/10">
          <div className="size-2 rounded-full bg-red-500/70" />
          <div className="size-2 rounded-full bg-yellow-500/70" />
          <div className="size-2 rounded-full bg-green-500/70" />
          <div className="ml-3 text-xs text-white/40 font-mono">
            drafts/c-acme-001 — Gmail
          </div>
        </div>
        <div className="pt-4 text-left text-sm space-y-3">
          <div className="text-white/40">To: maya@stripe.com</div>
          <div className="text-white/40">
            Subject:{" "}
            <span className="text-white">
              Quick thought on the new Stripe Apps SDK
            </span>
          </div>
          <div className="text-white/80 leading-relaxed">
            Hey Maya — saw the Stripe Apps SDK ship last week. Curious whether
            the team is hitting the same observability gap our other K8s-shop
            customers run into: deploy-aware anomaly detection in the first 90
            seconds. We built something for exactly that. Worth a 15-min look?
          </div>
          <div className="text-white/40 pt-1">— from your Gmail draft</div>
        </div>
      </div>
    </motion.div>
  );
}
