"""Gateway — interactive and batch mode entry point."""
import sys
import logging
from pathlib import Path
from galaxy.types import GatewayRequest
from galaxy.orchestrator.orchestrator import Orchestrator

log = logging.getLogger("galaxy.gateway")


class Gateway:
    """Interactive gateway for Galaxy Data."""
    
    def __init__(self):
        self.orchestrator = Orchestrator()
        self.history: list[dict] = []
    
    def interactive_mode(self):
        """Run in interactive REPL mode."""
        print("\n" + "="*60)
        print("  🌌 Galaxy Data — Interactive Mode")
        print("="*60)
        print("  Commands:")
        print("    search <query>     — Search and collect datasets")
        print("    extract <query>    — Search + web extraction")
        print("    set max-results N  — Set max results per source")
        print("    set max-pages N    — Set max pages for extraction")
        print("    set min-size NMB   — Set minimum data size")
        print("    set modality TYPE  — Filter: images|audio|video|tabular|text|mixed")
        print("    status             — Show current settings")
        print("    history            — Show past queries")
        print("    exit               — Quit")
        print("="*60 + "\n")
        
        settings = {
            "max_results": 10,
            "max_pages": 20,
            "min_size_bytes": 0,
            "modality": "mixed",
        }
        
        while True:
            try:
                cmd = input("\n🌌 galaxy> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break
            
            if not cmd:
                continue
            
            if cmd.lower() in ('exit', 'quit', 'q'):
                print("Goodbye!")
                break
            
            elif cmd.lower() == 'status':
                print(f"  max_results:  {settings['max_results']}")
                print(f"  max_pages:    {settings['max_pages']}")
                print(f"  min_size:     {settings['min_size_bytes']} bytes")
                print(f"  modality:     {settings['modality']}")
            
            elif cmd.lower() == 'history':
                if not self.history:
                    print("  No queries yet.")
                for h in self.history:
                    print(f"  [{h['session_id']}] {h['query']} → {h['datasets']} datasets")
            
            elif cmd.lower().startswith('set '):
                parts = cmd.split(maxsplit=2)
                if len(parts) == 3:
                    key, val = parts[1].replace('-', '_'), parts[2]
                    if key == 'max_results':
                        settings['max_results'] = int(val)
                    elif key == 'max_pages':
                        settings['max_pages'] = int(val)
                    elif key == 'min_size':
                        settings['min_size_bytes'] = self._parse_size(val)
                    elif key == 'modality':
                        settings['modality'] = val.lower()
                    print(f"  ✅ {key} = {settings.get(key, val)}")
                else:
                    print("  Usage: set <key> <value>")
            
            elif cmd.lower().startswith('search ') or cmd.lower().startswith('extract '):
                enable_extract = cmd.lower().startswith('extract ')
                query = cmd.split(maxsplit=1)[1] if ' ' in cmd else cmd
                
                print(f"\n  Searching: {query}")
                print(f"  Mode: {'search + extract' if enable_extract else 'search only'}")
                print(f"  Settings: {settings}\n")
                
                request = GatewayRequest(query=query)
                try:
                    result = self.orchestrator.run(
                        request,
                        enable_web_extraction=enable_extract,
                        max_results=settings['max_results'],
                        max_pages=settings['max_pages'],
                        min_size_bytes=settings['min_size_bytes'],
                        modality=settings['modality'],
                    )
                    
                    self.history.append({
                        "session_id": result.session_id,
                        "query": query,
                        "datasets": result.datasets_count,
                        "quality": result.quality_score,
                    })
                    
                    print(f"\n  ✅ Done: {result.datasets_count} datasets, quality={result.quality_score:.2f}")
                    print(f"  📁 Output: {result.package_path}")
                except Exception as e:
                    print(f"  ❌ Error: {e}")
            
            else:
                print(f"  Unknown command: {cmd}")
                print("  Type 'search <query>' or 'help'")
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '100MB' to bytes."""
        size_str = size_str.strip().upper()
        multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
        for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
            if size_str.endswith(suffix):
                return int(float(size_str[:-len(suffix)]) * mult)
        return int(size_str)
    
    def batch_run(self, query: str, **kwargs):
        """Run a single batch query."""
        request = GatewayRequest(query=query)
        return self.orchestrator.run(request, **kwargs)
