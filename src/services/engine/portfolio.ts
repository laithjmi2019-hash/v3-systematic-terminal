import { PortfolioRiskMetrics } from "@/types";
import { getHistoricalPrices, getCompanyProfile } from "../fmp/client";
import { stdDev } from "./math";

// Helper to calc Pearson correlation of two return arrays
function pearsonCorrelation(x: number[], y: number[]) {
    if (x.length !== y.length || x.length === 0) return 0;
    const n = x.length;
    const avgX = x.reduce((a,b)=>a+b,0)/n;
    const avgY = y.reduce((a,b)=>a+b,0)/n;
    
    let num = 0;
    let den1 = 0;
    let den2 = 0;

    for (let i=0; i<n; i++) {
        const diffX = x[i] - avgX;
        const diffY = y[i] - avgY;
        num += diffX * diffY;
        den1 += diffX * diffX;
        den2 += diffY * diffY;
    }

    if (den1 === 0 || den2 === 0) return 0;
    return num / Math.sqrt(den1 * den2);
}

export async function evaluatePortfolio(holdings: { ticker: string, weight: number }[]): Promise<PortfolioRiskMetrics> {
    const signals: string[] = [];
    const returnsMap: { [ticker: string]: number[] } = {};
    const sectorsMap: { [ticker: string]: string } = {};

    // 1. Fetch data
    for (const h of holdings) {
        const prices = await getHistoricalPrices(h.ticker, 252);
        const returns = [];
        // Convert prices to daily returns
        for(let i=0; i<prices.length-1; i++){
            if (prices[i+1].close > 0) {
              returns.push((prices[i].close - prices[i+1].close) / prices[i+1].close);
            }
        }
        returnsMap[h.ticker] = returns;

        const profile = await getCompanyProfile(h.ticker);
        sectorsMap[h.ticker] = profile.sector || "Unknown";
    }

    // 2. Correlation Matrix
    const correlationMatrix: any = {};
    let totalCorrs = 0;
    let sumCorrs = 0;
    let highRiskPairs = 0;

    const tickers = holdings.map(h => h.ticker);
    for (const t1 of tickers) {
        correlationMatrix[t1] = {};
        for (const t2 of tickers) {
            if (t1 === t2) {
                correlationMatrix[t1][t2] = 1.0;
            } else {
                const arr1 = returnsMap[t1] || [];
                const arr2 = returnsMap[t2] || [];
                const len = Math.min(arr1.length, arr2.length);
                const corr = pearsonCorrelation(arr1.slice(0, len), arr2.slice(0, len));
                correlationMatrix[t1][t2] = corr;
                
                // Track for averages avoiding duplicates (only t1 > t2)
                if (t1 > t2) {
                    sumCorrs += corr;
                    totalCorrs++;
                    if (corr > 0.8) {
                        highRiskPairs++;
                        signals.push(`High correlation overlap detected between ${t1} and ${t2} (${corr.toFixed(2)})`);
                    }
                }
            }
        }
    }

    const avgCorrelation = totalCorrs > 0 ? (sumCorrs / totalCorrs) : 0;

    // 3. Sector Concentration
    const sectorWeights: { [sec: string]: number } = {};
    for (const h of holdings) {
        const sec = sectorsMap[h.ticker] || "Unknown";
        sectorWeights[sec] = (sectorWeights[sec] || 0) + h.weight;
    }
    
    const topSectors = Object.entries(sectorWeights).map(([s, w]) => ({ sector: s, percent: w })).sort((a,b)=>b.percent - a.percent);
    const maxSectorConc = topSectors.length > 0 ? topSectors[0].percent : 0;

    if (maxSectorConc > 0.4) {
        signals.push(`Sector concentration warning: ${topSectors[0].sector} represents ${(maxSectorConc*100).toFixed(1)}% of portfolio.`);
    }

    // 4. Top Holdings Concentration
    const sortedHoldings = [...holdings].sort((a,b)=>b.weight - a.weight);
    const top3Weight = sortedHoldings.slice(0, 3).reduce((sum, h) => sum + h.weight, 0);
    
    if (top3Weight > 0.6) {
        signals.push(`Concentration warning: Top 3 holdings represent ${(top3Weight*100).toFixed(1)}% of portfolio.`);
    }

    // 5. Volatility (Portfolio aggregate std_dev of weighted returns)
    // For simplicity, we approximate it by averaging volatilities weighted
    let ptVolatility = 0;
    for (const h of holdings) {
        ptVolatility += stdDev(returnsMap[h.ticker] || []) * h.weight;
    }

    // Risk Score: 0.5 * AvgCorrelation + 0.3 * SectorConcentration + 0.2 * Volatility
    // scale roughly to 100
    // avgCorr ranges roughly (-1 to 1) -> we map negative to 0 for penalty
    const safeCorr = Math.max(0, avgCorrelation); 
    // Sector conc ranges (0 to 1)
    // Volatility ranges roughly (0 to 0.05 daily). Let's scale * 20 to bring to 0-1 range
    const riskFactor = (0.5 * safeCorr) + (0.3 * maxSectorConc) + (0.2 * Math.min(1, ptVolatility * 20));
    const portfolioRiskScore = riskFactor * 100;

    if (portfolioRiskScore > 75) {
        signals.push("CRITICAL: Extreme portfolio fragility detected. Reduce overlapping positions immediately.");
    }

    return {
        avgCorrelation,
        sectorConcentration: maxSectorConc,
        volatility: ptVolatility,
        portfolioRiskScore,
        topSectors,
        topHoldings: sortedHoldings.map(h => ({ ticker: h.ticker, percent: h.weight })),
        correlationMatrix,
        signals
    };
}
