import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">OpenReef</h1>
        <div className="flex gap-4">
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">
            Log in
          </Link>
          <Link
            href="/register"
            className="text-sm bg-primary text-primary-foreground px-4 py-2 rounded-md hover:bg-primary/90"
          >
            Sign up
          </Link>
        </div>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-6 text-center">
        <h2 className="text-4xl font-bold tracking-tight mb-4">
          Fine-tune AI models without the complexity
        </h2>
        <p className="text-lg text-muted-foreground max-w-2xl mb-8">
          Upload your dataset, pick a model, launch a fine-tuning job on decentralized GPU
          infrastructure. No terminal, no YAML, no headaches.
        </p>
        <div className="flex gap-4">
          <Link
            href="/register"
            className="bg-primary text-primary-foreground px-6 py-3 rounded-md font-medium hover:bg-primary/90"
          >
            Get started
          </Link>
          <a
            href="https://t.me/openreef"
            target="_blank"
            rel="noopener noreferrer"
            className="border border-input px-6 py-3 rounded-md font-medium hover:bg-accent"
          >
            Join Telegram
          </a>
        </div>
      </main>

      <footer className="border-t px-6 py-4 text-sm text-muted-foreground">
        <div className="flex justify-between max-w-6xl mx-auto w-full">
          <span>OpenReef MVP</span>
          <a href="https://t.me/openreef" target="_blank" className="hover:text-foreground">
            Support
          </a>
        </div>
      </footer>
    </div>
  );
}
