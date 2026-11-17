// Next.jsの動作を設定し、画面とAPIで共有する祝日データを読み込めるようにするファイルです。
import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // 画面とAPIの共通祝日データ（../shared）を読み込む。
  turbopack: { root: path.resolve(__dirname, "..") },
};

export default nextConfig;
