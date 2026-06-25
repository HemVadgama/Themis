def greedy_maneuver_decision(agent):
    return agent.state.risk_state == "HIGH" and agent.state.fuel_budget > 0
