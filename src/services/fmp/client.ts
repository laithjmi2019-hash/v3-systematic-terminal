const FMP_API_KEY = process.env.FMP_API_KEY || "ZopJDkQbPkxpeehQrJtxGAQRVWJnkiop";
const BASE_URL = "https://financialmodelingprep.com/api/v3";

export async function getQuote(ticker: string) {
  const res = await fetch(`${BASE_URL}/quote/${ticker}?apikey=${FMP_API_KEY}`, { cache: 'no-store' });
  if (!res.ok) throw new Error("Failed to fetch quote");
  const data = await res.json();
  return data[0] || {}; 
}

export async function getFinancialGrowth(ticker: string) {
  const res = await fetch(`${BASE_URL}/financial-growth/${ticker}?limit=3&apikey=${FMP_API_KEY}`, { cache: 'no-store' });
  if (!res.ok) throw new Error("Failed to fetch financial growth");
  const data = await res.json();
  
  if (!data || data.length === 0) {
      return { revenueGrowth: 0, netIncomeGrowth: 0, epsgrowth: 0, yearsAveraged: 0 };
  }
  
  const rev_avg = data.reduce((acc: number, val: any) => acc + (val.revenueGrowth || 0), 0) / data.length;
  const eps_avg = data.reduce((acc: number, val: any) => acc + (val.epsgrowth || val.netIncomeGrowth || 0), 0) / data.length;

  return {
      revenueGrowth: rev_avg,
      netIncomeGrowth: eps_avg,
      epsgrowth: eps_avg,
      yearsAveraged: data.length
  };
}

export async function getKeyMetrics(ticker: string) {
  const res = await fetch(`${BASE_URL}/key-metrics-ttm/${ticker}?apikey=${FMP_API_KEY}`, { cache: 'no-store' });
  if (!res.ok) throw new Error("Failed to fetch key metrics");
  const data = await res.json();
  return data[0] || {};
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
