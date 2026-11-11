
import requests
import pandas as pd

# The script is retrieving one full year of historical climate data (2025) for a specific geographical location in Costa Rica.

url = "https://power.larc.nasa.gov/api/temporal/daily/point"

params = {
    "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR",
    "community": "AG",
    "longitude": -84.1,
    "latitude": 10.0,
    "start": "20250101",
    "end": "20251231",
    "format": "JSON"
}

response = requests.get(url, params=params, timeout=60)

response.raise_for_status()

data = response.json()

print("HTTP Status:", response.status_code)
print("Response keys:", data.keys())

parameters = data["properties"]["parameter"]

print("Available parameters:")
print(parameters.keys())

print("\nFirst 5 temperature observations:")

for date, value in list(parameters["T2M"].items())[:5]:
    print(date, value)


df = pd.DataFrame(data["properties"]["parameter"])

df.index = pd.to_datetime(df.index, format="%Y%m%d")

df.index.name = "date"

df = df.reset_index()

print(df.head())
print(df.info())

df = df.replace(-999, float("nan"))


print("Average temperature:")
print(df["T2M"].mean())

print("\nTotal annual precipitation:")
print(df["PRECTOTCORR"].sum())

print("\nHottest daily maximum temperature:")
print(df["T2M_MAX"].max())

print("\nDays with precipitation:")
print((df["PRECTOTCORR"] > 0).sum())
