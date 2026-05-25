import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpenReef - Fine-tuning on OpenGPU Network",
  description: "Simple, affordable AI fine-tuning on decentralized compute.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
