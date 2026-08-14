import Link from "next/link";
import { KeyRoundIcon } from "lucide-react";
import { KeyPill } from "@/components/KeyPill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { maskKey } from "@/lib/api";

export default function KeysPage() {
  const masked = maskKey();
  return (
    <div className="mx-auto max-w-[1360px] px-11 pt-[26px] pb-[120px]">
      <div className="mb-[18px]">
        <h2 className="text-xl font-semibold">API keys</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Router gateway key only. This is not AIand org key admin.
        </p>
      </div>
      <Card className="max-w-[640px] gap-0 py-0">
        <CardHeader className="pt-[22px] pb-3.5">
          <CardTitle className="flex items-center gap-2 text-[13px] font-medium text-muted-foreground">
            <KeyRoundIcon />
            ROUTER_API_KEY
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 pb-0">
          <KeyPill masked={masked} />
          <CardDescription>
            Masked preview of the Next server env var <strong>ROUTER_API_KEY</strong>
            {masked.set ? "" : " (not set)"}. The raw value is not in the client bundle. Copy asks the
            server for it. Point clients at <code>http://127.0.0.1:8000</code> with this key — never{" "}
            <code>AIAND_API_KEY</code>.
          </CardDescription>
        </CardContent>
        <CardFooter className="mt-6 justify-start gap-3 border-0 bg-transparent">
          <Button render={<Link href="/routers/auto#run-inference" />} nativeButton={false} variant="outline" className="h-10">
            Integrate curl
          </Button>
          <Button render={<Link href="/playground" />} nativeButton={false} className="h-10">
            Try in playground
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
