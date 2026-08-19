"""Run-scoped protocol actors for ``spacecraft-campaign-v1``.

The runner owns delivery, truth, validation, and execution.  These actors only
consume an actor-scoped view and return messages, proposals, and auditable
protocol transitions.
"""

from copy import deepcopy
from dataclasses import fields

from src.maneuvers.model import ManeuverProposal
from src.network.message import Message, MessageType
from src.protocols.base import CampaignProtocolStep, ProtocolContext, ProtocolDecision
from src.risk.events import RiskEvent


COORDINATOR_ID = "CENTRAL_COORDINATOR"


def _transition(event_type, payload, *, references=None, entity_ids=None):
    return {
        "event_type": event_type,
        "payload": payload,
        "references": references or {},
        "entity_ids": entity_ids or [],
    }


def _risk_from_payload(payload):
    value = payload.get("risk_event")
    if isinstance(value, RiskEvent):
        return deepcopy(value)
    if not isinstance(value, dict):
        raise ValueError("protocol message is missing risk_event")
    allowed = {item.name for item in fields(RiskEvent)}
    return RiskEvent(**{key: deepcopy(item) for key, item in value.items() if key in allowed})


def _proposal_from_dict(value):
    allowed = {item.name for item in fields(ManeuverProposal)}
    data = {key: deepcopy(item) for key, item in value.items() if key in allowed}
    data["delta_v_vector_km_per_step"] = tuple(data["delta_v_vector_km_per_step"])
    if data.get("actual_delta_v_vector_km_per_step") is not None:
        data["actual_delta_v_vector_km_per_step"] = tuple(data["actual_delta_v_vector_km_per_step"])
    return ManeuverProposal(**data)


def check_campaign_step(step, actor_id):
    if not isinstance(step, CampaignProtocolStep):
        raise TypeError(f"Campaign protocol actor '{actor_id}' must return CampaignProtocolStep.")
    for message in step.outbound_messages:
        if not isinstance(message, Message):
            raise TypeError("Campaign outbound_messages must contain Message objects.")
        if message.sender_id != actor_id:
            raise ValueError(f"Actor '{actor_id}' cannot send as '{message.sender_id}'.")
    for proposal in step.maneuver_proposals:
        if not isinstance(proposal, ManeuverProposal):
            raise TypeError("Campaign maneuver_proposals must contain ManeuverProposal objects.")
        if proposal.agent_id != actor_id:
            raise ValueError(f"Actor '{actor_id}' cannot propose for '{proposal.agent_id}'.")
    return step


class CentralizedCampaignProtocol:
    name = "centralized"

    def __init__(self):
        self._directed_risks = set()

    def actors(self, agent_ids):
        return (COORDINATOR_ID, *agent_ids)

    def on_message(self, message, context):
        step = CampaignProtocolStep()
        if message.message_type == MessageType.RISK_ALERT and context.actor_id == COORDINATOR_ID:
            risk = _risk_from_payload(message.payload)
            if risk.risk_event_id in self._directed_risks:
                return step
            views = [context.agent_views.get(agent_id) for agent_id in sorted(risk.participants())]
            views = [view for view in views if view is not None]
            if not views:
                return step
            selected = min(views, key=lambda view: (view.mission_priority, -view.fuel_budget, view.agent_id))
            self._directed_risks.add(risk.risk_event_id)
            step.outbound_messages.append(
                Message(
                    sender_id=COORDINATOR_ID,
                    recipient_id=selected.agent_id,
                    message_type=MessageType.MANEUVER_DIRECTIVE,
                    payload=deepcopy(message.payload),
                )
            )
            step.trace_transitions.append(
                _transition(
                    "PROTOCOL_DECISION",
                    {
                        "protocol": self.name,
                        "risk_event_id": risk.risk_event_id,
                        "selected_agent_id": selected.agent_id,
                        "selection_criterion": "mission_priority_then_available_resource_then_id",
                    },
                    references={"risk_event_id": risk.risk_event_id},
                    entity_ids=[selected.agent_id],
                )
            )
        elif message.message_type == MessageType.MANEUVER_DIRECTIVE and context.actor_id != COORDINATOR_ID:
            risk = _risk_from_payload(message.payload)
            proposal = context.maneuver_generator.best_candidate(
                context.actor_id,
                risk,
                context.trajectories,
                context.current_time,
                self.name,
                context.reassessment_horizon_steps,
            )
            if proposal is not None:
                proposal.metadata.update({"directive_message_id": message.message_id})
                step.maneuver_proposals.append(proposal)
        return step

    def on_tick(self, context):
        return CampaignProtocolStep()


