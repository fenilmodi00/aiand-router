import { getModels } from "@/lib/api";

export default async function ModelsPage() {
  const res = await getModels();
  const rows = res.data?.data ?? [];

  return (
    <div className="content">
      <div className="section-head" style={{ marginTop: 0 }}>
        <div>
          <h2 className="big">Models</h2>
          <div className="card-sub">
            Gateway catalog. AA index is a public prior (not_aiand), not a measured quality score.
          </div>
        </div>
      </div>
      {!res.ok ? (
        <div className="empty" style={{ height: 120, marginBottom: 16 }}>
          Could not load /v1/models ({res.error}).
        </div>
      ) : null}
      <div className="table">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Enabled</th>
              <th className="r">AA prior</th>
              <th>Source</th>
              <th>Owned by</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="empty-row">
                  No models returned.
                </td>
              </tr>
            ) : (
              rows.map((m) => (
                <tr key={m.id}>
                  <td>
                    {m.id}
                    {m.id === "router/auto" ? <div className="muted">virtual</div> : null}
                  </td>
                  <td>{m.id === "router/auto" ? "—" : m.enabled ? "yes" : "no"}</td>
                  <td className="r">{m.aa_index == null ? "—" : m.aa_index}</td>
                  <td>{m.aa_source || (m.id === "router/auto" ? "—" : "not_aiand")}</td>
                  <td>{m.owned_by || "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
