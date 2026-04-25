import { EngineResult, Quote, PillarScore, RedFlag, Verdict, FMPFinancialGrowth, FMPKeyMetrics } from "@/types";

export function evaluateStock(
  ticker: string, 
  quote: Quote, 
  growth: FMPFinancialGrowth, 
  metrics: FMPKeyMetrics,
  prices: any[],
  macroMultiplier: number = 1.0
): EngineResult {
  const redFlags: RedFlag[] = [];
  
  function buildBreakdown(metric: string, points: number, maxPoints: number, passed: boolean, valStr: string, exp: string) {
      return { metric, points, basePoints: points, penaltyBase: 0, maxPoints, passed, value: valStr, explanation: exp };
  }

  // 1. GROWTH (Max 50)
  const growthScore = (): PillarScore => {
    const revGrow = growth.revenueGrowth || 0;
    const epsGrow = growth.netIncomeGrowth || growth.epsgrowth || 0;
    const yrs = growth.yearsAveraged || 1;

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

  // 2. VALUE (Sector Relative) (Max 20)
  const valueScore = (): PillarScore => {
    const pe = quote.pe || 0;
    const sector = quote.sector || "DEFAULT";

    const SECTOR_PE: Record<string, number> = {
        "Technology": 28.0, "Healthcare": 22.0, "Financial Services": 14.0,
        "Consumer Cyclical": 20.0, "Industrials": 21.0, "Energy": 12.0,
        "Consumer Defensive": 20.0, "Utilities": 17.0, "Real Estate": 25.0,
        "Basic Materials": 15.0, "Communication Services": 19.0, "DEFAULT": 20.0
    };
    const secMedianPe = SECTOR_PE[sector] || 20.0;
    
    let pePts = 5;
    const relPe = (secMedianPe > 0 && pe > 0) ? (pe / secMedianPe) : 999.0;

    if (pe > 0 && relPe <= 0.8) pePts = 20;
    else if (pe > 0 && relPe <= 1.2) pePts = 10;

    const breakdown = [
        buildBreakdown("P/E Ratio", pePts, 20, pePts > 5, `${pe.toFixed(1)} vs ${secMedianPe.toFixed(1)} (Peer)`, "Rel PE <=0.8=20, <=1.2=10, >1.2=5"),
    ];

    return { total: pePts, baseScore: pePts, penaltyRatio: 0, max: 20, breakdown };
  };

  // 3. STABILITY (Max 40)
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
  const profitabilityScore = (): PillarScore => {
    const roa = metrics.roaTTM || 0;
    const fcf = metrics.freeCashFlowPerShareTTM || quote.pfcf || 0;

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
  const dividendScore = (): PillarScore => {
    const yieldPct = (metrics.dividendYieldPercentageTTM !== undefined ? metrics.dividendYieldPercentageTTM : quote.dividendYield) || 0; 
    let formattedYield = (yieldPct * 100 * (yieldPct < 1 ? 1 : 0.01)); 

    let divPts = 0;
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
  
  // 6. ENGINES & GUARDRAILS
  let bonusPenalty = 0;
  const revScore = quote.revisions_score !== undefined ? quote.revisions_score : 0.5;
  if (revScore >= 0.75) bonusPenalty = 10;
  else if (revScore <= 0.25) bonusPenalty = -15;

  if (bonusPenalty !== 0) {
      redFlags.push({
          id: "revisions",
          severity: bonusPenalty > 0 ? "INFO" : "WARNING",
          metric: "Smart Money Analysis",
          message: `${bonusPenalty > 0 ? '+' : ''}${bonusPenalty} point adjustment.`,
          value: ""
      });
  }

  let failTrendGate = false;
  const currPrice = quote.price || 0;
  let sma200 = 0;
  if (prices && prices.length > 50) {
      const pricesSubset = prices.slice(0, 200).map(p => p.close || 0); // Assuming latest first? FMP historical-price-full actually returns latest first
      sma200 = pricesSubset.reduce((a, b) => a + b, 0) / pricesSubset.length;
      if (currPrice > 0 && currPrice < sma200) {
          failTrendGate = true;
          redFlags.push({
              id: "trend-gate",
              severity: "CRITICAL",
              metric: "SMA 200 Kill-Switch",
              message: `Structural downtrend. Price ($${currPrice.toFixed(2)}) < SMA200 ($${sma200.toFixed(2)}). Score capped to HOLD.`,
              value: ""
          });
      }
  }

  let finalScore = (baseTotal + bonusPenalty) * macroMultiplier;
  finalScore = Math.min(finalScore, 150);

  if (failTrendGate) {
      finalScore = Math.min(finalScore, 64);
  }
  
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
