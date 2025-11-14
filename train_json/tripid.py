from google.transit import gtfs_realtime_pb2
import gzip

feed = gtfs_realtime_pb2.FeedMessage()
with open(r"C:\Users\bunta\NowTrain-v2\train_json\jreast_odpt_train_vehicle (5)", "rb") as f:
    data = f.read()


# gzip 圧縮されてる場合はここで解凍
# data = gzip.decompress(data)

feed.ParseFromString(data)

for entity in feed.entity[:5]:
    if entity.HasField("vehicle"):
        v = entity.vehicle
        print("entity_id:", entity.id)
        print("trip_id:", v.trip.trip_id)
        print("route_id:", v.trip.route_id)
        print("timestamp:", v.timestamp)
        print("---")
