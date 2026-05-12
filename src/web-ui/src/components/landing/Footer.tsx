export function Footer() {
  return (
    <footer className="bg-black text-white/50 border-t border-white/5">
      <div className="max-w-6xl mx-auto px-6 py-12 flex flex-col md:flex-row items-center justify-between gap-4 text-sm">
        <div className="font-semibold tracking-tight text-white">
          Outreach<span className="text-white/40">.</span>
        </div>
        <div className="flex items-center gap-6">
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
            Early access
          </a>
        </div>
        <div className="text-white/30">© 2026</div>
      </div>
    </footer>
  );
}
