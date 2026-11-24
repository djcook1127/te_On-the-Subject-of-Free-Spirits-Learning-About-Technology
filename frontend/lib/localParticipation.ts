// このPC内のローカル参加検証専用。識別用Cookieの値はJavaScriptへ渡さない。
export type LocalMember = { id: string; name: string };
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request(roomId: string, nickname?: string, inviteToken?: string): Promise<LocalMember | null> {
  const res = await fetch(`${API}/api/rooms/${encodeURIComponent(roomId)}/${nickname === undefined ? "me" : "members"}`, {
    method: nickname === undefined ? "GET" : "POST",
    credentials: "include",
    cache: "no-store",
    ...(nickname === undefined ? {} : {
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nickname, invite_token: inviteToken }),
    }),
  });
  if (nickname === undefined && res.status === 401) return null;
  if (!res.ok) {
    const error = await res.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : "参加情報を確認できません。再試行してください。");
  }
  return res.json();
}

export const getLocalMember = (roomId: string) => request(roomId);
export const joinLocalRoom = (roomId: string, nickname: string, inviteToken?: string) => request(roomId, nickname, inviteToken);
