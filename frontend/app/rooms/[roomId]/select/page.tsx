import SelectionWorkspace from "./SelectionWorkspace";

export default async function SelectionPage({ params }: { params: Promise<{ roomId: string }> }) {
  const { roomId } = await params;
  return <SelectionWorkspace key={roomId} roomId={roomId} />;
}