class GreedyCampaignProtocol:
    name = "greedy"

    def __init__(self):
        self._attempted = set()

    def actors(self, agent_ids):
        return agent_ids

    def on_message(self, message, context):
        step = CampaignProtocolStep()
        if message.message_type != MessageType.RISK_ALERT:
            return step
        risk = _risk_from_payload(message.payload)
        key = (context.actor_id, risk.risk_event_id)
        if key in self._attempted or context.actor_id not in risk.participants():
            return step
        self._attempted.add(key)
        if context.agent_view is None or context.agent_view.fuel_budget <= 0:
            return step
        proposal = context.maneuver_generator.best_candidate(
            context.actor_id,
            risk,
            context.trajectories,
            context.current_time,
            self.name,
            context.reassessment_horizon_steps,
        )
        if proposal is not None:
            step.maneuver_proposals.append(proposal)
            step.trace_transitions.append(
                _transition(
                    "PROTOCOL_DECISION",
                    {"protocol": self.name, "risk_event_id": risk.risk_event_id, "selected_agent_id": context.actor_id, "selection_criterion": "independent_first_local_alert"},
                    references={"risk_event_id": risk.risk_event_id},
                    entity_ids=[context.actor_id],
                )
            )
        return step

    def on_tick(self, context):
        return CampaignProtocolStep()


