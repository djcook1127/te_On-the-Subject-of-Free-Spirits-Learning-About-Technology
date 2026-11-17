// すべての画面に共通するHTMLの枠、日本語の指定、ページ情報と基本CSSを設定するプログラムです。
import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Giftia",
  description: "ギフトの商品検索",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
