import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getModels } from "@/lib/api";

export default async function ModelsPage() {
  const res = await getModels();
  const rows = res.data?.data ?? [];

  return (
    <div className="mx-auto max-w-[1360px] px-11 pt-[26px] pb-[120px]">
      <div className="mb-[18px]">
        <h2 className="text-xl font-semibold">Models</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Gateway catalog. AA index is a public prior (not_aiand), not a measured quality score.
        </p>
      </div>
      {!res.ok ? (
        <Alert className="mb-4">
          <AlertTitle>Could not load /v1/models</AlertTitle>
          <AlertDescription>{res.error}</AlertDescription>
        </Alert>
      ) : null}
      <div className="overflow-hidden rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Enabled</TableHead>
              <TableHead className="text-right">AA prior</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Owned by</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="py-12 text-center text-muted-foreground">
                  No models returned.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>
                    {m.id}
                    {m.id === "router/auto" ? (
                      <div className="font-mono text-[11px] text-muted-foreground">virtual</div>
                    ) : null}
                  </TableCell>
                  <TableCell>{m.id === "router/auto" ? "—" : m.enabled ? "yes" : "no"}</TableCell>
                  <TableCell className="text-right">{m.aa_index == null ? "—" : m.aa_index}</TableCell>
                  <TableCell>{m.aa_source || (m.id === "router/auto" ? "—" : "not_aiand")}</TableCell>
                  <TableCell>{m.owned_by || "—"}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
