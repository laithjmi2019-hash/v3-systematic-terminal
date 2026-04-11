import { getMacroState } from "@/services/engine/macro";
import { MacroBadge } from "./macro-badge";
import { Terminal } from "lucide-react";

export async function Navbar() {
  const macroState = await getMacroState();
  
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center px-4 justify-between">
        <div className="flex items-center gap-3">
          <Terminal className="h-6 w-6 text-primary" />
          <span className="font-bold font-mono tracking-tight text-lg">SYS_TERMINAL</span>
        </div>
        
        <div className="flex flex-1 items-center space-x-2 justify-end">
          <div className="hidden md:flex relative w-full max-w-sm mr-4 items-center">
            {/* MVP Command bar mock */}
            <div className="flex w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-1.5 text-sm shadow-sm opacity-50 cursor-not-allowed">
              <span className="text-muted-foreground flex items-center gap-2">
                <span className="text-xs border px-1.5 py-0.5 rounded leading-none">⌘</span>
                <span>Search ticker...</span>
              </span>
            </div>
          </div>
          <MacroBadge state={macroState} />
        </div>
      </div>
    </header>
  );
}
