import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "汽车零部件智能采购助手",
  description: "面向乘用车售后业务的汽车零部件适配、比价与采购助手",
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
