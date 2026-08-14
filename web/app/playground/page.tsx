import Link from "next/link";
import { ChevronLeftIcon } from "lucide-react";
import { Playground } from "@/components/Playground";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { getModels } from "@/lib/api";

export default async function PlaygroundPage() {
  const res = await getModels();
  const models = (res.data?.data ?? []).filter((m) => m.id !== "router/auto");

  return (
    <div className="mx-auto max-w-[1360px] px-11 pt-[26px] pb-[120px]">
      <Breadcrumb className="mb-[22px]">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink render={<Link href="/routers/auto" />} className="inline-flex size-[22px] items-center justify-center rounded-md hover:bg-muted">
              <ChevronLeftIcon />
              <span className="sr-only">Back</span>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbItem>
            <BreadcrumbLink render={<Link href="/routers" />}>Routers</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink render={<Link href="/routers/auto" />}>router/auto</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Playground</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <Playground models={models} loadError={res.ok ? null : res.error} />
    </div>
  );
}
