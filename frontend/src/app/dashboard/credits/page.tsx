"use client";

import { useEffect, useState } from "react";
import { getBalance, createCheckoutSession, devAddCredits } from "@/lib/api";
import type { BalanceResponse } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/page-header";
import { Loader2, Coins, CreditCard, AlertCircle, Zap, Shield } from "lucide-react";

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

  const handleAmount = (amount: number) => {
    if (devMode) {
      handleDevAdd(amount);
    } else {
      handleCheckout(amount);
    }
  };

  return (
    <div className="space-y-6 max-w-xl">
      <PageHeader
        title="Credits"
        description="Manage your account balance"
      />

      {balance && (
        <Card>
          <CardHeader className="text-center pb-2">
            <CardTitle className="flex items-center justify-center gap-2">
              <Coins className="h-5 w-5" />
              Current Balance
            </CardTitle>
          </CardHeader>
          <CardContent className="text-center">
            <div className="text-4xl font-bold">${balance.balance.toFixed(2)}</div>
            <div className="text-sm text-muted-foreground mt-1">USD</div>
          </CardContent>
        </Card>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard className="h-5 w-5" />
            Add Credits
          </CardTitle>
          {devMode && (
            <CardDescription className="text-yellow-600 dark:text-yellow-400">
              Development Mode — Credits added locally for testing
            </CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            {presetAmounts.map((amount) => (
              <Button
                key={amount}
                variant="outline"
                className="h-20 flex flex-col gap-1"
                onClick={() => handleAmount(amount)}
                disabled={loading || devLoading}
              >
                <span className="text-xl font-bold">${amount}</span>
                <span className="text-xs text-muted-foreground">
                  {devMode ? "add credits" : "credits"}
                </span>
              </Button>
            ))}
          </div>

          <Separator />

          <div className="flex gap-3">
            <Input
              type="number"
              min={1}
              step={1}
              value={customAmount}
              onChange={(e) => setCustomAmount(e.target.value)}
              placeholder="Custom amount"
            />
            <Button
              onClick={() => {
                const n = parseFloat(customAmount);
                if (n > 0) handleAmount(n);
              }}
              disabled={loading || devLoading}
            >
              {(loading || devLoading) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {loading ? "Redirecting..." : devLoading ? "Adding..." : "Add"}
            </Button>
          </div>
        </CardContent>
        <CardFooter className="flex flex-col items-start gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Shield className="h-3 w-3" />
            Payments processed securely via Stripe
          </div>
          <div className="flex items-center gap-1">
            <Zap className="h-3 w-3" />
            Credits added instantly
          </div>
        </CardFooter>
      </Card>

      <div className="text-xs text-muted-foreground">
        Need help?{" "}
        <a href="https://t.me/openreef" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          Contact us on Telegram
        </a>
      </div>
    </div>
  );
}
