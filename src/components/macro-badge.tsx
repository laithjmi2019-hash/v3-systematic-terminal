import { MacroState } from "@/types";
import { Badge } from "@/components/ui/badge";

export function MacroBadge({ state }: { state: MacroState }) {
  const getBadgeColor = () => {
    switch(state.phase) {
      case "EXPANSION": return "bg-green-500/20 text-green-500 hover:bg-green-500/30 border-green-500/50";
      case "LATE_EXPANSION": return "bg-orange-500/20 text-orange-500 hover:bg-orange-500/30 border-orange-500/50";
      case "PEAK": return "bg-red-500/20 text-red-500 hover:bg-red-500/30 border-red-500/50";
      case "RESET": return "bg-blue-500/20 text-blue-500 hover:bg-blue-500/30 border-blue-500/50";
      default: return "";
    }
  };

  return (
    <div className="flex items-center gap-3">
      <div className="flex flex-col text-right">
        <span className="text-xs text-muted-foreground uppercase tracking-widest">Macro Cycle</span>
        <span className="text-sm font-medium">Fed Rate {state.rateTrend}</span>
      </div>
      <Badge variant="outline" className={`px-3 py-1 ${getBadgeColor()}`}>
        {state.phase.replace("_", " ")}
      </Badge>
    </div>
  );
}
