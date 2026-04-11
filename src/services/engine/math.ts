export function clamp(value: number, min: number, max: number): number {
  if (Number.isNaN(value)) value = 0; // fallback securely for null fields
  return Math.max(min, Math.min(max, value));
}

// Normalizes a score where higher is better
export function normalize(value: number, min: number, max: number): number {
  if (value <= min) return 0;
  if (value >= max) return 1;
  return clamp((value - min) / (max - min), 0, 1);
}

// Normalizes a score where lower is better (e.g. Debt, PE)
export function inverseNormalize(value: number, min: number, max: number): number {
  if (value <= min) return 1;
  if (value >= max) return 0;
  return clamp((max - value) / (max - min), 0, 1);
}

// Computes Sample Standard Deviation
export function stdDev(arr: number[]): number {
  if (!arr || arr.length <= 1) return 0;
  const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
  const variance = arr.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / (arr.length - 1);
  return Math.sqrt(variance);
}

export function mean(arr: number[]): number {
    if (!arr || arr.length === 0) return 0;
    return arr.reduce((a, b) => a + b, 0) / arr.length;
}

// Computes the Volatility Penalty = min(std_dev / abs(mean), 0.5)
export function calculateVolatilityPenalty(series: number[]): number {
  const m = mean(series);
  if (m === 0) return 0.5; // High penalty if average is literally 0 to avoid Infinity 
  const sd = stdDev(series);
  return Math.min(sd / Math.abs(m), 0.5);
}
