/** Embeds the campaign timeline (same data the standalone observability service serves).
 *  Real implementation lands alongside step 5.
 */
export default function Observability() {
  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Observability</h1>
      <p className="mt-2 text-black/60">
        End-to-end campaign trace timeline. Wired in step 5.
      </p>
    </div>
  );
}
