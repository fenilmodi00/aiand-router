"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutGridIcon,
  GitForkIcon,
  LayersIcon,
  KeyRoundIcon,
  BarChart3Icon,
  SettingsIcon,
  ChevronsLeftIcon,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from "@/components/ui/sidebar";

const itemClass = "size-[38px]! justify-center rounded-[9px] p-0! [&>svg]:size-[17px]";

export function Rail({
  routers = 0,
  models = 0,
  keys = 0,
}: {
  routers?: number;
  models?: number;
  keys?: number;
}) {
  const path = usePathname();
  const onRouters = path === "/routers" || path.startsWith("/routers/");

  return (
    <Sidebar collapsible="icon" variant="sidebar" className="border-sidebar-border">
      <SidebarHeader className="items-center p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              render={<Link href="/routers" />}
              tooltip="Home"
              className="mb-2 size-8 justify-center rounded-[9px] bg-sidebar-primary p-0 text-[15px] font-bold text-sidebar-primary-foreground hover:bg-sidebar-primary hover:text-sidebar-primary-foreground"
            >
              A
              <span className="sr-only">Home</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup className="items-center p-2">
          <SidebarGroupContent>
            <SidebarMenu className="items-center gap-1.5">
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/routers" />}
                  tooltip="Overview"
                  className={itemClass}
                >
                  <LayoutGridIcon />
                  <span className="sr-only">Overview</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/routers" />}
                  isActive={onRouters}
                  tooltip="Routers"
                  className={itemClass}
                >
                  <GitForkIcon />
                  <span className="sr-only">Routers</span>
                </SidebarMenuButton>
                {routers > 0 ? (
                  <SidebarMenuBadge className="top-px -right-0.5 flex size-[15px] min-w-[15px] rounded-lg border border-sidebar-border bg-sidebar-accent p-0 font-mono text-[9px] leading-[14px] group-data-[collapsible=icon]:flex">
                    {routers}
                  </SidebarMenuBadge>
                ) : null}
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/models" />}
                  isActive={path === "/models"}
                  tooltip="Models"
                  className={itemClass}
                >
                  <LayersIcon />
                  <span className="sr-only">Models</span>
                </SidebarMenuButton>
                {models > 0 ? (
                  <SidebarMenuBadge className="top-px -right-0.5 flex size-[15px] min-w-[15px] rounded-lg border border-sidebar-border bg-sidebar-accent p-0 font-mono text-[9px] leading-[14px] group-data-[collapsible=icon]:flex">
                    {models}
                  </SidebarMenuBadge>
                ) : null}
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/keys" />}
                  isActive={path === "/keys"}
                  tooltip="API keys"
                  className={itemClass}
                >
                  <KeyRoundIcon />
                  <span className="sr-only">API keys</span>
                </SidebarMenuButton>
                {keys > 0 ? (
                  <SidebarMenuBadge className="top-px -right-0.5 flex size-[15px] min-w-[15px] rounded-lg border border-sidebar-border bg-sidebar-accent p-0 font-mono text-[9px] leading-[14px] group-data-[collapsible=icon]:flex">
                    {keys}
                  </SidebarMenuBadge>
                ) : null}
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  render={<Link href="/usage" />}
                  isActive={path === "/usage"}
                  tooltip="Usage"
                  className={itemClass}
                >
                  <BarChart3Icon />
                  <span className="sr-only">Usage</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="items-center p-2">
        <SidebarMenu className="items-center gap-1.5">
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="Settings" className={itemClass}>
              <SettingsIcon />
              <span className="sr-only">Settings</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarTrigger className="size-[38px] text-muted-foreground">
              <ChevronsLeftIcon />
            </SidebarTrigger>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
