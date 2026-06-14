import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const geistSans = localFont({ src: "./fonts/GeistVF.woff", variable: "--font-geist-sans", weight: "100 900" });
const geistMono = localFont({ src: "./fonts/GeistMonoVF.woff", variable: "--font-geist-mono", weight: "100 900" });

export const metadata: Metadata = {
  title: "PortDoc AI — Sovereign RAG Console",
  description: "Access-controlled RAG over port security documents. 100% local.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-slate-950 font-sans text-slate-100 antialiased`}>
        <div id="app-root">{children}</div>
      </body>
    </html>
  );
}
