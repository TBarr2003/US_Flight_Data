import subprocess
import sys

steps = [
    ("Raw Ingestion", "src.ingestion.ingest_raw"),
    ("Cleaning", "src.cleaning.clean"),
    ("Aggregation", "src.aggregation.aggregate"),
]

for name, module in steps:
    print(f"\n{'='*50}")
    print(f"Running: {name}")
    print('='*50)
    result = subprocess.run(
        [sys.executable, "-m", module],
        capture_output=False
    )
    if result.returncode != 0:
        print(f"ERROR: {name} failed")
        sys.exit(1)
    print(f"SUCCESS: {name} complete")

print("\nPipeline complete!")