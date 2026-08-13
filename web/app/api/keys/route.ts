import { NextResponse } from "next/server";
import { maskKey } from "@/lib/api";

export async function GET() {
  return NextResponse.json(maskKey());
}

export async function POST() {
  const key = process.env.ROUTER_API_KEY || "";
  if (!key) {
    return NextResponse.json({ error: "ROUTER_API_KEY is not set" }, { status: 404 });
  }
  return NextResponse.json({ key });
}
