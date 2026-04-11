import { Navbar } from "@/components/navbar";
import { getQuote, getHistoricalFinancials } from "@/services/fmp/client";
import { evaluateStock } from "@/services/engine/scoring";
import { calculateAlphaAndRank } from "@/services/engine/alpha";
import { generateAIExplanation } from "@/services/llm/client";
import { getMacroState } from "@/services/engine/macro";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, CheckCircle2, AlertTriangle, Info, Target, Zap, ShieldAlert, Cpu } from "lucide-react";
import { RedFlag, PillarScore, Verdict, LLMInsight } from "@/types";

function VerdictBadge({ verdict, totalScore, baseScore }: { verdict: Verdict, totalScore: number, baseScore: number }) {
  let color = "bg-gray-500/20 text-gray-500 border-gray-500/50";
  if (verdict === "PASS") color = "bg-green-500/20 text-green-500 border-green-500/50";
  if (verdict === "WATCH") color = "bg-yellow-500/20 text-yellow-500 border-yellow-500/50";
  if (verdict === "AVOID") color = "bg-red-500/20 text-red-500 border-red-500/50";

  return (
    <div className="flex flex-col items-end">
      <Badge variant="outline" className={`text-2xl px-6 py-2 tracking-widest ${color}`}>
        {verdict}
      </Badge>
      <span className="text-xs text-muted-foreground mt-2 font-mono">ADJ SCORE: {totalScore}/80 | BASE: {baseScore}</span>
    </div>
  );
}

