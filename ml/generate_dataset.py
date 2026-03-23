import pandas as pd
import random

vehicle_types = ["car", "bike", "truck", "auto"]
brands = {
    "car": ["Maruti", "Hyundai", "Honda", "Tata"],
    "bike": ["Honda", "Hero", "Yamaha", "TVS"],
    "truck": ["Tata", "Ashok Leyland"],
    "auto": ["Bajaj", "TVS"]
}

fuel_types = ["Petrol", "Diesel", "CNG"]
transmissions = ["Manual", "Automatic"]
cities = ["Bhubaneswar", "Ranchi", "Raipur", "Bhopal", "Indore"]

data = []

for _ in range(1500):
    vtype = random.choice(vehicle_types)
    brand = random.choice(brands[vtype])
    model = "Model_" + str(random.randint(1,5))
    year = random.randint(2010, 2023)
    kms = random.randint(5000, 150000)
    fuel = random.choice(fuel_types)
    transmission = random.choice(transmissions)
    owner = random.randint(1,3)
    city = random.choice(cities)
    condition = random.randint(1,5)

    # price formula (logic based)
    base_price = 800000 if vtype == "car" else 70000 if vtype == "bike" else 500000 if vtype == "truck" else 150000
    depreciation = (2024 - year) * 20000
    price = base_price - depreciation - (kms * 2) + (condition * 10000)
    price = max(price, 20000)

    data.append([
        vtype, brand, model, year, kms, fuel, transmission,
        owner, city, condition, int(price)
    ])

df = pd.DataFrame(data, columns=[
    "vehicle_type","brand","model","year","kms","fuel_type",
    "transmission","owner_count","city","condition_score","price"
])

df.to_csv("vehicles.csv", index=False)
print("Dataset created with 1500 rows")