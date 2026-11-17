import CandidateWorkspace from "./CandidateWorkspace";

export default async function SinglePage({ params, searchParams }: {
  params: Promise<{ roomId: string }>;
  searchParams: Promise<{ member?: string }>;
}) {
  const { roomId } = await params;
  const { member } = await searchParams;
  const localParticipation = process.env.NEXT_PUBLIC_LOCAL_ROOMS === "1" && /^\d+$/.test(roomId);
  return <CandidateWorkspace key={`${roomId}-${member}`} roomId={roomId} initialMemberId={member ?? "demo-yutti"} localParticipation={localParticipation} />;
}