class AuctionCampaignProtocol:
    name = "auction"

    def __init__(self):
        self.auctions = {}
        self.reservations = {}

    def actors(self, agent_ids):
        return agent_ids

    def _score(self, proposal, view, risk, context):
        weights = context.auction_weights
        available = max(view.fuel_budget, 1e-12)
        risk_reduction = max(0.0, (proposal.expected_post_maneuver_separation_km or risk.distance_km) - risk.distance_km)
        slack = max(0, risk.decision_deadline - context.current_time - 1)
        factors = {
            "maneuver_cost": proposal.estimated_fuel_cost,
            "mission_priority": float(view.mission_priority),
            "fuel_scarcity": proposal.estimated_fuel_cost / available,
            "expected_risk_reduction_km": risk_reduction,
            "deadline_slack_steps": float(slack),
        }
        score = (
            weights["maneuver_cost"] * factors["maneuver_cost"]
            + weights["mission_priority"] * factors["mission_priority"]
            + weights["fuel_scarcity"] * factors["fuel_scarcity"]
            - weights["risk_reduction"] * factors["expected_risk_reduction_km"]
            - weights["deadline_slack"] * factors["deadline_slack_steps"]
        )
        return float(score), factors

    def on_message(self, message, context):
        step = CampaignProtocolStep()
        if message.message_type == MessageType.RISK_ALERT:
            risk = _risk_from_payload(message.payload)
            auctioneer = min(risk.participants())
            if context.actor_id != auctioneer:
                return step
            auction_id = f"auction:{risk.risk_event_id}"
            if auction_id in self.auctions:
                return step
            eligible = sorted(risk.participants())
            collection_deadline = max(context.current_time, risk.decision_deadline - context.network_latency_steps - 1)
            self.auctions[auction_id] = {
                "auction_id": auction_id,
                "risk_event_id": risk.risk_event_id,
                "auctioneer_id": auctioneer,
                "eligible": eligible,
                "collection_deadline": collection_deadline,
                "decision_deadline": risk.decision_deadline,
                "bids": {},
                "award_sent": False,
                "proposal_emitted": False,
                "terminated": False,
            }
            common = deepcopy(message.payload)
            common.update({"auction_id": auction_id, "auctioneer_id": auctioneer, "eligible_participants": eligible, "collection_deadline": collection_deadline})
            for recipient_id in eligible:
                step.outbound_messages.append(Message(auctioneer, recipient_id, MessageType.AUCTION_ANNOUNCEMENT, deepcopy(common)))
            step.trace_transitions.extend([
                _transition("AUCTION_CREATED", {"auction_id": auction_id, "risk_event_id": risk.risk_event_id, "auctioneer_id": auctioneer, "eligible_participants": eligible, "bids_expected": len(eligible), "collection_deadline": collection_deadline, "decision_deadline": risk.decision_deadline}, references={"auction_id": auction_id, "risk_event_id": risk.risk_event_id}, entity_ids=eligible),
                _transition("AUCTION_ANNOUNCED", {"auction_id": auction_id, "recipients": eligible}, references={"auction_id": auction_id, "risk_event_id": risk.risk_event_id}, entity_ids=eligible),
            ])
        elif message.message_type == MessageType.AUCTION_ANNOUNCEMENT:
            risk = _risk_from_payload(message.payload)
            auction_id = message.payload["auction_id"]
            if context.actor_id not in message.payload["eligible_participants"] or context.actor_id in self.reservations:
                return step
            view = context.agent_view
            if view is None:
                return step
            proposal = context.maneuver_generator.best_candidate(context.actor_id, risk, context.trajectories, context.current_time, self.name, context.reassessment_horizon_steps)
            if proposal is None or proposal.estimated_fuel_cost > view.fuel_budget:
                return step
            if context.current_time + context.network_latency_steps > message.payload["collection_deadline"]:
                return step
            score, factors = self._score(proposal, view, risk, context)
            bid_id = f"bid:{auction_id}:{context.actor_id}"
            self.reservations[context.actor_id] = {"auction_id": auction_id, "cost": proposal.estimated_fuel_cost, "deadline": risk.decision_deadline}
            bid_payload = {"auction_id": auction_id, "bid_id": bid_id, "risk_event_id": risk.risk_event_id, "risk_event": risk.to_dict(include_campaign=True), "bidder_id": context.actor_id, "score": score, "factors": factors, "proposal": proposal.to_dict(), "collection_deadline": message.payload["collection_deadline"], "decision_deadline": risk.decision_deadline}
            step.outbound_messages.append(Message(context.actor_id, message.payload["auctioneer_id"], MessageType.AUCTION_BID, bid_payload))
            step.trace_transitions.extend([
                _transition("AUCTION_BID_CREATED", {key: deepcopy(value) for key, value in bid_payload.items() if key != "proposal"}, references={"auction_id": auction_id, "bid_id": bid_id, "risk_event_id": risk.risk_event_id}, entity_ids=[context.actor_id]),
                _transition("PROTOCOL_RESOURCE_RESERVED", {"auction_id": auction_id, "agent_id": context.actor_id, "modeled_cost": proposal.estimated_fuel_cost}, references={"auction_id": auction_id, "bid_id": bid_id, "risk_event_id": risk.risk_event_id}, entity_ids=[context.actor_id]),
            ])
        elif message.message_type == MessageType.AUCTION_BID:
            auction = self.auctions.get(message.payload.get("auction_id"))
            if auction is None or context.actor_id != auction["auctioneer_id"] or context.current_time > auction["collection_deadline"]:
                return step
            bidder = message.payload.get("bidder_id")
            if bidder not in auction["eligible"] or not isinstance(message.payload.get("score"), (int, float)):
                return step
            auction["bids"][bidder] = deepcopy(message.payload)
            step.trace_transitions.append(_transition("AUCTION_BID_RECEIVED", {"auction_id": auction["auction_id"], "bid_id": message.payload["bid_id"], "bidder_id": bidder, "score": message.payload["score"], "received_time": context.current_time}, references={"auction_id": auction["auction_id"], "bid_id": message.payload["bid_id"], "risk_event_id": auction["risk_event_id"], "message_id": message.message_id}, entity_ids=[bidder]))
        elif message.message_type == MessageType.AUCTION_AWARD:
            auction = self.auctions.get(message.payload.get("auction_id"))
            if auction is None or context.actor_id != message.payload.get("winner_id"):
                return step
            risk = _risk_from_payload(message.payload)
            step.trace_transitions.append(_transition("AUCTION_AWARD_RECEIVED", {"auction_id": auction["auction_id"], "award_id": message.payload["award_id"], "winner_id": context.actor_id, "received_time": context.current_time}, references={"auction_id": auction["auction_id"], "award_id": message.payload["award_id"], "bid_id": message.payload["bid_id"], "risk_event_id": risk.risk_event_id, "message_id": message.message_id}, entity_ids=[context.actor_id]))
            if context.current_time + 1 <= risk.decision_deadline:
                proposal = context.maneuver_generator.best_candidate(context.actor_id, risk, context.trajectories, context.current_time, self.name, context.reassessment_horizon_steps)
                if proposal is not None:
                    proposal.metadata.update({"auction_id": auction["auction_id"], "bid_id": message.payload["bid_id"], "award_id": message.payload["award_id"]})
                    step.maneuver_proposals.append(proposal)
                    auction["proposal_emitted"] = True
                    step.outbound_messages.append(Message(context.actor_id, auction["auctioneer_id"], MessageType.AUCTION_ACKNOWLEDGEMENT, {"auction_id": auction["auction_id"], "award_id": message.payload["award_id"], "bid_id": message.payload["bid_id"], "risk_event_id": risk.risk_event_id, "deadline": risk.decision_deadline}))
            reservation = self.reservations.pop(context.actor_id, None)
            if reservation:
                step.trace_transitions.append(_transition("PROTOCOL_RESOURCE_RELEASED", {"auction_id": auction["auction_id"], "agent_id": context.actor_id, "reason": "award_received"}, references={"auction_id": auction["auction_id"], "risk_event_id": risk.risk_event_id}, entity_ids=[context.actor_id]))
        elif message.message_type == MessageType.AUCTION_ACKNOWLEDGEMENT:
            auction = self.auctions.get(message.payload.get("auction_id"))
            if auction is not None and context.actor_id == auction["auctioneer_id"]:
                step.trace_transitions.append(_transition("AUCTION_ACKNOWLEDGED", {"auction_id": auction["auction_id"], "award_id": message.payload["award_id"], "winner_id": message.sender_id}, references={"auction_id": auction["auction_id"], "award_id": message.payload["award_id"], "bid_id": message.payload["bid_id"], "risk_event_id": auction["risk_event_id"], "message_id": message.message_id}, entity_ids=[message.sender_id]))
        return step

    def on_tick(self, context):
        step = CampaignProtocolStep()
        for auction_id in sorted(self.auctions):
            auction = self.auctions[auction_id]
            if context.actor_id == auction["auctioneer_id"] and not auction["award_sent"] and context.current_time >= auction["collection_deadline"]:
                auction["award_sent"] = True
                if not auction["bids"]:
                    auction["terminated"] = True
                    step.trace_transitions.append(_transition("AUCTION_NO_VALID_BID", {"auction_id": auction_id, "risk_event_id": auction["risk_event_id"], "collection_deadline": auction["collection_deadline"]}, references={"auction_id": auction_id, "risk_event_id": auction["risk_event_id"]}, entity_ids=auction["eligible"]))
                else:
                    winner = min(auction["bids"].values(), key=lambda bid: (bid["score"], bid["bidder_id"], bid["bid_id"]))
                    award_id = f"award:{auction_id}"
                    award_payload = {"auction_id": auction_id, "award_id": award_id, "bid_id": winner["bid_id"], "risk_event_id": auction["risk_event_id"], "winner_id": winner["bidder_id"], "score": winner["score"], "decision_deadline": auction["decision_deadline"], "deadline": auction["decision_deadline"], "risk_event": deepcopy(winner["risk_event"])}
                    step.outbound_messages.append(Message(context.actor_id, winner["bidder_id"], MessageType.AUCTION_AWARD, award_payload))
                    step.trace_transitions.extend([
                        _transition("AUCTION_WINNER_SELECTED", {"auction_id": auction_id, "winner_id": winner["bidder_id"], "winning_bid_id": winner["bid_id"], "winning_score": winner["score"], "valid_bid_count": len(auction["bids"]), "tie_break": "score_then_bidder_id_then_bid_id"}, references={"auction_id": auction_id, "bid_id": winner["bid_id"], "risk_event_id": auction["risk_event_id"], "award_id": award_id}, entity_ids=[winner["bidder_id"]]),
                        _transition("AUCTION_AWARD_SENT", {"auction_id": auction_id, "award_id": award_id, "winner_id": winner["bidder_id"], "decision_deadline": auction["decision_deadline"]}, references={"auction_id": auction_id, "bid_id": winner["bid_id"], "risk_event_id": auction["risk_event_id"], "award_id": award_id}, entity_ids=[winner["bidder_id"]]),
                    ])
            if context.current_time >= auction["decision_deadline"] and not auction["proposal_emitted"] and not auction["terminated"] and context.actor_id == auction["auctioneer_id"]:
                auction["terminated"] = True
                step.trace_transitions.append(_transition("AUCTION_TIMED_OUT", {"auction_id": auction_id, "risk_event_id": auction["risk_event_id"], "reason": "award_not_received_before_execution_deadline"}, references={"auction_id": auction_id, "risk_event_id": auction["risk_event_id"]}, entity_ids=auction["eligible"]))
        reservation = self.reservations.get(context.actor_id)
        if reservation and context.current_time >= reservation["deadline"]:
            self.reservations.pop(context.actor_id, None)
            step.trace_transitions.append(_transition("PROTOCOL_RESOURCE_RELEASED", {"auction_id": reservation["auction_id"], "agent_id": context.actor_id, "reason": "auction_deadline"}, references={"auction_id": reservation["auction_id"]}, entity_ids=[context.actor_id]))
        return step


