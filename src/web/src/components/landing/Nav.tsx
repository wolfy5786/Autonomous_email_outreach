import { Button } from "@/components/ui/button";

export function Nav() {
  return (
    <nav className="fixed top-0 inset-x-0 z-50 backdrop-blur-md bg-black/40 border-b border-white/10">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <a href="#top" className="text-white font-semibold tracking-tight">
          Outreach
          <span className="text-white/40">.</span>
        </a>
        <div className="hidden md:flex items-center gap-8 text-sm text-white/70">
          <a href="#problem" className="hover:text-white transition">
            Why
          </a>
          <a href="#how" className="hover:text-white transition">
            How it works
          </a>
          <a href="#features" className="hover:text-white transition">
            Features
          </a>
          <a href="#access" className="hover:text-white transition">
            Pricing
          </a>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="invertedOutline" size="sm" asChild>
            <a href="/app">Open app</a>
          </Button>
          <Button variant="glow" size="sm" asChild>
            <a href="#access">Get early access</a>
          </Button>
        </div>
      </div>
    </nav>
  );
}
