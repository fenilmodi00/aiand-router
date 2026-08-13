export function StatCard({
  label,
  value,
  sub,
  green,
}: {
  label: string;
  value: string;
  sub?: string;
  green?: boolean;
}) {
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className={`value${green ? " green" : ""}`}>{value}</div>
      {sub ? <div className="sub">{sub}</div> : null}
    </div>
  );
}