function PillarCard({ title, pillar }: { title: string; pillar: PillarScore }) {
  return (
    <Card className="flex flex-col h-full bg-muted/10 border-muted/30">
      <CardHeader className="pb-2 flex flex-row items-center justify-between border-b bg-muted/20">
        <CardTitle className="text-sm font-medium uppercase tracking-wider">{title}</CardTitle>
        <div className="flex items-center gap-2">
            {pillar.penaltyRatio > 0 && <span className="text-[10px] text-red-400 border border-red-400/20 px-1 rounded bg-red-400/10">VOL PENALTY -{(pillar.penaltyRatio*100).toFixed(0)}%</span>}
            <span className="font-mono font-bold">{pillar.total} <span className="text-muted-foreground font-normal text-xs">/ {pillar.max}</span></span>
        </div>
      </CardHeader>
      <CardContent className="flex-1 space-y-4 pt-4">
        {pillar.breakdown.map((b, i) => (
          <div key={i} className="space-y-1.5">
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                {b.passed ? (
                  <CheckCircle2 className="h-3 w-3 text-green-500" />
                ) : (
                  <AlertCircle className="h-3 w-3 text-red-500" />
                )}
                <span className="font-medium text-muted-foreground text-xs">{b.metric}</span>
              </div>
              <span className="font-mono text-xs">{b.basePoints.toFixed(1)}/{b.maxPoints} pts</span>
            </div>
            <div className="flex justify-between items-center bg-muted/30 p-2 rounded text-[10px]">
               <span className="text-muted-foreground max-w-[80%] uppercase">{b.explanation}</span>
               <span className="font-mono font-bold">{b.value}</span>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function DecisionBox({ insight }: { insight: LLMInsight }) {
  return (
    <Card className="bg-primary/5 border-primary/30 shadow-lg">
      <CardHeader className="pb-3 border-b border-primary/10">
        <CardTitle className="flex items-center gap-2 text-primary text-sm uppercase tracking-widest">
            <Cpu className="h-4 w-4" /> Decision Intelligence
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4 space-y-6">
         <div>
            <h3 className="text-lg font-medium text-foreground">{insight.reason}</h3>
            <p className="text-muted-foreground text-sm uppercase mt-1 flex items-center gap-2">
                <Target className="h-4 w-4" /> System Action: <strong className="text-foreground">{insight.action}</strong>
            </p>
         </div>

         <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
             <div className="space-y-2">
                 <span className="text-xs uppercase text-green-500 font-bold tracking-wider">Strengths</span>
                 <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                     {insight.strengths.map((s,i) => <li key={i}>{s}</li>)}
                 </ul>
             </div>
             <div className="space-y-2">
                 <span className="text-xs uppercase text-red-500 font-bold tracking-wider">Risks & Violations</span>
                 <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                     {insight.risks.map((s,i) => <li key={i}>{s}</li>)}
                 </ul>
             </div>
         </div>
      </CardContent>
    </Card>
  );
}

export default async function StockTerminal({ params }: { params: Promise<{ ticker: string }> }) {
  const resolvedParams = await params;
  const ticker = resolvedParams.ticker.toUpperCase();
  
  const quote = await getQuote(ticker);
  const financials = await getHistoricalFinancials(ticker);
  const macroState = await getMacroState();
  
  const baseResult = evaluateStock(ticker, financials, quote, macroState.multiplier);
  const finalResult = calculateAlphaAndRank(baseResult);
  const aiInsight = await generateAIExplanation(finalResult);

  return (
    <main className="flex min-h-screen flex-col">
      <Navbar />
      <div className="flex-1 w-full max-w-7xl mx-auto p-4 md:p-8 space-y-6">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b pb-4">
          <div>
            <div className="flex items-center gap-4">
              <h1 className="text-4xl font-bold tracking-tight">{ticker}</h1>
              <span className="text-3xl text-muted-foreground font-light">${quote.price || "0.00"}</span>
              <Badge className="bg-primary/20 text-primary hover:bg-primary/30 border-none ml-2 tracking-widest uppercase">
                  {finalResult.alphaRankingStr}
              </Badge>
            </div>
            <div className="flex items-center gap-4 mt-2">
               <span className="text-sm text-muted-foreground font-mono">MACRO ADJ: {macroState.multiplier}x</span>
               <span className="text-sm text-muted-foreground font-mono">ALPHA SCORE: {finalResult.alphaScore.toFixed(1)}/100</span>
            </div>
          </div>
          <VerdictBadge verdict={finalResult.verdict} totalScore={finalResult.totalScore} baseScore={finalResult.baseScore} />
        </div>

        {/* Top level alerts */}
        {finalResult.redFlags.length > 0 && (
          <div className="border border-red-500/30 bg-red-500/10 p-4 rounded-lg flex flex-col gap-2">
            <h4 className="text-red-500 font-bold uppercase tracking-wider text-xs flex items-center gap-2"><ShieldAlert className="h-4 w-4"/> Systematic Hard Alerts</h4>
            {finalResult.redFlags.map((f, i) => (
                <div key={i} className="flex gap-2 items-center text-sm">
                   <strong className={`px-1.5 py-0.5 rounded text-[10px] ${f.severity === 'CRITICAL' ? 'bg-red-500 text-black' : 'bg-orange-500 text-black'}`}>{f.severity}</strong>
                   <span className="text-muted-foreground">({f.metric}: {f.value})</span>
                   <span>{f.message}</span>
                </div>
            ))}
          </div>
        )}

        <DecisionBox insight={aiInsight} />

        {/* 5-Pillar Matrix */}
        <div>
           <h2 className="text-xl font-bold mb-4 mt-8 font-mono uppercase tracking-widest text-muted-foreground border-b pb-2">Mathematical Breakdown</h2>
           <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
             <PillarCard title="Moat & Stability" pillar={finalResult.pillars.moat} />
             <PillarCard title="Profitability" pillar={finalResult.pillars.profitability} />
             <PillarCard title="Financial Strength" pillar={finalResult.pillars.financialStrength} />
             <PillarCard title="Cash Flow Quality" pillar={finalResult.pillars.cashFlowQuality} />
             <PillarCard title="Valuation" pillar={finalResult.pillars.valuation} />
           </div>
        </div>

      </div>
    </main>
  );
}
