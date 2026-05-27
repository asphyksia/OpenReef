"use client";

import { useEffect, useState } from "react";
import { getBalance, createCheckoutSession, devAddCredits } from "@/lib/api";
import type { BalanceResponse } from "@/types";

const presetAmounts = [10, 25, 50, 100];

export default function CreditsPage() {
  const [balance, setBalance] = useState<BalanceResponse | null>(null);
  const [customAmount, setCustomAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [devMode, setDevMode] = useState(false);
  const [devLoading, setDevLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getBalance()
      .then(setBalance)
      .catch((err) => {
        console.error("getBalance failed:", err);
        setError(err.message || "Failed to load balance");
      });
  }, []);

  async function handleCheckout(amount: number) {
    setError("");
    setLoading(true);
    try {
      const { checkout_url } = await createCheckoutSession(amount);
      window.location.href = checkout_url;
    } catch (err) {
      // If Stripe fails, fallback to dev mode
      if (err instanceof Error && (err.message.includes("placeholder") || err.message.includes("API keys") || err.message.includes("dev mode"))) {
        setDevMode(true);
        setError("");
      } else {
        setError(err instanceof Error ? err.message : "Failed to create checkout");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleDevAdd(amount: number) {
    setError("");
    setDevLoading(true);
    try {
      const result = await devAddCredits(amount);
      setBalance({ balance: result.balance, currency: "USD" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add credits");
    } finally {
      setDevLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-2xl font-bold">Credits</h1>

      {balance && (
        <div className="bg-card border rounded-lg p-6 text-center">
          <div className="text-sm text-muted-foreground">Current Balance</div>
          <div className="text-4xl font-bold mt-2">${balance.balance.toFixed(2)}</div>
          <div className="text-xs text-muted-foreground mt-1">USD</div>
        </div>
      )}

      {devMode ? (
        <div className="border rounded-lg p-6 bg-yellow-50 dark:bg-yellow-950/20 border-yellow-200">
          <h2 className="text-sm font-semibold mb-1">Development Mode</h2>
          <p className="text-xs text-muted-foreground mb-4">
            Stripe is not configured. Credits are added locally for testing.
          </p>

          {error && (
            <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-md mb-3">{error}</div>
          )}

          <div className="grid grid-cols-2 gap-3 mb-4">
            {presetAmounts.map((amount) => (
              <button
                key={amount}
                onClick={() => handleDevAdd(amount)}
                disabled={devLoading}
                className="border rounded-lg p-4 text-center hover:bg-accent disabled:opacity-50"
              >
                <div className="text-xl font-bold">${amount}</div>
                <div className="text-xs text-muted-foreground">add credits</div>
              </button>
            ))}
          </div>

          <div className="flex gap-3">
            <input
              type="number"
              min={1}
              step={1}
              value={customAmount}
              onChange={(e) => setCustomAmount(e.target.value)}
              placeholder="Custom amount"
              className="flex-1 border rounded-md px-3 py-2 text-sm"
            />
            <button
              onClick={() => {
                const n = parseFloat(customAmount);
                if (n > 0) handleDevAdd(n);
              }}
              disabled={devLoading}
              className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
            >
              {devLoading ? "Adding..." : "Add"}
            </button>
          </div>
        </div>
      ) : (
        <div className="border rounded-lg p-6">
          <h2 className="text-sm font-semibold mb-3">Add Credits</h2>

          {error && (
            <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-md mb-3">{error}</div>
          )}

          <div className="grid grid-cols-2 gap-3 mb-4">
            {presetAmounts.map((amount) => (
              <button
                key={amount}
                onClick={() => handleCheckout(amount)}
                disabled={loading}
                className="border rounded-lg p-4 text-center hover:bg-accent disabled:opacity-50"
              >
                <div className="text-xl font-bold">${amount}</div>
                <div className="text-xs text-muted-foreground">credits</div>
              </button>
            ))}
          </div>

          <div className="flex gap-3">
            <input
              type="number"
              min={1}
              step={1}
              value={customAmount}
              onChange={(e) => setCustomAmount(e.target.value)}
              placeholder="Custom amount"
              className="flex-1 border rounded-md px-3 py-2 text-sm"
            />
            <button
              onClick={() => {
                const n = parseFloat(customAmount);
                if (n > 0) handleCheckout(n);
              }}
              disabled={loading}
              className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
            >
              {loading ? "Redirecting..." : "Add"}
            </button>
          </div>
        </div>
      )}

      <div className="text-xs text-muted-foreground">
        <p>Payments are processed securely via Stripe. Credits are added to your account instantly.</p>
        <p className="mt-2">
          Need help?{" "}
          <a href="https://t.me/openreef" target="_blank" className="text-primary hover:underline">
            Contact us on Telegram
          </a>
        </p>
      </div>
    </div>
  );
}
