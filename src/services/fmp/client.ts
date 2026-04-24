const FMP_API_KEY = process.env.FMP_API_KEY || "ZopJDkQbPkxpeehQrJtxGAQRVWJnkiop";
const BASE_URL = "https://financialmodelingprep.com/api/v3";

export async function getQuote(ticker: string) {
  const res = await fetch(`${BASE_URL}/quote/${ticker}?apikey=${FMP_API_KEY}`, { cache: 'no-store' });
  if (!res.ok) throw new Error("Failed to fetch quote");
  const data = await res.json();
  return data[0] || {}; 
}

export async function getFinancialGrowth(ticker: string) {
  const res = await fetch(`${BASE_URL}/financial-growth/${ticker}?limit=1&apikey=${FMP_API_KEY}`, { cache: 'no-store' });
  if (!res.ok) throw new Error("Failed to fetch financial growth");
  const data = await res.json();
  return data[0] || {};
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

// Keep stubs for backwards compatibility if needed elsewhere
export async function getHistoricalFinancials(ticker: string, limit: number = 10) {
  return [];
}

export async function getHistoricalPrices(ticker: string, days: number = 252) {
  const res = await fetch(`${BASE_URL}/historical-price-full/${ticker}?timeseries=${days}&apikey=${FMP_API_KEY}`, { cache: 'no-store' });
  if (!res.ok) return [];
  const data = await res.json();
  return data.historical || [];
}
