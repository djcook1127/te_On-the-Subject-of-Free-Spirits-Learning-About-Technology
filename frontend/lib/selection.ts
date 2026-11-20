import type { Gift } from "./api";

export type ProposalProduct = { productId: string; reason: string; gift: Gift };
export type Selection = {
  room: { id: string; title: string; budgetTotal: number };
  phase: "collecting" | "voting" | "decided";
  catalogSource: "demo" | "shared";
  me: { id: number; name: string; isOrganizer: boolean; canPropose: boolean; submitted: boolean; version: number };
  members: { id: number; name: string; canPropose: boolean }[];
  progress: { designated: number; submitted: number };
  notes: { id: number; kind: string; text: string }[];
  ownProducts: ProposalProduct[];
  candidates: { gift: Gift; reasons: string[]; totalStars: number; voters: number; myStars: number | null; comments: { id: number; text: string }[] }[];
  decision: { mode: "single" | "catalog"; products: Gift[]; payment: "demo" } | null;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ParticipationRequired extends Error {}

export async function selectionRequest<T>(roomId: string, path = "", method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`${API}/api/rooms/${encodeURIComponent(roomId)}/selection${path}`, {
    method, credentials: "include", cache: "no-store",
    ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  });
  if (response.status === 401) throw new ParticipationRequired("名前を入力して参加してください");
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(typeof data?.detail === "string" ? data.detail : "操作できませんでした。入力と接続を確認してください。");
  }
  return response.json();
}
