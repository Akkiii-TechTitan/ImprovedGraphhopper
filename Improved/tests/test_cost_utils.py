import os
import sys

# Always add the parent directory (Improved) to Python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from cost_utils import CostConfig, estimate_trip_cost



def test_car_cost_basic():
    # 100 km, 10 km/L, 100 PHP/L -> 100/10 = 10L * 100 = 1000 PHP
    cfg = CostConfig(car_km_per_liter=10, fuel_price_per_liter=100)
    cost = estimate_trip_cost(100, "car", cfg)
    assert cost == 1000


def test_bike_cost():
    # 10 km, 1.5 PHP/km -> 15 PHP
    cfg = CostConfig(bike_maintenance_per_km=1.5)
    cost = estimate_trip_cost(10, "bike", cfg)
    assert cost == 15


def test_airplane_cost():
    # 20 km, 5 PHP/km -> 100 PHP
    cfg = CostConfig(airplane_cost_per_km=5)
    cost = estimate_trip_cost(20, "airplane", cfg)
    assert cost == 100


def test_unknown_vehicle_returns_zero():
    cfg = CostConfig()
    cost = estimate_trip_cost(50, "hoverboard", cfg)
    assert cost == 0.0
