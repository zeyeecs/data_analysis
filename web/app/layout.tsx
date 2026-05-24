import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "商品价格趋势",
  description: "合并 F / R / V 全渠道已售样本，查看商品价格走势",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
