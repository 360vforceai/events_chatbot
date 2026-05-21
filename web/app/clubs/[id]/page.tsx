export default function Page({ params }: { params: { id: string } }) {
  return <h1 className="text-2xl font-semibold">Club: {params.id}</h1>;
}
