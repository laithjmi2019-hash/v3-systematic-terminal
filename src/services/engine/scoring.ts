import { EngineResult, HistoricalFinancials, Quote, PillarScore, RedFlag, Severity } from "@/types";
import { normalize, inverseNormalize, calculateVolatilityPenalty, stdDev } from "./math";

export function evaluateStock(ticker: string, financials: HistoricalFinancials[], quote: Quote, macroMultiplier: number = 1.0): EngineResult {
  const redFlags: RedFlag[] = [];
  
  // Sort newest first
  const sortedFin = [...financials].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  const current = sortedFin[0] || ({} as HistoricalFinancials);

  // Arrays over time for Volatility calculations
  const gmSeries = sortedFin.map(f => f.grossMargin);
  const revSeries = sortedFin.map(f => f.revenue);
  const nmSeries = sortedFin.map(f => f.netMargin);
  const roeSeries = sortedFin.map(f => f.roe);
  const fcfSeries = sortedFin.map(f => f.freeCashFlow);
  
  // Helper to construct breakdowns uniformly
  function buildBreakdown(metric: string, rawScore: number, weight: number, maxPillar: number, valStr: string, exp: string) {
      const basePoints = rawScore * (weight * maxPillar);
      const points = basePoints; // Will update penalty separately if needed
      return { metric, points, basePoints, penaltyBase: 0, maxPoints: weight * maxPillar, passed: rawScore > 0.4, value: valStr, explanation: exp };
  }

  // 1. MOAT (Max 20)
  const moat = (): PillarScore => {
    const gmScore = normalize(current.grossMargin, 0.20, 0.80);
    const gmStabScore = 1 / (1 + stdDev(gmSeries)); // User spec
    
    // Calculate Revenue growth array
    const revGrowths: number[] = [];
    for(let i=0; i<sortedFin.length-1; i++){
        if (sortedFin[i+1].revenue > 0) revGrowths.push((sortedFin[i].revenue - sortedFin[i+1].revenue) / sortedFin[i+1].revenue);
    }
    const revConsScore = 1 / (1 + stdDev(revGrowths));

    const totalRaw = (0.4 * gmScore) + (0.3 * gmStabScore) + (0.3 * revConsScore);
    const baseScore = totalRaw * 20;

    const breakdown = [
        buildBreakdown("Gross Margin", gmScore, 0.4, 20, `${(current.grossMargin*100).toFixed(1)}%`, "Normalized 20%-80%"),
        buildBreakdown("Margin Stability", gmStabScore, 0.3, 20, `${stdDev(gmSeries).toFixed(2)} SD`, "Inverse StdDev Penalty"),
        buildBreakdown("Revenue Consistency", revConsScore, 0.3, 20, `${stdDev(revGrowths).toFixed(2)} SD`, "Inverse StdDev Penalty")
    ];

    // Apply global pillar volatility penalty based on Revenue
    const penalty = calculateVolatilityPenalty(revGrowths);
    const finalPoints = baseScore * (1 - penalty);

    return { total: Number(finalPoints.toFixed(1)), baseScore: Number(baseScore.toFixed(1)), penaltyRatio: penalty, max: 20, breakdown };
  };

  // 2. PROFITABILITY (Max 15)
  const profitability = (): PillarScore => {
    const roeScore = normalize(current.roe, 0, 0.30);
    const nmScore = normalize(current.netMargin, 0, 0.25);
    const roaScore = normalize(current.roa, 0, 0.15);

    const totalRaw = (0.4 * roeScore) + (0.3 * nmScore) + (0.3 * roaScore);
    const baseScore = totalRaw * 15;

    const breakdown = [
        buildBreakdown("ROE", roeScore, 0.4, 15, `${(current.roe*100).toFixed(1)}%`, "Normalized 0-30%"),
        buildBreakdown("Net Margin", nmScore, 0.3, 15, `${(current.netMargin*100).toFixed(1)}%`, "Normalized 0-25%"),
        buildBreakdown("ROA", roaScore, 0.3, 15, `${(current.roa*100).toFixed(1)}%`, "Normalized 0-15%")
    ];

    const penalty = calculateVolatilityPenalty(nmSeries);
    const finalPoints = baseScore * (1 - penalty);

    return { total: Number(finalPoints.toFixed(1)), baseScore: Number(baseScore.toFixed(1)), penaltyRatio: penalty, max: 15, breakdown };
  };

  // 3. FINANCIAL STRENGTH (Max 15)
  const financialStrength = (): PillarScore => {
    const cr = current.totalDebt > 0 ? 1.5 : 2; // Stub CR calculation since balance sheet might not fully match MVP inputs
    const crScore = normalize(cr, 1, 3);
    
    // Inverse Normalize D/E 0-2
    const de = current.totalEquity > 0 ? current.totalDebt / current.totalEquity : 2.5;
    const deScore = inverseNormalize(de, 0, 2.0);

    // Interest Coverage
    const ic = current.interestExpense > 0 ? (current.netIncome + current.interestExpense) / current.interestExpense : 10;
    const icScore = normalize(ic, 1, 10);

    const totalRaw = (0.4 * crScore) + (0.4 * deScore) + (0.2 * icScore);
    const baseScore = totalRaw * 15;

    const breakdown = [
        buildBreakdown("Current Ratio", crScore, 0.4, 15, cr.toFixed(1), "Normalized 1-3"),
        buildBreakdown("Debt to Equity", deScore, 0.4, 15, de.toFixed(1), "Inverted 0-2"),
        buildBreakdown("Interest Coverage", icScore, 0.2, 15, ic.toFixed(1), "Normalized 1-10"),
    ];

    return { total: Number(baseScore.toFixed(1)), baseScore: Number(baseScore.toFixed(1)), penaltyRatio: 0, max: 15, breakdown };
  };

  // 4. CASH FLOW QUALITY (Max 15)
  const cashFlowQuality = (): PillarScore => {
    const fcfGrowths: number[] = [];
    for(let i=0; i<Math.min(sortedFin.length-1, 5); i++){
        if (sortedFin[i+1].freeCashFlow !== 0) fcfGrowths.push((sortedFin[i].freeCashFlow - sortedFin[i+1].freeCashFlow) / Math.abs(sortedFin[i+1].freeCashFlow));
    }
    const fcfGrowAvg = fcfGrowths.length ? fcfGrowths.reduce((a,b)=>a+b,0)/fcfGrowths.length : 0;
    const fcfGScore = normalize(fcfGrowAvg, 0, 0.20);
    
    const fcfConsScore = 1 / (1 + stdDev(fcfGrowths));

    const sharesNow = current.sharesOutstanding;
    const sharesOld = sortedFin[sortedFin.length - 1]?.sharesOutstanding || sharesNow;
    const dilutionGrowth = sharesOld > 0 ? (sharesNow - sharesOld) / sharesOld : 0;
    const dilScore = inverseNormalize(dilutionGrowth, 0, 0.05);

    const totalRaw = (0.4 * fcfGScore) + (0.3 * fcfConsScore) + (0.3 * dilScore);
    const baseScore = totalRaw * 15;

    const breakdown = [
        buildBreakdown("FCF Growth", fcfGScore, 0.4, 15, `${(fcfGrowAvg*100).toFixed(1)}%`, "Normalized 0-20%"),
        buildBreakdown("FCF Consistency", fcfConsScore, 0.3, 15, "0.0 SD", "Inverse Volatility"),
        buildBreakdown("Share Dilution", dilScore, 0.3, 15, `${(dilutionGrowth*100).toFixed(1)}%`, "Inverted 0-5%"),
    ];
    
    const penalty = calculateVolatilityPenalty(fcfSeries);
    const finalPoints = baseScore * (1 - penalty);

    return { total: Number(finalPoints.toFixed(1)), baseScore: Number(baseScore.toFixed(1)), penaltyRatio: penalty, max: 15, breakdown };
  };

  // 5. VALUATION (Max 15)
  const valuation = (): PillarScore => { 
    // PE Inverse 10-40, PFCF Inverse 8-30
    const peScore = inverseNormalize(quote.pe, 10, 40);
    const pfcfScore = inverseNormalize(quote.pfcf, 8, 30);

    const totalRaw = (0.5 * peScore) + (0.5 * pfcfScore);
    const baseScore = totalRaw * 15;

    const breakdown = [
        buildBreakdown("P/E Ratio", peScore, 0.5, 15, Math.max(0, quote.pe || 0).toFixed(1), "Inverted 10-40"),
        buildBreakdown("P/FCF", pfcfScore, 0.5, 15, Math.max(0, quote.pfcf || 0).toFixed(1), "Inverted 8-30"),
    ];

    return { total: Number(baseScore.toFixed(1)), baseScore: Number(baseScore.toFixed(1)), penaltyRatio: 0, max: 15, breakdown };
  };

  const pMoat = moat();
  const pProf = profitability();
  const pFin = financialStrength();
  const pCF = cashFlowQuality();
  const pVal = valuation();

  const baseScore = pMoat.total + pProf.total + pFin.total + pCF.total + pVal.total;
  let totalScore = baseScore * macroMultiplier;
  
  // --- HARD FAIL LOGIC ---
  const de = current.totalEquity > 0 ? current.totalDebt / current.totalEquity : 99;
  const ic = current.interestExpense > 0 ? (current.netIncome + current.interestExpense) / current.interestExpense : 10;
  
  const sharesNow = current.sharesOutstanding;
  const sharesOld = sortedFin.find(f => f.date.includes(String(new Date(current.date).getFullYear()-1)))?.sharesOutstanding || sharesNow;
  const dilutionGrowth = sharesOld > 0 ? (sharesNow - sharesOld) / sharesOld : 0;

  let negFCFYears = 0;
  for(let i=0; i<Math.min(sortedFin.length, 3); i++) {
      if(sortedFin[i].freeCashFlow < 0) negFCFYears++;
  }

  let hardFailTriggered = false;

  if (de > 2) { redFlags.push({ id: "hf_de", severity: "CRITICAL", message: "Debt/Equity exceeds 2.0 limit.", metric: "Debt/Equity", value: de.toFixed(1) }); hardFailTriggered = true; }
  if (negFCFYears >= 3) { redFlags.push({ id: "hf_fcf", severity: "CRITICAL", message: "Negative FCF for 3+ consecutive years.", metric: "FCF Trend", value: `${negFCFYears} yrs` }); hardFailTriggered = true; }
  if (dilutionGrowth > 0.05) { redFlags.push({ id: "hf_dil", severity: "CRITICAL", message: "Annual share dilution > 5%.", metric: "Dilution", value: `${(dilutionGrowth*100).toFixed(1)}%` }); hardFailTriggered = true; }
  if (ic < 2) { redFlags.push({ id: "hf_ic", severity: "CRITICAL", message: "Interest Coverage below minimum 2x threshold.", metric: "Int Cov", value: ic.toFixed(1) }); hardFailTriggered = true; }
  if (current.roe < 0.05 && current.netMargin < 0.05) { redFlags.push({ id: "hf_prof", severity: "CRITICAL", message: "Both ROE and Net Margin below 5%.", metric: "Profitability", value: "Fail" }); hardFailTriggered = true; }

  let verdict: "PASS" | "WATCH" | "AVOID" = "AVOID";
  // Elite 70-80, Strong 50-69, Speculative 30-49, Avoid <30
  if (totalScore >= 50) verdict = "PASS";
  else if (totalScore >= 30) verdict = "WATCH";

  if (hardFailTriggered) {
      totalScore = Math.min(totalScore, 30);
      verdict = "AVOID";
      redFlags.push({
        id: "sys_downgrade",
        severity: "CRITICAL",
        message: "Systematic Hard Fail triggered. Total Score capped.",
        metric: "VERDICT",
        value: "OVERRIDE"
      });
  }

  return {
    ticker,
    baseScore: Number(baseScore.toFixed(1)),
    totalScore: Number(totalScore.toFixed(1)),
    macroMultiplier,
    alphaScore: 0, // Populated via Alpha wrapper
    alphaRankingStr: "Underperformer", 
    verdict,
    pillars: {
      moat: pMoat,
      profitability: pProf,
      financialStrength: pFin,
      cashFlowQuality: pCF,
      valuation: pVal,
    },
    redFlags
  };
}
