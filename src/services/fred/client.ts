// FRED API Client stub
import { MacroState } from "@/types";

const FRED_API_KEY = process.env.FRED_API_KEY;
const BASE_URL = "https://api.stlouisfed.org/fred/series/observations";

export async function getFedFundsRate(): Promise<{ value: number, trend: MacroState["rateTrend"] }> {
  if (!FRED_API_KEY) return { value: 5.25, trend: "FLAT" };
  // Fetch FEDFUNDS series
  return { value: 5.25, trend: "FLAT" };
}

export async function getM2Supply(): Promise<{ value: number, trend: MacroState["liquidityTrend"] }> {
  if (!FRED_API_KEY) return { value: 20000, trend: "FALLING" };
  // Fetch WM2NS series
  return { value: 20000, trend: "FALLING" };
}
