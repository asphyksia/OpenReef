import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = {
  title: "OpenReef - Fine-tuning on OpenGPU Network",
  description: "Simple, affordable AI fine-tuning on decentralized compute.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased transition-colors duration-300">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
