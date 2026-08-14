import { Playground } from "@/components/Playground";
import { getModels } from "@/lib/api";

export default async function PlaygroundWithIdPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const res = await getModels();
  const allModels = res.data?.data ?? [];
  const models = allModels.filter((m) => m.id !== "router/auto");

  return (
    <div className="w-full min-h-screen bg-black">
      <Playground
        models={models}
        initialModelId={id === "025ee19c-e401-4ffc-93d0-0ce9ad9ad16b" ? "router/auto" : id}
        loadError={res.ok ? null : res.error}
      />
    </div>
  );
}
