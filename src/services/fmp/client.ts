// FMP API Client stub
const FMP_API_KEY = process.env.FMP_API_KEY;
const BASE_URL = "https://financialmodelingprep.com/api/v3";

export async function getQuote(ticker: string) {
  if (!FMP_API_KEY) return mockQuote(ticker);
  
  const res = await fetch(`${BASE_URL}/quote/${ticker}?apikey=${FMP_API_KEY}`);
  if (!res.ok) throw new Error("Failed to fetch quote");
  const data = await res.json();
  return data[0]; // Needs mapping to our Quote type
}

export async function getHistoricalFinancials(ticker: string, limit: number = 10) {
  if (!FMP_API_KEY) return mockFinancials(ticker);
  // Full impl missing for brevity
  return [];
}

export async function getHistoricalPrices(ticker: string, days: number = 252) {
  if (!FMP_API_KEY) return mockPrices(ticker, days);
  
  // daily chart
  const res = await fetch(`${BASE_URL}/historical-price-full/${ticker}?timeseries=${days}&apikey=${FMP_API_KEY}`);
  if (!res.ok) throw new Error("Failed to fetch historical prices");
  const data = await res.json();
  return data.historical || [];
}

export async function getCompanyProfile(ticker: string) {
    if (!FMP_API_KEY) return mockProfile(ticker);
    
    const res = await fetch(`${BASE_URL}/profile/${ticker}?apikey=${FMP_API_KEY}`);
    if (!res.ok) throw new Error("Failed to fetch profile");
    const data = await res.json();
    return data[0] || {};
}

function mockQuote(ticker: string) { return {}; }
function mockFinancials(ticker: string) { return []; }
function mockPrices(ticker: string, days: number) { 
    // Return dummy price array
    return Array.from({length: days}).map((_, i) => ({ close: 100 + Math.random() * 10 }));
}
function mockProfile(ticker: string) {
    return { sector: "Technology", industry: "Software" };
}
