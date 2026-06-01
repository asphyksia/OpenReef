"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { verifyEmail } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, CheckCircle2, XCircle, Mail } from "lucide-react";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [status, setStatus] = useState<"verifying" | "success" | "error">("verifying");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("No verification token provided.");
      return;
    }

    verifyEmail(token)
      .then(() => {
        setStatus("success");
        setMessage("Email verified successfully! You can now log in.");
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "Verification failed.");
      });
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-background">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1 text-center">
          {status === "verifying" && (
            <>
              <div className="mx-auto mb-2">
                <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
              </div>
              <CardTitle>Verifying your email</CardTitle>
              <CardDescription>Please wait a moment...</CardDescription>
            </>
          )}
          {status === "success" && (
            <>
              <div className="mx-auto mb-2 text-green-600">
                <CheckCircle2 className="h-10 w-10" />
              </div>
              <CardTitle className="text-green-600">Email verified!</CardTitle>
              <CardDescription>{message}</CardDescription>
            </>
          )}
          {status === "error" && (
            <>
              <div className="mx-auto mb-2 text-destructive">
                <XCircle className="h-10 w-10" />
              </div>
              <CardTitle className="text-destructive">Verification failed</CardTitle>
              <CardDescription>{message}</CardDescription>
            </>
          )}
        </CardHeader>
        <CardContent className="text-center">
          {status === "verifying" && (
            <p className="text-sm text-muted-foreground">This should only take a second.</p>
          )}
          {status === "success" && (
            <Button asChild className="w-full">
              <Link href="/login">
                <Mail className="mr-2 h-4 w-4" />
                Log in
              </Link>
            </Button>
          )}
          {status === "error" && (
            <Alert variant="destructive">
              <AlertDescription>
                The link may have expired.{" "}
                <Link href="/login" className="font-medium underline underline-offset-4">
                  Log in to request a new one.
                </Link>
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center">Loading...</div>}>
      <VerifyEmailContent />
    </Suspense>
  );
}
