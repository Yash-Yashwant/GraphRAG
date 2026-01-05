import torch
import transformers
import marker
import surya

print(f"Torch version: {torch.__version__}")
print(f"Transformers version: {transformers.__version__}")
print(f"Marker version: {marker.__version__ if hasattr(marker, '__version__') else 'unknown'}")
print(f"Surya version: {surya.__version__ if hasattr(surya, '__version__') else 'unknown'}")
