#!/usr/bin/env python3
"""Galaxy Data - Dataset Intelligence Platform

Usage:
    python main.py "your dataset query"
    python main.py "Tamil OCR datasets" --extract
    python main.py "sentiment analysis" --max-results 20
    python main.py "climate data" --extract --max-pages 50 --max-results 15
"""
import sys
import logging
import argparse
from galaxy.types import GatewayRequest
from galaxy.orchestrator.orchestrator import Orchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    parser = argparse.ArgumentParser(
        description="Galaxy Data - Dataset Intelligence Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python main.py "sentiment analysis dataset"
  python main.py "image classification" --max-results 20
  python main.py "Indian food recipes" --extract --max-pages 30
  python main.py "stock market time series" --extract --max-results 15 --max-pages 40
  python main.py "audio speech recognition" --max-results 10
""")
    parser.add_argument("query", help="Natural language query for datasets")
    parser.add_argument("--extract", action="store_true",
                        help="Enable web extraction (scrape Wikipedia/Wikidata for data)")
    parser.add_argument("--max-results", type=int, default=10,
                        help="Max datasets per source (default: 10, higher = more data)")
    parser.add_argument("--max-pages", type=int, default=20,
                        help="Max pages to scan for web extraction (default: 20)")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--user-id", default="default", help="User ID")
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("  🌌 Galaxy Data - Dataset Intelligence Platform")
    print("="*60)
    print(f"  Query:          {args.query}")
    print(f"  Max results:    {args.max_results} per source")
    print(f"  Web extraction: {'enabled' if args.extract else 'disabled'}")
    if args.extract:
        print(f"  Max pages:      {args.max_pages}")
    print("="*60 + "\n")
    
    # Create request
    request = GatewayRequest(query=args.query, user_id=args.user_id)
    
    # Run pipeline
    orchestrator = Orchestrator()
    result = orchestrator.run(
        request,
        interactive=args.interactive,
        enable_web_extraction=args.extract,
        max_results=args.max_results,
        max_pages=args.max_pages,
    )
    
    # Print results
    print("\n" + "="*60)
    print("  📊 RESULTS")
    print("="*60)
    print(f"  Session:     {result.session_id}")
    print(f"  Output:      {result.package_path}")
    print(f"  Datasets:    {result.datasets_count}")
    print(f"  Total rows:  {result.total_samples}")
    print(f"  Quality:     {result.quality_score:.2f}")
    print(f"  Size:        {result.size_bytes / 1024:.1f} KB")
    print("="*60 + "\n")
    
    # List output files
    from pathlib import Path
    final = Path(result.package_path)
    if final.exists():
        print("  Output files:")
        for f in sorted(final.iterdir()):
            size = f.stat().st_size
            if size >= 1024*1024:
                size_str = f"{size/1024/1024:.1f} MB"
            elif size >= 1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size} B"
            print(f"    {f.name:50s} {size_str:>10s}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
