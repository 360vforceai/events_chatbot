export default function Page({ params }: { params: { id: string } }) {
  return <h1 className="text-2xl font-semibold">Event: {params.id}</h1>;
}
