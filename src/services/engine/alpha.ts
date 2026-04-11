import { EngineResult } from "@/types";

export function calculateAlphaAndRank(result: EngineResult): EngineResult {
  // Extract max points for scaling to 1.0
  const moatPct = result.pillars.moat.total / result.pillars.moat.max;
  const profPct = result.pillars.profitability.total / result.pillars.profitability.max;
  const valPct = result.pillars.valuation.total / result.pillars.valuation.max;
  const fsPct = result.pillars.financialStrength.total / result.pillars.financialStrength.max;

  // Quality is Moat + Profitability, averaged
  const QualityScore = (moatPct + profPct) / 2;
  const ValuationScore = valPct;
  const FinancialStrength = fsPct;

  // Average volatility penalty across pillars where it applies
  const penaltyAvg = (result.pillars.moat.penaltyRatio + result.pillars.profitability.penaltyRatio + result.pillars.cashFlowQuality.penaltyRatio) / 3;
  const ConsistencyScore = 1 - penaltyAvg; 

  // Macro
  // Normalizing macro multiplier (0.7 -> 1.1) to roughly (0 -> 1.0)
  // Let's just use it linearly: 1.1 = Max, 0.7 = Min.
  // normalized = (m - 0.7) / (1.1 - 0.7)
  const MacroAlignment = Math.max(0, Math.min(1, (result.macroMultiplier - 0.7) / 0.4));

  // AlphaScore computation (max theoretically 1.0, output 0-100)
  const alphaDecimal = (0.35 * QualityScore) + 
                       (0.25 * ValuationScore) + 
                       (0.20 * ConsistencyScore) + 
                       (0.10 * FinancialStrength) + 
                       (0.10 * MacroAlignment);

  const alphaScore = Number((alphaDecimal * 100).toFixed(1));

  // Top 1% -> "Elite Alpha", Top 5% -> "High Alpha", Top 20% -> "Market Outperformer", Else -> "Underperformer"
  // Assuming a normally distributed baseline mock threshold until cross-sectional engine is built:
  // > 85 = Elite (Top 1%)
  // > 75 = High Alpha (Top 5%)
  // > 60 = Outperformer (Top 20%)
  let alphaRankingStr: EngineResult["alphaRankingStr"] = "Underperformer";
  if (alphaScore > 85) alphaRankingStr = "Elite Alpha";
  else if (alphaScore > 75) alphaRankingStr = "High Alpha";
  else if (alphaScore > 60) alphaRankingStr = "Market Outperformer";

  // In hard fail, ranking is forcefully crushed
  if (result.verdict === "AVOID") {
      alphaRankingStr = "Underperformer";
  }

  return {
      ...result,
      alphaScore: result.verdict === "AVOID" ? Math.min(alphaScore, 30) : alphaScore,
      alphaRankingStr
  };
}
