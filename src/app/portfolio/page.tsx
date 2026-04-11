import { Navbar } from "@/components/navbar";
import { evaluatePortfolio } from "@/services/engine/portfolio";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Activity, PieChart, TrendingUp } from "lucide-react";

export default async function PortfolioOptimizer() {
  // Mock portfolio state for demonstration. In production, this would be passed in via DB or state.
  const mockHoldings = [
      { ticker: "AAPL", weight: 0.45 },
      { ticker: "MSFT", weight: 0.35 },
      { ticker: "GOOGL", weight: 0.20 }
  ];

  const portfolio = await evaluatePortfolio(mockHoldings);

  return (
    <main className="flex min-h-screen flex-col">
      <Navbar />
      <div className="flex-1 w-full max-w-7xl mx-auto p-4 md:p-8 space-y-6">
        
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b pb-4">
          <div>
            <h1 className="text-4xl font-bold tracking-tight">Portfolio Optimizer</h1>
            <p className="text-muted-foreground mt-1 text-sm">Real-time correlation modeling and risk evaluation.</p>
          </div>
          <div className="flex flex-col items-end">
            <Badge variant="outline" className={`text-2xl px-6 py-2 tracking-widest ${portfolio.portfolioRiskScore > 70 ? 'bg-red-500/20 text-red-500 border-red-500/50' : portfolio.portfolioRiskScore > 40 ? 'bg-yellow-500/20 text-yellow-500 border-yellow-500/50' : 'bg-green-500/20 text-green-500 border-green-500/50'}`}>
              RISK: {portfolio.portfolioRiskScore.toFixed(0)}/100
            </Badge>
          </div>
        </div>

        {portfolio.signals.length > 0 && (
          <div className="border border-orange-500/30 bg-orange-500/10 p-4 rounded-lg flex flex-col gap-2">
            <h4 className="text-orange-500 font-bold uppercase tracking-wider text-xs flex items-center gap-2"><AlertTriangle className="h-4 w-4"/> Portfolio Overexposure Warnings</h4>
            {portfolio.signals.map((s, i) => (
                <div key={i} className="flex gap-2 items-center text-sm text-muted-foreground">
                   <span>{s}</span>
                </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
             <Card className="bg-muted/10 border-muted/30">
               <CardHeader className="pb-2 border-b bg-muted/20">
                 <CardTitle className="text-sm font-medium uppercase tracking-wider flex items-center gap-2"><Activity className="h-4 w-4" /> Avg Correlation</CardTitle>
               </CardHeader>
               <CardContent className="pt-4 flex flex-col gap-1 text-center">
                   <div className="text-4xl font-mono">{portfolio.avgCorrelation.toFixed(2)}</div>
                   <span className="text-xs text-muted-foreground uppercase">{portfolio.avgCorrelation > 0.8 ? 'High Risk Overlap' : portfolio.avgCorrelation > 0.5 ? 'Moderate Correlation' : 'Well Diversified'}</span>
               </CardContent>
             </Card>

             <Card className="bg-muted/10 border-muted/30">
               <CardHeader className="pb-2 border-b bg-muted/20">
                 <CardTitle className="text-sm font-medium uppercase tracking-wider flex items-center gap-2"><PieChart className="h-4 w-4" /> Sector Concentration</CardTitle>
               </CardHeader>
               <CardContent className="pt-4 flex flex-col gap-1 text-center">
                   <div className="text-4xl font-mono">{(portfolio.sectorConcentration*100).toFixed(0)}%</div>
                   <span className="text-xs text-muted-foreground uppercase">{portfolio.topSectors[0]?.sector || "Mixed"} Dominance</span>
               </CardContent>
             </Card>

             <Card className="bg-muted/10 border-muted/30">
               <CardHeader className="pb-2 border-b bg-muted/20">
                 <CardTitle className="text-sm font-medium uppercase tracking-wider flex items-center gap-2"><TrendingUp className="h-4 w-4" /> Weighted Volatility</CardTitle>
               </CardHeader>
               <CardContent className="pt-4 flex flex-col gap-1 text-center">
                   <div className="text-4xl font-mono">{(portfolio.volatility*100).toFixed(2)}%</div>
                   <span className="text-xs text-muted-foreground uppercase">Estimated Daily Flux</span>
               </CardContent>
             </Card>
        </div>

        <Card className="bg-muted/10 border-muted/30">
           <CardHeader>
               <CardTitle>Correlation Matrix</CardTitle>
           </CardHeader>
           <CardContent>
               <div className="text-sm text-muted-foreground">
                   {/* Fallback to JSON for MVP display. A full table UI would map Object matrices. */}
                   <pre className="bg-muted p-4 rounded text-xs overflow-auto">
                       {JSON.stringify(portfolio.correlationMatrix, null, 2)}
                   </pre>
               </div>
           </CardContent>
        </Card>

      </div>
    </main>
  );
}
