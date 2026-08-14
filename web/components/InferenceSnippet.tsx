"use client";

import { toast } from "sonner";
import { CopyIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

const CURL = `curl -X POST "http://127.0.0.1:8000/v1/chat/completions" \\
    -H "Content-Type: application/json" \\
    -H "Authorization: Bearer <YOUR_API_KEY>" \\
    -d '{
  "model": "router/auto",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "Extract the key people, companies, and locations from this text: \\"Acme Corp hired Jane Doe as CTO on April 11, 2026 in Berlin.\\""
    }
  ],
  "stream": false
}'`;

export function InferenceSnippet() {
  return (
    <Card id="run-inference" className="gap-0 py-0">
      <CardHeader className="flex flex-row items-center gap-2.5 border-b py-4">
        <span className="text-sm text-muted-foreground">
          Routed through{" "}
          <span className="font-mono text-[12.5px] text-highlight">router/auto</span>
        </span>
        <span className="ml-auto flex items-center gap-2.5">
          <Badge variant="outline" className="h-8 rounded-lg px-3 font-normal">
            local <span className="font-semibold tracking-wider">GATEWAY</span>
          </Badge>
          <Button
            variant="outline"
            size="sm"
            type="button"
            onClick={() => {
              navigator.clipboard.writeText(CURL).then(() => toast.success("Copied"));
            }}
          >
            <CopyIcon data-icon="inline-start" />
            Copy
          </Button>
        </span>
      </CardHeader>
      <CardContent className="px-0">
        <pre className="overflow-x-auto px-[26px] py-[22px] font-mono text-[13px] leading-[1.65] text-muted-foreground">
          curl -X POST <span className="text-[color:var(--code-green)]">&quot;http://127.0.0.1:8000/v1/chat/completions&quot;</span> \
    -H <span className="text-[color:var(--code-green)]">&quot;Content-Type: application/json&quot;</span> \
    -H <span className="text-[color:var(--code-green)]">&quot;Authorization: Bearer &lt;YOUR_API_KEY&gt;&quot;</span> \
    -d <span className="text-[color:var(--code-green)]">
            {`'{
  "model": "`}
            <span className="text-highlight">router/auto</span>
            {`",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "Extract the key people, companies, and locations from this text: \\"Acme Corp hired Jane Doe as CTO on April 11, 2026 in Berlin.\\""
    }
  ],
  "stream": false
}'`}
          </span>
        </pre>
      </CardContent>
    </Card>
  );
}
