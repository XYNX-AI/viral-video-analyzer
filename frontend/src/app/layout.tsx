import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "爆款视频拆解器",
  description: "AI 驱动的短视频拉片分析工具",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
