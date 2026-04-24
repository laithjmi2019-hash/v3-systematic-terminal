export type Severity = "WARNING" | "CONCERN" | "CRITICAL";
export type Verdict = "STRONG BUY" | "BUY" | "HOLD" | "AVOID" | "PASS" | "WATCH";

export interface RedFlag {
  id: string;
  severity: Severity;
  message: string;
  metric: string;
  value: string;
}

export interface PillarScore {
  total: number;
  baseScore: number;
  penaltyRatio: number; // e.g. 0.2 means 20% stripped due to volatility
  max: number;
  breakdown: {
    metric: string;
    points: number;       // Adjusted final points
    basePoints: number;   // Pure mathematical points BEFORE penalty
    penaltyBase: number;  // Fraction stripped off this specific metric
    maxPoints: number;
    passed: boolean;
    explanation: string;
    value: string;
  }[];
}

export interface EngineResult {
  ticker: string;
  baseScore: number;
  totalScore: number; // Adjusted with macroMultiplier
  macroMultiplier: number;
  alphaScore: number;
  alphaRankingStr: "Elite Alpha" | "High Alpha" | "Market Outperformer" | "Underperformer";
  verdict: Verdict;
  pillars: {
    growth: PillarScore;
    value: PillarScore;
    stability: PillarScore;
    profitability: PillarScore;
    dividend: PillarScore;
  };
  redFlags: RedFlag[];
}

export interface PortfolioRiskMetrics {
    avgCorrelation: number;
    sectorConcentration: number;
    volatility: number;
    portfolioRiskScore: number;
    topSectors: { sector: string, percent: number }[];
    topHoldings: { ticker: string, percent: number }[];
    correlationMatrix: { [tickerA: string]: { [tickerB: string]: number } };
    signals: string[];
}

export interface LLMInsight {
    verdict: string;
    reason: string;
    strengths: string[];
    risks: string[];
    action: string;
}

export interface MacroState {
  phase: "EXPANSION" | "LATE_EXPANSION" | "PEAK" | "RESET";
  rateTrend: "RISING" | "FALLING" | "FLAT";
  liquidityTrend: "RISING" | "FALLING" | "FLAT";
  updatedAt: string;
}

// Data Models mapped closely to FMP
export interface HistoricalFinancials {
  date: string;
  revenue: number;
  grossProfit: number;
  grossMargin: number;
  netIncome: number;
  netMargin: number;
  roe: number;
  roa: number;
  freeCashFlow: number;
  sharesOutstanding: number;
  totalDebt: number;
  totalEquity: number;
  interestExpense: number;
  ebitda: number;
}

export interface Quote {
  ticker: string;
  price: number;
  pe: number;
  pfcf: number;
  marketCap: number;
  dividendYield: number;
}

export interface FMPFinancialGrowth {
  symbol: string;
  date: string;
  revenueGrowth: number;
  netIncomeGrowth: number;
  epsgrowth: number;
}

export interface FMPKeyMetrics {
  symbol: string;
  date: string;
  roeTTM: number;
  roaTTM: number;
  debtToEquityTTM: number;
  freeCashFlowPerShareTTM: number;
  dividendYieldPercentageTTM: number;
}

export interface FMPProfile {
  symbol: string;
  companyName: string;
  sector: string;
  industry: string;
  description: string;
}
