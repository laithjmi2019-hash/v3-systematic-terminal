import { EngineResult } from "@/types";

export function calculateAlphaAndRank(result: EngineResult): EngineResult {
  // Extract max points for scaling to 1.0 (Total max is roughly 150)
  const growthPct = result.pillars.growth.total / result.pillars.growth.max;
  const profPct = result.pillars.profitability.total / result.pillars.profitability.max;
  const valPct = result.pillars.value.total / result.pillars.value.max;
  const stabPct = result.pillars.stability.total / result.pillars.stability.max;
  const divPct = result.pillars.dividend.total / result.pillars.dividend.max;

  // Quality is Growth + Profitability, averaged
  const QualityScore = (growthPct + profPct) / 2;
  const ValuationScore = valPct;
  const FinancialStrength = stabPct;
  const DividendScore = divPct;

  const ConsistencyScore = 1.0; 

  // Macro alignment
  const MacroAlignment = Math.max(0, Math.min(1, (result.macroMultiplier - 0.7) / 0.4));

  // AlphaScore computation
  const alphaDecimal = (0.35 * QualityScore) + 
                       (0.25 * ValuationScore) + 
                       (0.15 * ConsistencyScore) + 
                       (0.10 * FinancialStrength) + 
                       (0.05 * DividendScore) +
                       (0.10 * MacroAlignment);

  const alphaScore = Number((alphaDecimal * 100).toFixed(1));

  let alphaRankingStr: EngineResult["alphaRankingStr"] = "Underperformer";
  if (alphaScore > 85) alphaRankingStr = "Elite Alpha";
  else if (alphaScore > 75) alphaRankingStr = "High Alpha";
  else if (alphaScore > 60) alphaRankingStr = "Market Outperformer";

  if (result.verdict === "AVOID") {
      alphaRankingStr = "Underperformer";
  }

  return {
      ...result,
      alphaScore: result.verdict === "AVOID" ? Math.min(alphaScore, 30) : alphaScore,
      alphaRankingStr
  };
}
