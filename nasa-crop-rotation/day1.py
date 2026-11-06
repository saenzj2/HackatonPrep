import pandas as pd
from io import StringIO 

csv_data = """farm_id,region,crop,rainfall_mm,temperature_c,soil_ph
F001,Alajuela,Coffee,180,24,5.8
F002,Heredia,Beans,120,22,6.2
F003,Guanacaste,Corn,65,32,6.5
F004,Limon,Banana,260,28,6.1
F005,Cartago,Potato,140,18,5.5
F006,Alajuela,Beans,175,25,6.4
F007,Guanacaste,Corn,45,34,6.8
F008,Limon,Banana,,29,6.0
F009,Heredia,Coffee,195,23,
F010,Cartago,Potato,155,17,5.7
F011,Alajuela,Corn,110,27,6.3
F012,Guanacaste,Beans,70,31,6.6
"""

df = pd.read_csv(StringIO(csv_data))

#print(df)

#print(df.shape)          # Rows and columns
#print(df.columns)        # Column names
#print(df.dtypes)         # Data types
#print(df.info())         # Structure and missing values
#print(df.describe())     # Numerical statistics
#print(df.isna().sum())   # Missing values per column

#selecting a single column
#print(df['rainfall_mm'])

#selecting multiple columns
#print(df[["region","crop","rainfall_mm"]])

#selecting first 3 rows
#print(df.iloc[0:3])

### --- FILTERING RECORDS --- ###
#farms receiving less than 100 mm of rainfall
dry_farms = df[df["rainfall_mm"] < 100]
#print(dry_farms)

#combining conditions with AND, OR & |
#farms with low rainfall and high temperature
hot_day = df[(df["rainfall_mm"] < 100) & (df["temperature_c"] > 30)]
#print(hot_day)

#all farms growing beans
bean = df[df["crop"]=="Beans"]
#print(bean)

#Farms with soil pH between 6.0 and 7.0.
#ph_range = df[df["soil_ph"].between(6.0, 7.0)]
soil_range = df[(df["soil_ph"]>6.0) & (df["soil_ph"]<7.0)]
#print(soil_range)

#Farms in Guanacaste with temperatures above 30°C.
guana_hot = df[(df["region"] == "Guanacaste")&(df["temperature_c"] > 30)]
#print(guana_hot)

### --- DATA CLEANING AND TRANFORMATIONS --- ###
#Detecting missing data
#print(df.isna().sum())
#print(df[df.isna().any(axis=1)])  #Print all rows in the DataFrame that contain at least one missing value

#Handlemissing values by filling them wiht their respective column medians
clean_df = df.copy()
clean_df["rainfall_mm"] = clean_df["rainfall_mm"].fillna(clean_df["rainfall_mm"].median())
clean_df["soil_ph"] = clean_df["soil_ph"].fillna(clean_df["soil_ph"].median())
print(clean_df)

#Creating new columns
def rainfall_category(mm):
    if mm < 100:
        return "Low"
    elif mm < 200:
        return "Moderate"
    return "High"

clean_df["rainfall_category"] = (clean_df["rainfall_mm"].apply(rainfall_category))
#print(clean_df[["farm_id", "rainfall_mm", "rainfall_category"]])

def high_temperature(temp):
    if temp > 30:
        return True
    return False

clean_df["high_temperature"] = clean_df["temperature_c"].apply(high_temperature)
#print(clean_df[["farm_id", "temperature_c", "high_temperature"]])

#### --- GROUP BY AND AGGREGATION --- ###
#Average rainfall by region
regional_rainfall = (clean_df.groupby("region")["rainfall_mm"].mean())
#print(regional_rainfall)

#Multiple Aggregations
#Create a column named avg_rainfall, using the rainfall_mm column, and calculate its mean for each region.
summary = (clean_df.groupby("region").agg(farm_count=("farm_id", "count"),avg_rainfall=("rainfall_mm", "mean"),avg_temperature=("temperature_c", "mean"),min_soil_ph=("soil_ph", "min"))).reset_index()
#print(summary)

summaryChallenge = (clean_df.groupby("crop").agg(n_farms=("farm_id","count"), avg_rainfall=("rainfall_mm", "mean"), avg_soilph=("soil_ph", "mean"))).reset_index()

sorted_challenge = summaryChallenge.sort_values(by="avg_rainfall", ascending=False)

print(sorted_challenge)

# Merging DataSets