"""
Standalone Test Script for GTFS-RT Integration
Tests GTFSRTClient and GTFSInterpolator with sample data
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from gtfs_loader import GTFSLoader
from gtfs_rt_client import GTFSRTClient
from gtfs_interpolator import GTFSInterpolator


async def main():
    print("=" * 80)
    print("GTFS-RT Integration Test")
    print("=" * 80)
    print()

    # 1. Load static GTFS data
    print("[1] Loading static GTFS data...")
    gtfs_path = Path(__file__).parent.parent / "train_json"
    gtfs_loader = GTFSLoader(str(gtfs_path))
    print()

    # 2. Initialize GTFS-RT client
    print("[2] Initializing GTFS-RT client...")
    rt_feed_path = gtfs_path / "jreast_odpt_train_vehicle (5)"
    if not rt_feed_path.exists():
        print(f"ERROR: GTFS-RT feed not found at {rt_feed_path}")
        return

    rt_client = GTFSRTClient(feed_path=str(rt_feed_path))
    print(f"    Feed path: {rt_feed_path}")
    print()

    # 3. Fetch vehicles from GTFS-RT
    print("[3] Fetching vehicles from GTFS-RT feed...")
    vehicles = await rt_client.get_vehicles()
    print(f"    Total vehicles: {len(vehicles)}")
    print()

    # 4. Initialize interpolator
    print("[4] Initializing interpolator...")
    interpolator = GTFSInterpolator(gtfs_loader)
    print()

    # 5. Test interpolation for first 10 vehicles
    print("[5] Testing interpolation for sample vehicles...")
    print("-" * 80)

    success_count = 0
    fail_count = 0

    # Show detailed info for first 10 vehicles
    for i, vehicle in enumerate(vehicles[:10]):
        print(f"\nVehicle #{i+1}:")
        print(f"  entity_id: {vehicle['entity_id']}")
        print(f"  trip_id: {vehicle['trip_id']}")
        print(f"  timestamp: {vehicle['timestamp']}")

        # Calculate position
        position = interpolator.calculate_position(
            trip_id=vehicle['trip_id'],
            timestamp=vehicle['timestamp'],
            entity_id=vehicle['entity_id']
        )

        if position:
            print(f"  ✓ Position calculated:")
            print(f"    lat: {position['lat']:.6f}")
            print(f"    lng: {position['lng']:.6f}")
            print(f"    progress: {position['progress']:.2%}")
            print(f"    from_stop: {position['from_stop_id']}")
            print(f"    to_stop: {position.get('to_stop_id', 'N/A')}")
            print(f"    interpolated: {position['interpolated']}")
            success_count += 1
        else:
            print(f"  ✗ Position calculation failed")
            fail_count += 1

    print("\n" + "-" * 80)

    # 6. Summary statistics for all vehicles
    print("\n[6] Summary for all vehicles:")
    print("-" * 80)

    total_vehicles = len(vehicles)
    total_success = 0
    total_fail = 0
    interpolated_count = 0
    fallback_count = 0

    for vehicle in vehicles:
        position = interpolator.calculate_position(
            trip_id=vehicle['trip_id'],
            timestamp=vehicle['timestamp'],
            entity_id=vehicle['entity_id']
        )

        if position:
            total_success += 1
            if position['interpolated']:
                interpolated_count += 1
            else:
                fallback_count += 1
        else:
            total_fail += 1

    print(f"Total vehicles: {total_vehicles}")
    print(f"  Success: {total_success} ({total_success/total_vehicles*100:.1f}%)")
    print(f"    - Interpolated: {interpolated_count}")
    print(f"    - Fallback: {fallback_count}")
    print(f"  Failed: {total_fail} ({total_fail/total_vehicles*100:.1f}%)")
    print()

    # 7. Check trip_id matching
    print("[7] Checking trip_id matching with static GTFS...")
    print("-" * 80)

    matched_trips = 0
    unmatched_trips = []

    for vehicle in vehicles[:20]:  # Check first 20
        trip_id = vehicle['trip_id']
        if trip_id in gtfs_loader.stop_times:
            matched_trips += 1
        else:
            unmatched_trips.append(trip_id)

    print(f"Checked: 20 vehicles")
    print(f"  Matched: {matched_trips}")
    print(f"  Unmatched: {len(unmatched_trips)}")

    if unmatched_trips:
        print(f"\nUnmatched trip_ids (sample):")
        for trip_id in unmatched_trips[:5]:
            print(f"  - {trip_id}")

    print()
    print("=" * 80)
    print("Test completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
