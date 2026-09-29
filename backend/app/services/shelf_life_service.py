"""
Remaining shelf life in hours, per batch, from postharvest physics.
Integrates thermal damage (Q10), chilling injury, and transpiration weight loss.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import Base
from app.services.psychrometrics import vpd_kpa

# ---------------------------------------------------------------- crop table
# Mirrors sim/sim_node.py CROPS and master plan Appendix A.
#   life_d    shelf life (days) at the ideal setpoint
#   q10       rate multiplier per +10 C
#   chill     chilling-injury threshold (C) -- SEPARATE from temp_min
#   transp_k  transpiration coefficient (drives weight loss)
#   max_loss  unmarketable beyond this weight loss (%)
#   price     Rs/kg, for value-at-risk
CROPS: dict[str, dict] = {
    "Tomato":        dict(life_d=21,  q10=2.3, chill=10.0, transp_k=2.0,  max_loss=6.0,  price=28),
    "Cabbage":       dict(life_d=90,  q10=2.5, chill=-0.9, transp_k=1.2,  max_loss=8.0,  price=18),
    "Leafy greens":  dict(life_d=12,  q10=2.8, chill=-0.4, transp_k=12.0, max_loss=3.0,  price=35),
    "French bean":   dict(life_d=10,  q10=2.6, chill=5.0,  transp_k=6.0,  max_loss=5.0,  price=45),
    "Green chilli":  dict(life_d=18,  q10=2.4, chill=7.0,  transp_k=3.5,  max_loss=5.0,  price=55),
    "Khasi mandarin":dict(life_d=60,  q10=2.0, chill=3.0,  transp_k=1.5,  max_loss=7.0,  price=40),
    "Pineapple":     dict(life_d=25,  q10=2.2, chill=7.0,  transp_k=2.2,  max_loss=6.0,  price=30),
    "Ginger":        dict(life_d=120, q10=2.0, chill=7.0,  transp_k=0.8,  max_loss=10.0, price=90),
}
DEFAULT_CROP = CROPS["Tomato"]


def crop_params(crop_type: Optional[str]) -> dict:
    """Case-insensitive crop lookup; unknown crops fall back to Tomato."""
    if not crop_type:
        return DEFAULT_CROP
    for name, params in CROPS.items():
        if name.lower() == crop_type.strip().lower():
            return params
    return DEFAULT_CROP


# ------------------------------------------------------------------- model
class ShelfLifeState(Base):
    """One accumulating damage row per zone. Created by Base.metadata.create_all."""

    __tablename__ = "shelf_life_state"

    state_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    zone_id = Column(String(36), ForeignKey("zones.zone_id", ondelete="CASCADE"),
                     nullable=False, index=True, unique=True)
    crop_type = Column(String(50))
    mass_kg = Column(Float, default=500.0)

    damage = Column(Float, default=0.0)         # thermal, 0->1
    chill_damage = Column(Float, default=0.0)   # chilling injury, 0->1
    weight_loss_pct = Column(Float, default=0.0)
    wet_hours = Column(Float, default=0.0)

    remaining_h = Column(Float)
    total_damage = Column(Float, default=0.0)
    value_at_risk = Column(Float, default=0.0)

    last_sampled_at = Column(DateTime)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


# ------------------------------------------------------------ pure physics
def rate(t_c: float, q10: float, chill_c: float) -> float:
    """Q10 deterioration rate, clamped at the chilling threshold."""
    return q10 ** ((max(t_c, chill_c) - 10.0) / 10.0)


def project_remaining_h(total_damage: float, t_c: float, params: dict) -> float:
    """Hours of life left IF held at t_c. A projection, not a countdown."""
    r = rate(t_c, params["q10"], params["chill"])
    return max(0.0, (1.0 - min(1.0, total_damage)) * params["life_d"] * 24.0 / r)


def integrate(
    *,
    prev_damage: float,
    prev_chill: float,
    prev_weight_loss: float,
    prev_wet_hours: float,
    t_c: float,
    rh_pct: float,
    dt_h: float,
    params: dict,
    condensation_margin_c: Optional[float] = None,
) -> dict:
    """
    Advance the damage integrals by dt_h. Pure -- no DB, no clock, no I/O.
    """
    dt_h = max(0.0, min(dt_h, 6.0))     # ignore absurd gaps (clock skew, restart)

    damage = prev_damage + rate(t_c, params["q10"], params["chill"]) * dt_h / (params["life_d"] * 24.0)
    chill = prev_chill
    if t_c < params["chill"]:
        chill += ((params["chill"] - t_c) / 5.0) * dt_h / 24.0
    weight_loss = prev_weight_loss + params["transp_k"] * vpd_kpa(t_c, rh_pct) * dt_h / 24.0
    wet_hours = prev_wet_hours + (dt_h if (condensation_margin_c is not None
                                           and condensation_margin_c < 0) else 0.0)

    # Whichever limit is reached first ends shelf life.
    total = max(damage + chill, weight_loss / params["max_loss"])
    return dict(damage=damage, chill_damage=chill, weight_loss_pct=weight_loss,
                wet_hours=wet_hours, total_damage=min(1.0, total))


# ------------------------------------------------------------------ service
class ShelfLifeService:
    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        zone_id: str,
        crop_type: Optional[str],
        temperature: Optional[float],
        humidity: Optional[float],
        sampled_at: datetime,
        condensation_margin_c: Optional[float] = None,
        mass_kg: Optional[float] = None,
    ) -> Optional[ShelfLifeState]:
        """
        Accumulate damage for one packet and return the updated state.

        Returns None when temperature or humidity is missing.
        """
        if temperature is None or humidity is None:
            return None

        params = crop_params(crop_type)
        state = (await db.execute(
            select(ShelfLifeState).where(ShelfLifeState.zone_id == zone_id)
        )).scalars().first()

        if state is None:
            state = ShelfLifeState(zone_id=zone_id, crop_type=crop_type,
                                   mass_kg=mass_kg or 500.0, last_sampled_at=sampled_at)
            db.add(state)
            await db.flush()

        # A crop change is a new batch: reset the integrals rather than carry
        # one crop's accumulated damage onto another.
        if crop_type and state.crop_type and crop_type.lower() != state.crop_type.lower():
            state.damage = state.chill_damage = state.weight_loss_pct = state.wet_hours = 0.0
            state.crop_type = crop_type
        if mass_kg:
            state.mass_kg = mass_kg

        dt_h = 0.0
        if state.last_sampled_at:
            dt_h = (sampled_at - state.last_sampled_at).total_seconds() / 3600.0

        result = integrate(
            prev_damage=state.damage or 0.0,
            prev_chill=state.chill_damage or 0.0,
            prev_weight_loss=state.weight_loss_pct or 0.0,
            prev_wet_hours=state.wet_hours or 0.0,
            t_c=temperature, rh_pct=humidity, dt_h=dt_h, params=params,
            condensation_margin_c=condensation_margin_c,
        )

        state.damage = result["damage"]
        state.chill_damage = result["chill_damage"]
        state.weight_loss_pct = result["weight_loss_pct"]
        state.wet_hours = result["wet_hours"]
        state.total_damage = result["total_damage"]
        state.remaining_h = project_remaining_h(result["total_damage"], temperature, params)
        state.value_at_risk = (state.mass_kg or 0.0) * params["price"] * result["total_damage"]
        state.last_sampled_at = sampled_at
        state.crop_type = state.crop_type or crop_type
        return state


shelf_life_service = ShelfLifeService()

