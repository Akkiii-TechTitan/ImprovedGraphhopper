# cost_utils.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class CostConfig:
    """Configuration for estimating trip cost (PHP)."""
    car_km_per_liter: float = 12.0
    fuel_price_per_liter: float = 75.0
    bike_maintenance_per_km: float = 1.0
    foot_cost_per_km: float = 0.0
    airplane_cost_per_km: float = 8.0  # rough per-km estimate


def estimate_trip_cost(
    distance_km: float,
    vehicle: Optional[str],
    cfg: CostConfig,
) -> float:
    """
    Estimate the trip cost in PHP for a given distance and vehicle type.
    Returns 0.0 if distance is non-positive or config is invalid.
    """
    if distance_km <= 0:
        return 0.0

    v = (vehicle or "car").lower()

    if v == "car":
        if cfg.car_km_per_liter <= 0:
            return 0.0
        liters = distance_km / cfg.car_km_per_liter
        return liters * cfg.fuel_price_per_liter

    if v == "bike":
        return distance_km * cfg.bike_maintenance_per_km

    if v == "foot":
        return distance_km * cfg.foot_cost_per_km

    if v == "airplane":
        return distance_km * cfg.airplane_cost_per_km

    # Fallback for unknown vehicle types
    return 0.0
