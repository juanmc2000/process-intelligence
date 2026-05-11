import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Process Intelligence",
  description: "Review and explore extracted process intelligence",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6">
          <span className="font-semibold text-sm tracking-tight">
            Process Intelligence
          </span>
          <Link
            href="/"
            className="text-sm text-gray-600 hover:text-gray-900 transition-colors"
          >
            Runs
          </Link>
          <Link
            href="/health"
            className="text-sm text-gray-600 hover:text-gray-900 transition-colors"
          >
            Health
          </Link>
        </nav>
        <main className="px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
