import { Navbar } from "@/components/navbar";

export default function ScreenerPage() {
  return (
    <main className="flex min-h-screen flex-col">
      <Navbar />
      <div className="flex-1 w-full max-w-7xl mx-auto p-4 md:p-8 space-y-8">
        <h1 className="text-3xl font-bold tracking-tight">Stock Screener</h1>
        <p className="text-muted-foreground">Filter the market based on strict systematic scores.</p>
        
        <div className="border rounded-lg p-16 text-center text-muted-foreground bg-muted/10">
           <p>Global screener database mapping in progress...</p>
           <p className="text-sm mt-2">Connect a live PostgreSQL database to cache evaluations and enable advanced filtering.</p>
        </div>
      </div>
    </main>
  );
}
