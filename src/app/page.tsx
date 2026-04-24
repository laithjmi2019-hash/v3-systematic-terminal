"use client";

import { Navbar } from "@/components/navbar";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const [ticker, setTicker] = useState("");
  const router = useRouter();

  const handleSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && ticker.trim()) {
      router.push(`/stock/${ticker.trim().toUpperCase()}`);
    }
  };

  return (
    <main className="flex min-h-screen flex-col">
      <Navbar />
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-6 max-w-3xl mx-auto">
        <h1 className="text-4xl font-bold font-mono tracking-tighter sm:text-5xl">
          Systematic Investment Analysis
        </h1>
        <p className="text-muted-foreground text-lg">
          Institutional-grade platform enforcing strict pass/fail logic across 5 quantitative pillars. Eliminate emotional investing.
        </p>

        <div className="w-full max-w-md mx-auto relative mt-8">
            <input 
              type="text" 
              placeholder="Enter ticker (e.g., AAPL)..." 
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              onKeyDown={handleSearch}
              className="w-full bg-muted/50 border-input border rounded-lg px-4 py-3 text-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition"
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground bg-background px-2 py-1 rounded border">
              Enter
            </div>
        </div>
      </div>
    </main>
  );
}
