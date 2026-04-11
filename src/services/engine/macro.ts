import { MacroState } from "@/types";
import { getFedFundsRate, getM2Supply } from "../fred/client";

export async function getMacroState(): Promise<MacroState & { multiplier: number }> {
  const fedFunds = await getFedFundsRate();
  const m2 = await getM2Supply();

  let phase: MacroState["phase"] = "EXPANSION";
  let multiplier = 1.0;

  if (fedFunds.trend === "RISING" && m2.trend === "FALLING") {
    phase = "LATE_EXPANSION"; 
    multiplier = 0.85;
  } else if (fedFunds.trend === "FALLING" && m2.trend === "RISING") {
    phase = "RESET";
    multiplier = 1.1;
  } else if (fedFunds.trend === "RISING" && m2.trend === "RISING") {
    phase = "EXPANSION";
    multiplier = 1.0;
  } else {
    phase = "PEAK"; 
    multiplier = 0.7;
  }

  return {
    phase,
    rateTrend: fedFunds.trend,
    liquidityTrend: m2.trend,
    updatedAt: new Date().toISOString(),
    multiplier
  };
}
