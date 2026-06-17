import type { RemixiconComponentType } from "@remixicon/react";
import {
  RiHome2Line,
  RiListCheck,
  RiRobot2Line,
  RiSettings5Line,
} from "@remixicon/react";

import { siteConfig } from "@/app/siteConfig";

export type NavigationItem = {
  name: string;
  href: string;
  icon: RemixiconComponentType;
  matchPrefix?: boolean;
};

export const coreNavigation: NavigationItem[] = [
  { name: "概览", href: siteConfig.baseLinks.overview, icon: RiHome2Line },
  { name: "详情", href: siteConfig.baseLinks.details, icon: RiListCheck },
  {
    name: "AI 任务",
    href: siteConfig.baseLinks.aiTasks,
    icon: RiRobot2Line,
    matchPrefix: true,
  },
  {
    name: "设置",
    href: siteConfig.baseLinks.settings,
    icon: RiSettings5Line,
    matchPrefix: true,
  },
];

export function isNavigationActive(pathname: string, item: NavigationItem): boolean {
  if (item.matchPrefix) {
    return pathname === item.href || pathname.startsWith(`${item.href}/`);
  }
  return pathname === item.href || pathname.startsWith(item.href);
}
