from marker.models import load_all_models
print("Loading models...")
try:
    models = load_all_models()
    print("Models loaded successfully.")
except Exception as e:
    print(f"Caught exception: {e}")
    import traceback
    traceback.print_exc()
