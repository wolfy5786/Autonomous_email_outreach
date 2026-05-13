import { ObservabilityDashboard } from "@/components/app/ObservabilityDashboard";

export default function Observability() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Observability</h1>
        <p className="mt-2 text-black/60 text-sm">
          All trace events across every campaign. Auto-refreshes.
        </p>
      </div>
      <ObservabilityDashboard />
    </div>
  );
}
