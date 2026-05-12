import { Nav } from "@/components/landing/Nav";
import { Hero } from "@/components/landing/Hero";
import { Problem } from "@/components/landing/Problem";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { ForFounders } from "@/components/landing/ForFounders";
import { Features } from "@/components/landing/Features";
import { Compare } from "@/components/landing/Compare";
import { CTA } from "@/components/landing/CTA";
import { Footer } from "@/components/landing/Footer";

export default function Landing() {
  return (
    <div className="min-h-screen bg-black antialiased selection:bg-white/15">
      <Nav />
      <main>
        <Hero />
        <Problem />
        <HowItWorks />
        <ForFounders />
        <Features />
        <Compare />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
