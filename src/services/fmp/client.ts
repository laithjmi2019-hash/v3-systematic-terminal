const FMP_API_KEY = process.env.FMP_API_KEY || "ZopJDkQbPkxpeehQrJtxGAQRVWJnkiop";
const ALPHA_VANTAGE_KEY = process.env.ALPHA_VANTAGE_KEY || "WLZRN9J45SFA1NEJ";
const FINNHUB_KEY = process.env.FINNHUB_KEY || "d2c9a2pr01qihtcqnssgd2c9a2pr01qihtcqnst0";
const BASE_URL = "https://financialmodelingprep.com/api/v3";

export async function getQuote(ticker: string) {
  let result: any = {};
  // 1. Try Finnhub for price
  try {
      const res = await fetch(`https://finnhub.io/api/v1/quote?symbol=${ticker}&token=${FINNHUB_KEY}`, { cache: 'no-store' });
      if (res.ok) {
         const data = await res.json();
         if (data.c) {
             result.price = data.c;
         }
      }
  } catch {}
  
  // 2. Try FMP (Free Tier Quote usually works)
  try { 
      const res = await fetch(`${BASE_URL}/quote/${ticker}?apikey=${FMP_API_KEY}`, { cache: 'no-store' });
      if (res.ok) {
          const data = await res.json();
          if (data[0]) {
              result = { ...data[0], price: result.price || data[0].price }; 
          }
      }
  } catch {}
  return result;
}

export async function getFinancialGrowth(ticker: string) {
  let result = { revenueGrowth: 0, netIncomeGrowth: 0, epsgrowth: 0, yearsAveraged: 0 };
  
  // 1. Try AlphaVantage (100% Free fallback)
  try {
     const res = await fetch(`https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol=${ticker}&apikey=${ALPHA_VANTAGE_KEY}`, { cache: 'no-store' });
     if (res.ok) {
         const data = await res.json();
         if (data.annualReports) {
             const reports = data.annualReports;
             const revGrowths: number[] = [];
             const niGrowths: number[] = [];
             const limit = Math.min(4, reports.length);
             
             for (let i = 0; i < limit - 1; i++) {
                 const curRev = parseFloat(reports[i].totalRevenue || '0');
                 const prevRev = parseFloat(reports[i+1].totalRevenue || '0');
                 if (prevRev !== 0) revGrowths.push((curRev - prevRev) / Math.abs(prevRev));
                 
                 const curNi = parseFloat(reports[i].netIncome || '0');
                 const prevNi = parseFloat(reports[i+1].netIncome || '0');
                 if (prevNi !== 0) niGrowths.push((curNi - prevNi) / Math.abs(prevNi));
             }
             
             if (revGrowths.length > 0) result.revenueGrowth = revGrowths.reduce((a,b)=>a+b,0)/revGrowths.length;
             if (niGrowths.length > 0) {
                 result.netIncomeGrowth = niGrowths.reduce((a,b)=>a+b,0)/niGrowths.length;
                 result.epsgrowth = result.netIncomeGrowth;
             }
             result.yearsAveraged = Math.max(revGrowths.length, niGrowths.length);
             return result;
         }
     }
  } catch {}
  return result;
}

export async function getKeyMetrics(ticker: string) {
    let metrics: any = { roeTTM: 0, roaTTM: 0, debtToEquityTTM: 0, dividendYieldPercentageTTM: 0 };
    
    // 1. Try Finnhub Metrics (100% Free fallback)
    try {
        const res = await fetch(`https://finnhub.io/api/v1/stock/metric?symbol=${ticker}&metric=all&token=${FINNHUB_KEY}`, { cache: 'no-store' });
        if (res.ok) {
            const data = await res.json();
            if (data.metric) {
                metrics.roeTTM = (data.metric.roeTTM || 0) / 100.0;
                metrics.roaTTM = (data.metric.roaTTM || 0) / 100.0;
                metrics.debtToEquityTTM = (data.metric["totalDebt/totalEquityQuarterly"] || 0) / 100.0;
                metrics.dividendYieldPercentageTTM = (data.metric.dividendYieldIndicatedAnnual || 0) / 100.0;
            }
        }
    } catch {}
    return metrics;
}

export async function getCompanyProfile(ticker: string) {
  const res = await fetch(`${BASE_URL}/profile/${ticker}?apikey=${FMP_API_KEY}`, { cache: 'no-store' });
  if (!res.ok) throw new Error("Failed to fetch profile");
  const data = await res.json();
  return data[0] || {};
}

export async function getHistoricalFinancials(ticker: string, limit: number = 10) {
  return [];
}

export async function getHistoricalPrices(ticker: string, days: number = 252) {
  const res = await fetch(`${BASE_URL}/historical-price-full/${ticker}?timeseries=${days}&apikey=${FMP_API_KEY}`, { cache: 'no-store' });
  if (!res.ok) return [];
  const data = await res.json();
  // FMP historical endpoint returns oldest to newest? Wait, FMP usually returns newest first in JSON.
  // We need to return oldest first for the moving average calculation or keep it consistent.
  // Actually, for SMA200, we simply need 200 prices to average, order doesn't impact Simple MA sum.
  return data.historical || [];
}

export async function getAnalystRevisions(ticker: string) {
    let revisions_score = 0.5;
    try {
        const res = await fetch(`${BASE_URL}/analyst-estimates/${ticker}?period=quarter&limit=4&apikey=${FMP_API_KEY}`, { cache: 'no-store' });
        if (res.ok) {
            const data = await res.json();
            if (data && data.length >= 2) {
                const est1 = data[0].estimatedEps || 0;
                const est2 = data[1].estimatedEps || 0;
                if (est1 > est2 * 1.05) revisions_score = 1.0;
                else if (est1 > est2) revisions_score = 0.75;
                else if (est1 < est2 * 0.95) revisions_score = 0.0;
                else if (est1 < est2) revisions_score = 0.25;
            }
        }
    } catch {}
    return { revisions_score };
}
