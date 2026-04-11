import { EngineResult, LLMInsight } from "@/types";

const LLM_API_KEY = process.env.OPENAI_API_KEY;

export async function generateAIExplanation(result: EngineResult): Promise<LLMInsight> {
  // If no API key, use fallback rule-based presentation matching the schema
  if (!LLM_API_KEY) {
    const fallback: LLMInsight = {
      verdict: result.verdict,
      reason: result.verdict === "PASS" ? 
              "Strong fundamental metrics combining high margins and reasonable valuation." : 
              "Financial structure or valuation fails institutional threshold checks.",
      strengths: result.totalScore > 50 ? ["High absolute points in moat/profitability.", "Stable standard deviation averages."] : ["No notable quantitative strengths detected."],
      risks: result.redFlags.length > 0 ? result.redFlags.map(f => f.message) : ["General market risk.", "Volatility penalty impacts."],
      action: result.verdict === "AVOID" ? "Avoid completely" : result.verdict === "PASS" ? "Accumulation zone" : "Wait for valuation correction"
    };
    return fallback;
  }

  // Real LLM call pseudo-code for structured JSON output
  /*
  const response = await fetch("https://api.openai.com/v1/chat/completions", ...);
  const data = await response.json();
  return JSON.parse(data.choices[0].message.content); // Enforced to LLMInsight
  */
  
  return {
    verdict: "WATCH",
    reason: "API simulation bypass.",
    strengths: [],
    risks: [],
    action: "Do nothing"
  };
}
