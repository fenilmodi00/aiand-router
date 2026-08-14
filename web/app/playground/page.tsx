import { Playground } from "@/components/Playground";
import { getModels } from "@/lib/api";

export default async function PlaygroundPage() {
  const res = await getModels();
  const models = (res.data?.data ?? []).filter((m) => m.id !== "router/auto");

  return (
    <div className="w-full min-h-screen bg-black">
      <Playground models={models} initialModelId="router/auto" loadError={res.ok ? null : res.error} />
    </div>
  );
}
