// Next.jsの動作を設定し、画面とAPIで共有する祝日データを読み込めるようにするファイルです。
import type { NextConfig } from "next";
import path from "node:path";

const upstream = process.env.GIFTIA_API_UPSTREAM;
const apiOrigin = upstream ? new URL(upstream) : null;
if (apiOrigin && (apiOrigin.protocol !== "https:" || apiOrigin.username || apiOrigin.password ||
  apiOrigin.pathname !== "/" || apiOrigin.search || apiOrigin.hash)) {
  throw new Error("GIFTIA_API_UPSTREAMにはFunctionsのHTTPSオリジンを指定してください");
}

const nextConfig: NextConfig = {
  // 画面とAPIの共通祝日データ（../shared）を読み込む。
  turbopack: { root: path.resolve(__dirname, "..") },
  ...(apiOrigin ? {
    env: { NEXT_PUBLIC_API_URL: "", NEXT_PUBLIC_SELECTION_ROOMS: "1" },
    async rewrites() {
      return [{ source: "/api/:path*", destination: `${apiOrigin.origin}/api/:path*` }];
    },
  } : {}),
};

export default nextConfig;
