"use strict";

(function exposeTemporal(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ThemisTemporal = api;
})(typeof globalThis === "undefined" ? this : globalThis, function temporalFactory() {
  function cursorForEvent(event) {
    return { time: Number(event?.time ?? 0), sequence: Number(event?.sequence ?? -1) };
  }

  function endOfTime(time) {
    return { time: Number(time ?? 0), sequence: Number.POSITIVE_INFINITY };
  }

  function occurred(event, cursor) {
    const eventTime = Number(event?.time ?? 0);
    const eventSequence = Number(event?.sequence ?? -1);
    return eventTime < cursor.time || (eventTime === cursor.time && eventSequence <= cursor.sequence);
  }

  function eventsThrough(run, cursor) {
    return (run?.events || []).filter(event => occurred(event, cursor));
  }

  function trajectoryStateAtCursor(run, cursor) {
    const state = {};
    for (const event of eventsThrough(run, cursor)) {
      if (event.event_type === "STATE_UPDATED" && event.payload?.trajectories) {
        Object.assign(state, structuredClone(event.payload.trajectories));
      } else if (event.event_type === "TRAJECTORY_REPROPAGATED" && event.payload?.agent_id && event.payload?.trajectory) {
        state[event.payload.agent_id] = structuredClone(event.payload.trajectory);
      }
    }
    return state;
  }

  function positionAt(trajectory, time) {
    const elapsed = Number(time) - Number(trajectory?.reference_time || 0);
    const position = trajectory?.position_km || [0, 0, 0];
    const velocity = trajectory?.velocity_km_per_step || [0, 0, 0];
    return [0, 1, 2].map(index => Number(position[index] || 0) + Number(velocity[index] || 0) * elapsed);
  }

  function sampleTimes(start, end, run) {
    const first = Number(start);
    const last = Number(end);
    if (last < first) return [];
    const interval = Math.max(1, Math.ceil((last - first) / 120));
    const times = new Set([first, last]);
    for (let time = first; time <= last; time += interval) times.add(time);
    for (const event of run?.events || []) {
      if (event.time >= first && event.time <= last) times.add(Number(event.time));
    }
    return [...times].sort((left, right) => left - right);
  }

  function historyForAgent(run, agentId, cursor) {
    return sampleTimes(0, cursor.time, run).map(time => {
      const sampleCursor = time === cursor.time ? cursor : endOfTime(time);
      const trajectory = trajectoryStateAtCursor(run, sampleCursor)[agentId];
      return trajectory ? { time, position: positionAt(trajectory, time) } : null;
    }).filter(Boolean);
  }

  function projectionForAgent(run, agentId, cursor, endTime) {
    const trajectory = trajectoryStateAtCursor(run, cursor)[agentId];
    if (!trajectory) return [];
    return sampleTimes(cursor.time, Math.max(cursor.time, Number(endTime)), run)
      .map(time => ({ time, position: positionAt(trajectory, time) }));
  }

  function riskStatesAtCursor(run, cursor) {
    const risks = new Map();
    for (const event of eventsThrough(run, cursor)) {
      const payload = event.payload || {};
      const riskId = event.references?.risk_event_id || payload.risk_event_id;
      if (!riskId) continue;
      if (["CONJUNCTION_DETECTED", "SECONDARY_CONJUNCTION_DETECTED"].includes(event.event_type)) {
        risks.set(riskId, { ...payload, risk_event_id: riskId, status: payload.status || "OPEN", detected_event_id: event.event_id });
      } else if (event.event_type === "RISK_REASSESSED") {
        const risk = risks.get(riskId) || { risk_event_id: riskId };
        risks.set(riskId, { ...risk, ...payload, status: payload.outcome || risk.status || "ASSESSED", reassessed_event_id: event.event_id });
      } else if (event.event_type === "CONJUNCTION_RESOLVED") {
        const risk = risks.get(riskId) || { risk_event_id: riskId };
        risks.set(riskId, { ...risk, status: "RESOLVED", resolved_event_id: event.event_id });
      }
    }
    return [...risks.values()];
  }

  function messagesAtCursor(run, cursor) {
    const messages = new Map();
    for (const event of eventsThrough(run, cursor)) {
      if (!event.event_type?.startsWith("MESSAGE_")) continue;
      const payload = event.payload || {};
      const messageId = event.references?.message_id || payload.message_id;
      if (!messageId) continue;
      const message = messages.get(messageId) || { message_id: messageId, events: [] };
      Object.assign(message, payload);
      message.events.push(event.event_id);
      message.latest_event_id = event.event_id;
      if (event.event_type === "MESSAGE_DROPPED") message.status = "dropped";
      else if (event.event_type === "MESSAGE_DELIVERED") message.status = "delivered";
      else if (event.event_type === "MESSAGE_DELAYED_BEYOND_USEFULNESS") message.status = "late";
      else if (event.event_type === "MESSAGE_SENT") message.status = "in_flight";
      messages.set(messageId, message);
    }
    return [...messages.values()];
  }

  function messageStatusCounts(messages) {
    const counts = { delivered: 0, dropped: 0, late: 0, in_flight: 0 };
    for (const message of messages || []) counts[message.status] = (counts[message.status] || 0) + 1;
    return counts;
  }

  return {
    cursorForEvent,
    endOfTime,
    occurred,
    eventsThrough,
    trajectoryStateAtCursor,
    positionAt,
    historyForAgent,
    projectionForAgent,
    riskStatesAtCursor,
    messagesAtCursor,
    messageStatusCounts,
  };
});
