#!/usr/bin/env python3
"""Galaxy Data - Dataset Intelligence Platform

Usage:
    python main.py "sentiment analysis dataset"
    python main.py "face images" --modality images --max-results 20
    python main.py "climate data" --extract --min-size 50MB
    python main.py --interactive
"""
import sys
import logging
import argparse
from galaxy.types import GatewayRequest
from galaxy.orchestrator.orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)


def parse_size(size_str: str) -> int:
    """Parse size string like '100MB' to bytes."""
    size_str = size_str.strip().upper()
    multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
    for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if size_str.endswith(suffix):
            return int(float(size_str[:-len(suffix)]) * mult)
    return int(size_str)


def human_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def main():
    parser = argparse.ArgumentParser(
        description="Galaxy Data - Dataset Intelligence Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python main.py "sentiment analysis dataset"
  python main.py "face detection" --modality images --max-results 20
  python main.py "Indian food recipes" --extract --max-pages 30
  python main.py "stock market data" --min-size 50MB --max-results 20
  python main.py --interactive
""")
    parser.add_argument("query", nargs='?', help="Natural language query")
    parser.add_argument("--extract", action="store_true",
                        help="Enable web extraction (scrape web for data)")
    parser.add_argument("--max-results", type=int, default=10,
                        help="Max datasets per source (default: 10)")
    parser.add_argument("--max-pages", type=int, default=20,
                        help="Max pages for web extraction (default: 20)")
    parser.add_argument("--min-size", type=str, default="0",
                        help="Min data size target, e.g. 10MB, 1GB (default: 0)")
    parser.add_argument("--modality", type=str, default="mixed",
                        choices=["mixed", "images", "audio", "video", "tabular", "text"],
                        help="Filter by data type (default: mixed)")
    parser.add_argument("--interactive", action="store_true", help="Interactive REPL mode")
    parser.add_argument("--user-id", default="default", help="User ID")
    
    args = parser.parse_args()
    
    # Interactive mode
    if args.interactive:
        from galaxy.gateway.gateway import Gateway
        gw = Gateway()
        gw.interactive_mode()
        return 0
    
    if not args.query:
        parser.print_help()
        return 1
    
    min_size = parse_size(args.min_size)
    
    print("\n" + "="*60)
    print("  🌌 Galaxy Data - Dataset Intelligence Platform")
    print("="*60)
    print(f"  Query:          {args.query}")
    print(f"  Max results:    {args.max_results} per source")
    print(f"  Modality:       {args.modality}")
    print(f"  Web extraction: {'enabled' if args.extract else 'disabled'}")
    if args.extract:
        print(f"  Max pages:      {args.max_pages}")
    if min_size > 0:
        print(f"  Min size:       {human_size(min_size)}")
    print("="*60 + "\n")
    
    request = GatewayRequest(query=args.query, user_id=args.user_id)
    
    orchestrator = Orchestrator()
    result = orchestrator.run(
        request,
        enable_web_extraction=args.extract,
        max_results=args.max_results,
        max_pages=args.max_pages,
        min_size_bytes=min_size,
        modality=args.modality,
    )
    
    # Print results
    print("\n" + "="*60)
    print("  📊 RESULTS")
    print("="*60)
    print(f"  Session:     {result.session_id}")
    print(f"  Output:      {result.package_path}")
    print(f"  Datasets:    {result.datasets_count}")
    print(f"  Total rows:  {result.total_samples:,}")
    print(f"  Quality:     {result.quality_score:.2f}")
    print(f"  Size:        {human_size(result.size_bytes)}")
    print("="*60 + "\n")
    
    # List output structure
    from pathlib import Path
    final = Path(result.package_path)
    if final.exists():
        print("  Output structure:")
        for item in sorted(final.iterdir()):
            if item.is_dir():
                data_dir = item / "data"
                if data_dir.exists():
                    file_count = len(list(data_dir.iterdir()))
                    dir_size = sum(f.stat().st_size for f in data_dir.iterdir() if f.is_file())
                    print(f"    📁 {item.name}/ ({file_count} files, {human_size(dir_size)})")
                else:
                    print(f"    📁 {item.name}/")
            else:
                print(f"    📄 {item.name} ({human_size(item.stat().st_size)})")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
