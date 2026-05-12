import { motion } from "framer-motion";
import { X, Check } from "lucide-react";

export function Compare() {
  return (
    <section className="bg-[#070710] text-white py-28 border-t border-white/5">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <p className="text-sm uppercase tracking-widest text-white/40 mb-4">
            See the difference
          </p>
          <h2 className="text-4xl md:text-5xl font-semibold tracking-tight">
            A generic template vs. a real draft.
          </h2>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.5 }}
            className="rounded-2xl border border-red-500/20 bg-red-500/[0.04] p-6"
          >
            <div className="flex items-center gap-2 text-xs text-red-300">
              <X className="size-4" />
              The template everyone sends
            </div>
            <div className="mt-4 space-y-2 text-sm text-white/60 leading-relaxed">
              <div className="text-white/40">
                Subject: Quick question about {"{company}"}
              </div>
              <div className="text-white/80">Hi {"{first_name}"},</div>
              <div>
                I help {"{industry}"} companies like yours grow revenue
                through innovative outreach solutions. We've worked with
                hundreds of {"{industry}"} teams to scale their pipeline.
              </div>
              <div>Would you be open to a quick 15-min chat next week?</div>
              <div className="text-white/40">Best, &lt;name&gt;</div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="rounded-2xl border border-emerald-400/20 bg-emerald-500/[0.04] p-6 ring-1 ring-emerald-400/10"
          >
            <div className="flex items-center gap-2 text-xs text-emerald-300">
              <Check className="size-4" />
              What we draft
            </div>
            <div className="mt-4 space-y-2 text-sm text-white/80 leading-relaxed">
              <div className="text-white/50">
                Subject: deploy-aware anomalies for the Stripe Apps team
              </div>
              <div>Hey Maya —</div>
              <div>
                Saw the Stripe Apps SDK launch last Tuesday. The doc on
                webhook reliability hinted at the same thing our other
                K8s-shop customers ran into: when a deploy goes out at 3am,
                you don't find the regression until the morning. We built
                runtime anomaly correlation that catches it in the first 90s
                post-deploy.
              </div>
              <div>
                Worth a 15-min look while the SDK is still settling? I can
                send our Stripe-shaped writeup either way.
              </div>
              <div className="text-white/50">— Mokshith</div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
