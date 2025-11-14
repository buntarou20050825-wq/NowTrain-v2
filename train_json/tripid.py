import pandas as pd

# GTFSのtrips.txtを読み込み
df = pd.read_csv('C:/Users/bunta/NowTrain-v2/train_json/trips.json')

# trip_idのサンプルを表示
print(df['trip_id'].head(20))

# 列車番号が含まれているか検索
print(df[df['trip_id'].str.contains('870T|844T', na=False)])
