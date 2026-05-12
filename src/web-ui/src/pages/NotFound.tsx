import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-neutral-50 text-black">
      <p className="text-sm uppercase tracking-widest text-black/40">404</p>
      <h1 className="mt-3 text-4xl font-semibold tracking-tight">
        Page not found
      </h1>
      <Link
        to="/"
        className="mt-6 text-sm text-black/60 underline underline-offset-4 hover:text-black"
      >
        ← back to home
      </Link>
    </div>
  );
}
