import CandidateWorkspace from "./CandidateWorkspace";

export default async function SinglePage({ params, searchParams }: {
  params: Promise<{ roomId: string }>;
  searchParams: Promise<{ member?: string }>;
}) {
  const { roomId } = await params;
  const { member } = await searchParams;
  return <CandidateWorkspace key={`${roomId}-${member}`} roomId={roomId} initialMemberId={member ?? "demo-yutti"} />;
}
