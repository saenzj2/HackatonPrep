import pandas as pd

# EcoCrop dataset
url = "https://digital-atlas.s3.amazonaws.com/cdh/data/ecocrop/ecocrop.parquet"

# Load Parquet into a pandas DataFrame
df = pd.read_parquet(url)

# Inspect the dataset
print(df.shape)           # (rows, columns)
print(df.columns.tolist()) # Column names
print(df.head())          # First 5 rows


maize = df[
    df["scientificname"]
    .str.contains("Zea mays", case=False, na=False)
].iloc[0]

print(maize)