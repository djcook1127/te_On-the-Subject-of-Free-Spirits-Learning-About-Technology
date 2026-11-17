// B担当の下書き用。A担当と接続する際は docs/b-candidate-contract.md を先に合意する。
import type { Gift } from "./api";

export type CandidateSlot =
  | { kind: "product"; productId: string; reason: string; gift: Gift; available?: boolean }
  | { kind: "hint"; text: string };
export type DemoMember = { id: string; name: string };
export type CandidateDraft = {
  room: { id: string; title: string; budgetTotal: number };
  member: DemoMember;
  demoMembers: DemoMember[];
  catalogSource?: "demo" | "shared";
  localParticipation?: boolean;
  version: number;
  slots: CandidateSlot[];
};
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request(roomId: string, memberId: string, body?: { version: number; slots: CandidateSlot[] }, localParticipation = false): Promise<CandidateDraft> {
  const res = await fetch(`${API}/api/rooms/${encodeURIComponent(roomId)}/candidate-draft`, {
    method: body ? "PUT" : "GET",
    headers: { ...(!localParticipation ? { "X-Demo-Member": memberId } : {}), ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(localParticipation ? { credentials: "include" as const } : {}),
    cache: "no-store",
    ...(body ? { body: JSON.stringify({
      version: body.version,
      slots: body.slots.map(slot => slot.kind === "hint"
        ? { kind: "hint", text: slot.text }
        : { kind: "product", productId: slot.productId, reason: slot.reason }),
    }) } : {}),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}：入力内容を確認してください`);
  }
  return res.json();
}

export const loadCandidateDraft = (roomId: string, memberId: string, localParticipation = false) => request(roomId, memberId, undefined, localParticipation);
export const saveCandidateDraft = (roomId: string, memberId: string, version: number, slots: CandidateSlot[], localParticipation = false) => request(roomId, memberId, { version, slots }, localParticipation);
