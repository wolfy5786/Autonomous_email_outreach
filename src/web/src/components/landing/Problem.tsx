import { motion } from "framer-motion";

const pains = [
  {
    stat: "1.7%",
    label: "Average cold email reply rate in 2024",
    body: "Generic templates trip every spam filter and bore every prospect. Most outbound is a numbers game everyone loses.",
  },
  {
    stat: "70%",
    label: "Of selling time founders spend on prospecting",
    body: "Researching a single company well takes 20 minutes. Doing it for 50 prospects a week means there's no time left to actually sell.",
  },
  {
    stat: "$84k",
    label: "Fully loaded cost of your first SDR",
    body: "Hiring an SDR before $1M ARR is a luxury. Until you have one, you're the SDR — and your time is the most expensive in the company.",
  },
];

export function Problem() {
  return (
    <section id="problem" className="bg-black text-white py-28 border-t border-white/5">
      <div className="max-w-6xl mx-auto px-6">
        <div className="max-w-2xl">
          <p className="text-sm uppercase tracking-widest text-white/40 mb-4">
            The problem
          </p>
          <h2 className="text-4xl md:text-5xl font-semibold tracking-tight">
            Outbound is broken.
          </h2>
          <p className="mt-6 text-lg text-white/60">
            Mass-blast outbound has trained every inbox to ignore strangers.
            Real personalization works — but no one has time for it.
          </p>
        </div>

        <div className="mt-16 grid md:grid-cols-3 gap-8">
          {pains.map((p, i) => (
            <motion.div
              key={p.stat}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="rounded-2xl border border-white/10 bg-white/[0.02] p-8"
            >
              <div className="text-5xl font-semibold tracking-tight bg-clip-text text-transparent bg-gradient-to-br from-white to-white/30">
                {p.stat}
              </div>
              <div className="mt-2 text-sm text-white/50">{p.label}</div>
              <p className="mt-5 text-white/70 text-sm leading-relaxed">
                {p.body}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
