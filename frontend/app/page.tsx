import Link from "next/link";

/** Home page — entry point for the Process Intelligence frontend. */
export default function Home() {
  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-semibold mb-2">Process Intelligence</h1>
      <p className="text-gray-600 mb-6">
        Upload customer artifacts and review extracted process knowledge.
      </p>
      <div className="flex gap-3">
        <Link
          href="/runs/upload"
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
        >
          Upload artifact
        </Link>
        <Link
          href="/health"
          className="px-4 py-2 border border-gray-300 text-sm rounded hover:bg-gray-100 transition-colors"
        >
          Check health
        </Link>
      </div>
    </div>
  );
}
