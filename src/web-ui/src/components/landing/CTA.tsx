import { FormEvent, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Check } from "lucide-react";
import { Button } from "@/components/ui/button";

export function CTA() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!email) return;
    // TODO: wire to gateway POST /api/early-access when the backend lands.
    setSubmitted(true);
  }

  return (
    <section
      id="access"
      className="relative overflow-hidden bg-black text-white py-32 border-t border-white/5"
    >
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(50% 50% at 50% 50%, rgba(99,102,241,0.25) 0%, rgba(0,0,0,0) 70%)",
        }}
      />
      <div className="relative max-w-3xl mx-auto px-6 text-center">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-4xl md:text-6xl font-semibold tracking-tight"
        >
          Get your time back.
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mt-6 text-lg text-white/60 max-w-xl mx-auto"
        >
          We're in early access. Drop your email — we'll send you a single
          sample draft for a prospect you'd actually want to email.
        </motion.p>

        {submitted ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-10 inline-flex items-center gap-2 px-6 py-3 rounded-md bg-emerald-500/10 border border-emerald-400/30 text-emerald-200"
          >
            <Check className="size-4" />
            You're on the list. We'll be in touch.
          </motion.div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="mt-10 flex flex-col sm:flex-row gap-3 max-w-md mx-auto"
          >
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="founder@yourstartup.com"
              className="flex-1 h-14 px-5 rounded-md bg-white/5 border border-white/15 text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-indigo-400/40"
            />
            <Button type="submit" variant="glow" size="xl">
              Request access
              <ArrowRight className="size-4" />
            </Button>
          </form>
        )}
        <p className="mt-6 text-xs text-white/40">
          Real personalized sample. No mass sequence. No spam.
        </p>
      </div>
    </section>
  );
}
