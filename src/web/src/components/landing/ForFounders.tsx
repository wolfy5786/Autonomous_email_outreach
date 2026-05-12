import { motion } from "framer-motion";
import { Check } from "lucide-react";

const fits = [
  "You're pre-seed to Series A and still doing outbound yourself.",
  "You've tried Apollo / Lemlist / Instantly and the templates feel cheap.",
  "You don't want to hire an SDR — but you do want pipeline.",
  "You know your ICP cold but don't have hours to research each prospect.",
  "You'd rather send 30 great emails than 300 generic ones.",
];

export function ForFounders() {
  return (
    <section className="bg-[#070710] text-white py-28 border-t border-white/5">
      <div className="max-w-5xl mx-auto px-6">
        <div className="grid md:grid-cols-2 gap-16 items-center">
          <div>
            <p className="text-sm uppercase tracking-widest text-white/40 mb-4">
              Who it's for
            </p>
            <h2 className="text-4xl md:text-5xl font-semibold tracking-tight">
              Built for B2B SaaS founders.
            </h2>
            <p className="mt-6 text-lg text-white/60 leading-relaxed">
              Not for outbound agencies. Not for 50-rep SDR floors. For the
              founder who knows their customer better than anyone — and just
              needs a way to reach more of them without hating their inbox.
            </p>
          </div>

          <ul className="space-y-4">
            {fits.map((f, i) => (
              <motion.li
                key={f}
                initial={{ opacity: 0, x: 20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
                className="flex items-start gap-3"
              >
                <div className="mt-1 size-5 rounded-full bg-white/10 flex items-center justify-center shrink-0">
                  <Check className="size-3 text-white" />
                </div>
                <span className="text-white/80 leading-relaxed">{f}</span>
              </motion.li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
