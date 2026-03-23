import os
import json
import joblib
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE, "ml", "model.pkl")
METRICS_PATH = os.path.join(BASE, "ml", "metrics.json")

_model = None
_mae = None

def load_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model

def load_mae(default_mae=7500):
    global _mae
    if _mae is not None:
        return _mae
    try:
        with open(METRICS_PATH, "r", encoding="utf-8") as f:
            _mae = float(json.load(f).get("MAE", default_mae))
    except Exception:
        _mae = float(default_mae)
    return _mae

def predict_price(data: dict) -> int:
    model = load_model()
    df = pd.DataFrame([data])
    pred = model.predict(df)[0]
    return int(round(float(pred)))

def predict_range(predicted_price: int):
    mae = load_mae()
    low = int(max(0, round(predicted_price - mae)))
    high = int(round(predicted_price + mae))
    return low, high, int(round(mae))

def get_price_tag(listed_price: int, predicted_price: int) -> str:
    if listed_price < predicted_price * 0.90:
        return "Underpriced"
    if listed_price > predicted_price * 1.10:
        return "Overpriced"
    return "Fair"

def get_top_feature_importance(top_n=8):
    model = load_model()
    preprocess = model.named_steps["preprocess"]
    reg = model.named_steps["model"]

    feature_names = preprocess.get_feature_names_out()
    importances = reg.feature_importances_

    pairs = list(zip(feature_names, importances))
    pairs.sort(key=lambda x: x[1], reverse=True)

    cleaned = []
    for name, score in pairs[:top_n]:
        # Cleaner labels
        label = name.replace("cat__", "").replace("num__", "")
        label = label.replace("vehicle_type_", "type: ")
        label = label.replace("brand_", "brand: ")
        label = label.replace("model_", "model: ")
        label = label.replace("fuel_type_", "fuel: ")
        label = label.replace("transmission_", "trans: ")
        label = label.replace("city_", "city: ")
        cleaned.append((label, float(score)))

    return cleaned