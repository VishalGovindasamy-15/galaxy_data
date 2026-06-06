#!/usr/bin/env python3
"""Galaxy Data - Dataset Intelligence Platform

Usage:
    python main.py "your dataset query"
    python main.py "Tamil OCR datasets" --extract
    python main.py "sentiment analysis" --interactive
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
    parser = argparse.ArgumentParser(description="Galaxy Data - Dataset Intelligence Platform")
    parser.add_argument("query", help="Natural language query for datasets")
    parser.add_argument("--extract", action="store_true", help="Enable web extraction if no datasets found")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--user-id", default="default", help="User ID")
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("  Galaxy Data - Dataset Intelligence Platform")
    print("="*60)
    print(f"  Query: {args.query}")
    print(f"  Web extraction: {'enabled' if args.extract else 'disabled'}")
    print("="*60 + "\n")
    
    # Create request
    request = GatewayRequest(query=args.query, user_id=args.user_id)
    
    # Run pipeline
    orchestrator = Orchestrator()
    result = orchestrator.run(
        request,
        interactive=args.interactive,
        enable_web_extraction=args.extract,
    )
    
    # Print results
    print("\n" + "="*60)
    print("  RESULTS")
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
            print(f"    {f.name:40s} {size:>10,} bytes")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
