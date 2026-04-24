import { EngineResult, Quote, PillarScore, RedFlag, Verdict, FMPFinancialGrowth, FMPKeyMetrics } from "@/types";

export function evaluateStock(
  ticker: string, 
  quote: Quote, 
  growth: FMPFinancialGrowth, 
  metrics: FMPKeyMetrics,
  macroMultiplier: number = 1.0
): EngineResult {
  const redFlags: RedFlag[] = [];
  
  // Helper to construct breakdowns uniformly
  function buildBreakdown(metric: string, points: number, maxPoints: number, passed: boolean, valStr: string, exp: string) {
      return { metric, points, basePoints: points, penaltyBase: 0, maxPoints, passed, value: valStr, explanation: exp };
  }

  // 1. GROWTH (Max 50)
  // Rev Growth > 10% = 25 pts, 5-10% = 15 pts, <5% = 5 pts. Same for Earnings (netIncomeGrowth)
  const growthScore = (): PillarScore => {
    const revGrow = growth.revenueGrowth || 0;
    const epsGrow = growth.netIncomeGrowth || growth.epsgrowth || 0;

    let revPts = 5;
    if (revGrow > 0.10) revPts = 25;
    else if (revGrow >= 0.05) revPts = 15;

    let epsPts = 5;
    if (epsGrow > 0.10) epsPts = 25;
    else if (epsGrow >= 0.05) epsPts = 15;

    const total = revPts + epsPts;

    const breakdown = [
        buildBreakdown("Revenue Growth", revPts, 25, revPts > 5, `${(revGrow*100).toFixed(1)}%`, ">10%=25, 5-10%=15, <5%=5"),
        buildBreakdown("Earnings Growth", epsPts, 25, epsPts > 5, `${(epsGrow*100).toFixed(1)}%`, ">10%=25, 5-10%=15, <5%=5")
    ];

    return { total, baseScore: total, penaltyRatio: 0, max: 50, breakdown };
  };

  // 2. VALUE (Max 20)
  // P/E < 15 = 20 pts, 15-25 = 10 pts, > 25 = 5 pts
  const valueScore = (): PillarScore => {
    const pe = quote.pe || 0;
    let pePts = 5;
    if (pe > 0 && pe < 15) pePts = 20;
    else if (pe >= 15 && pe <= 25) pePts = 10;
    // if negative P/E, treated as bad (5 pts)

    const breakdown = [
        buildBreakdown("P/E Ratio", pePts, 20, pePts > 5, pe.toFixed(1), "<15=20, 15-25=10, >25=5"),
    ];

    return { total: pePts, baseScore: pePts, penaltyRatio: 0, max: 20, breakdown };
  };

  // 3. STABILITY (Max 40)
  // Debt/Equity < 1 = 20 pts, otherwise 5. ROE > 15% = 20 pts, otherwise 10.
  const stabilityScore = (): PillarScore => {
    const de = metrics.debtToEquityTTM || 0;
    const roe = metrics.roeTTM || 0;

    const dePts = (de >= 0 && de < 1) ? 20 : 5;
    const roePts = (roe > 0.15) ? 20 : 10;
    
    const total = dePts + roePts;

    const breakdown = [
        buildBreakdown("Debt / Equity", dePts, 20, dePts === 20, de.toFixed(2), "<1=20, else 5"),
        buildBreakdown("ROE", roePts, 20, roePts === 20, `${(roe*100).toFixed(1)}%`, ">15%=20, else 10"),
    ];

    return { total, baseScore: total, penaltyRatio: 0, max: 40, breakdown };
  };

  // 4. PROFITABILITY (Max 30)
  // ROA > 10% = 15 pts, otherwise 5. Free Cash Flow > 0 = 15 pts, otherwise 5.
  const profitabilityScore = (): PillarScore => {
    const roa = metrics.roaTTM || 0;
    const fcf = metrics.freeCashFlowPerShareTTM || quote.pfcf || 0; // fallback

    const roaPts = (roa > 0.10) ? 15 : 5;
    const fcfPts = (fcf > 0) ? 15 : 5;

    const total = roaPts + fcfPts;

    const breakdown = [
        buildBreakdown("ROA", roaPts, 15, roaPts === 15, `${(roa*100).toFixed(1)}%`, ">10%=15, else 5"),
        buildBreakdown("Free Cash Flow", fcfPts, 15, fcfPts === 15, fcf > 0 ? "Positive" : "Negative", ">0 = 15, else 5"),
    ];

    return { total, baseScore: total, penaltyRatio: 0, max: 30, breakdown };
  };

  // 5. DIVIDEND (Max 10)
  // Dividend Yield > 3% = 10 pts, 1-3% = 5 pts, <1% = 0.
  const dividendScore = (): PillarScore => {
    const yieldPct = (metrics.dividendYieldPercentageTTM !== undefined ? metrics.dividendYieldPercentageTTM : quote.dividendYield) || 0; 
    let divPts = 0;
    // metrics.dividendYieldPercentageTTM could be 0.03 for 3% or already * 100. Let's assume FMP passes percentage if labeled 'Percentage' or raw decimal. Usually it's decimal.
    // We treat > 0.03 as >3%.
    let formattedYield = (yieldPct * 100 * (yieldPct < 1 ? 1 : 0.01)); // normalization

    if (formattedYield > 3) divPts = 10;
    else if (formattedYield >= 1) divPts = 5;

    const breakdown = [
        buildBreakdown("Dividend Yield", divPts, 10, divPts > 0, `${formattedYield.toFixed(1)}%`, ">3%=10, 1-3%=5, <1%=0"),
    ];

    return { total: divPts, baseScore: divPts, penaltyRatio: 0, max: 10, breakdown };
  };

  const pGrowth = growthScore();
  const pVal = valueScore();
  const pStab = stabilityScore();
  const pProf = profitabilityScore();
  const pDiv = dividendScore();

  const baseTotal = pGrowth.total + pVal.total + pStab.total + pProf.total + pDiv.total;
  let finalScore = baseTotal * macroMultiplier;
  
  let verdict: Verdict = "AVOID";
  if (finalScore >= 80) verdict = "STRONG BUY";
  else if (finalScore >= 65) verdict = "BUY";
  else if (finalScore >= 50) verdict = "HOLD";

  return {
    ticker,
    baseScore: baseTotal,
    totalScore: Number(finalScore.toFixed(1)),
    macroMultiplier,
    alphaScore: 0, 
    alphaRankingStr: "Underperformer", 
    verdict,
    pillars: {
      growth: pGrowth,
      value: pVal,
      stability: pStab,
      profitability: pProf,
      dividend: pDiv,
    },
    redFlags
  };
}
