import os
import json
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE, "vehicles.csv")
MODEL_PATH = os.path.join(BASE, "model.pkl")
ENC_PATH = os.path.join(BASE, "encoders.pkl")
METRICS_PATH = os.path.join(BASE, "metrics.json")

df = pd.read_csv(CSV_PATH)

target = "price"
features = ["vehicle_type","brand","model","year","kms","fuel_type","transmission","owner_count","city","condition_score"]

df = df.dropna(subset=features + [target])

X = df[features]
y = df[target]

cat_cols = ["vehicle_type","brand","model","fuel_type","transmission","city"]
num_cols = ["year","kms","owner_count","condition_score"]

preprocess = ColumnTransformer(
    transformers=[
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
        ("num", "passthrough", num_cols),
    ]
)

model = RandomForestRegressor(
    n_estimators=400,
    random_state=42,
    n_jobs=-1
)

pipe = Pipeline([
    ("preprocess", preprocess),
    ("model", model)
])

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

pipe.fit(X_train, y_train)

pred = pipe.predict(X_test)
mae = float(mean_absolute_error(y_test, pred))
r2 = float(r2_score(y_test, pred))

joblib.dump(pipe, MODEL_PATH)
joblib.dump({"features": features}, ENC_PATH)

with open(METRICS_PATH, "w", encoding="utf-8") as f:
    json.dump({"MAE": mae, "R2": r2, "rows": int(len(df))}, f, indent=2)

print("Saved:", MODEL_PATH)
print("Saved:", ENC_PATH)
print("Saved:", METRICS_PATH)
print("MAE:", round(mae, 2))
print("R2:", round(r2, 4))