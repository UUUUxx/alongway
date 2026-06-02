"""
Haversine-based local POI pre-filter for v2 route optimization.

Instead of calling Amap route API for every POI candidate, this module:
1. Computes approximate detour using Haversine distance
2. Ranks candidates by detour cost
3. Keeps only Top-K candidates for real Amap route verification

This dramatically reduces Amap API calls from ~N*candidates to ~N*top_k.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from agent.models import EnrichedCandidate, Location


@dataclass
class FilteredCandidate:
    """A candidate with Haversine-based detour approximation."""
    candidate: EnrichedCandidate
    detour_approx_meters: float
    direct_distance_meters: float


class HaversinePreFilter:
    """
    Pre-filters POI candidates using Haversine distance approximation.

    Only the Top-K candidates (by estimated detour) are returned for
    expensive Amap route verification.
    """

    def __init__(self, top_k: int = 3) -> None:
        self.top_k = top_k

    def filter(
        self,
        start: Location,
        end: Location,
        candidates_by_task: dict[str, list[EnrichedCandidate]],
    ) -> dict[str, list[FilteredCandidate]]:
        """
        Pre-filter candidates for each task.

        For each task, ranks candidates by Haversine-estimated detour
        and keeps only the Top-K.
        """
        base_dist = self._haversine_meters(
            start.longitude or 0, start.latitude or 0,
            end.longitude or 0, end.latitude or 0,
        )

        filtered: dict[str, list[FilteredCandidate]] = {}
        for task_id, candidates in candidates_by_task.items():
            scored: list[FilteredCandidate] = []
            for c in candidates:
                poi = c.poi
                if poi.longitude is None or poi.latitude is None:
                    # Without coordinates, keep it (can't compute detour)
                    scored.append(FilteredCandidate(
                        candidate=c,
                        detour_approx_meters=0,
                        direct_distance_meters=base_dist,
                    ))
                    continue

                # Compute Haversine-estimated detour
                d1 = self._haversine_meters(
                    start.longitude or 0, start.latitude or 0,
                    poi.longitude, poi.latitude,
                )
                d2 = self._haversine_meters(
                    poi.longitude, poi.latitude,
                    end.longitude or 0, end.latitude or 0,
                )
                detour = max(0, d1 + d2 - base_dist)
                scored.append(FilteredCandidate(
                    candidate=c,
                    detour_approx_meters=detour,
                    direct_distance_meters=d1 + d2,
                ))

            # Sort by estimated detour (ascending)
            scored.sort(key=lambda x: (x.detour_approx_meters, x.direct_distance_meters))
            filtered[task_id] = scored[:self.top_k]

        return filtered

    @staticmethod
    def haversine_meters(
        lon1: float, lat1: float,
        lon2: float, lat2: float,
    ) -> float:
        """Public Haversine function for use by other modules."""
        return HaversinePreFilter._haversine_meters(lon1, lat1, lon2, lat2)

    @staticmethod
    def _haversine_meters(
        lon1: float, lat1: float,
        lon2: float, lat2: float,
    ) -> float:
        earth_radius = 6_371_000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        return earth_radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
