"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type UploadState = "idle" | "uploading" | "done" | "error";

/**
 * Upload screen — lets the user select a file and start a processing run.
 * Navigates to the run status page on success.
 */
export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>("idle");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setState("uploading");
    setError(null);

    try {
      const res = await api.upload(file);
      setState("done");
      router.push(`/runs/${res.run_id}`);
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  return (
    <div className="max-w-md">
      <h1 className="text-xl font-semibold mb-1">Upload artifact</h1>
      <p className="text-sm text-gray-500 mb-6">
        Supported formats: PDF, DOCX, EML, ZIP, TXT, MD
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <input
          type="file"
          accept=".pdf,.docx,.eml,.zip,.txt,.md"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4
                     file:rounded file:border-0 file:text-sm file:font-medium
                     file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          disabled={state === "uploading"}
        />

        <button
          type="submit"
          disabled={!file || state === "uploading"}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded
                     hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {state === "uploading" ? "Uploading…" : "Upload and start run"}
        </button>

        {state === "error" && error && (
          <p className="text-sm text-red-600">{error}</p>
        )}
      </form>
    </div>
  );
}
