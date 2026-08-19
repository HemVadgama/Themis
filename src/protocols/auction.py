"""Auction protocol marker and legacy-interface compatibility surface.

The communication-dependent implementation is driven by the campaign lifecycle in
``src.protocols.campaign``.  The one-shot methods deliberately return no action so
the v1 benchmark is never silently reinterpreted as an auction.
"""

from src.protocols.base import ProtocolDecision


class AuctionProtocol:
    name = "auction"

    def decide(self, world, conjunctions):
        return ProtocolDecision(
            coordination_attempts=len(conjunctions),
            unresolved_conjunctions=len(conjunctions),
            rationale=[{"outcome": "campaign_lifecycle_required"}],
        )

    def propose_maneuvers(self, context):
        return ProtocolDecision(
            coordination_attempts=len(context.risk_events),
            unresolved_conjunctions=len(context.risk_events),
            rationale=[{"outcome": "campaign_lifecycle_required"}],
        )