class LegacyCampaignAdapter:
    """Run a one-shot installed protocol once per locally delivered risk."""

    def __init__(self, protocol):
        self.protocol = protocol
        self.name = protocol.name
        self._attempted = set()

    def actors(self, agent_ids):
        return agent_ids

    def on_message(self, message, context):
        if message.message_type != MessageType.RISK_ALERT:
            return CampaignProtocolStep()
        risk = _risk_from_payload(message.payload)
        key = (context.actor_id, risk.risk_event_id)
        if key in self._attempted:
            return CampaignProtocolStep()
        self._attempted.add(key)
        legacy = ProtocolContext(context.current_time, self.name, context.agent_views, list(context.risk_events), deepcopy(context.trajectories), context.maneuver_generator, context.reassessment_horizon_steps, context.global_access)
        decision = self.protocol.propose_maneuvers(legacy)
        if not isinstance(decision, ProtocolDecision):
            raise TypeError(f"Adapted protocol '{self.name}' must return ProtocolDecision.")
        return CampaignProtocolStep(maneuver_proposals=list(decision.maneuver_proposals))

    def on_tick(self, context):
        return CampaignProtocolStep()


def make_campaign_protocol(protocol):
    if protocol.name == "centralized":
        return CentralizedCampaignProtocol()
    if protocol.name == "greedy":
        return GreedyCampaignProtocol()
    if protocol.name == "auction":
        return AuctionCampaignProtocol()
    if all(callable(getattr(protocol, method, None)) for method in ("actors", "on_message", "on_tick")):
        return check_campaign_protocol(protocol)
    return LegacyCampaignAdapter(protocol)


def check_campaign_protocol(protocol):
    name = getattr(protocol, "name", None)
    if not isinstance(name, str) or not name:
        raise TypeError("A campaign protocol must expose a non-empty string 'name'.")
    for method in ("actors", "on_message", "on_tick"):
        if not callable(getattr(protocol, method, None)):
            raise TypeError(f"Campaign protocol '{name}' must implement {method}().")
    return protocol


__all__ = [
    "AuctionCampaignProtocol",
    "CentralizedCampaignProtocol",
    "GreedyCampaignProtocol",
    "LegacyCampaignAdapter",
    "check_campaign_step",
    "check_campaign_protocol",
    "make_campaign_protocol",
]
