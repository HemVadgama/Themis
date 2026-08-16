"use strict";

const assert = require("node:assert/strict");
const temporal = require("../src/viewer/static/temporal.js");

const run = {
  events: [
    {time: 0, sequence: 0, event_id: "event-0", event_type: "STATE_UPDATED", payload: {trajectories: {A: {reference_time: 0, position_km: [0, 0, 0], velocity_km_per_step: [1, 0, 0]}, B: {reference_time: 0, position_km: [30, 0, 0], velocity_km_per_step: [0, 0, 0]}}}},
    {time: 0, sequence: 1, event_id: "event-1", event_type: "MESSAGE_SENT", references: {message_id: "msg-1"}, payload: {message_id: "msg-1", sender_id: "MONITOR", recipient_id: "A", sent_time: 0, deliver_at: 1}},
    {time: 0, sequence: 2, event_id: "event-2", event_type: "CONJUNCTION_DETECTED", references: {risk_event_id: "risk-1"}, payload: {risk_event_id: "risk-1", satellite_a: "A", satellite_b: "B", threshold_km: 50}},
    {time: 1, sequence: 3, event_id: "event-3", event_type: "MESSAGE_DELIVERED", references: {message_id: "msg-1"}, payload: {message_id: "msg-1", sender_id: "MONITOR", recipient_id: "A", delivered_time: 1}},
    {time: 2, sequence: 4, event_id: "event-4", event_type: "TRAJECTORY_REPROPAGATED", payload: {agent_id: "A", trajectory: {reference_time: 2, position_km: [2, 0, 0], velocity_km_per_step: [100, 0, 0]}}},
    {time: 2, sequence: 5, event_id: "event-5", event_type: "CONJUNCTION_RESOLVED", references: {risk_event_id: "risk-1"}, payload: {risk_event_id: "risk-1"}},
  ],
};

const afterSend = {time: 0, sequence: 1};
assert.equal(temporal.messagesAtCursor(run, afterSend)[0].status, "in_flight");
assert.equal(temporal.riskStatesAtCursor(run, afterSend).length, 0);
assert.deepEqual(temporal.positionAt(temporal.trajectoryStateAtCursor(run, afterSend).A, 0), [0, 0, 0]);
assert.deepEqual(temporal.projectionForAgent(run, "A", afterSend, 4).at(-1).position, [4, 0, 0], "future repropagation must not leak into an earlier projection");

const afterDetection = {time: 0, sequence: 2};
assert.equal(temporal.riskStatesAtCursor(run, afterDetection)[0].status, "OPEN");
assert.equal(temporal.messagesAtCursor(run, afterDetection)[0].status, "in_flight");

assert.equal(temporal.messagesAtCursor(run, temporal.endOfTime(1))[0].status, "delivered");
assert.deepEqual(temporal.positionAt(temporal.trajectoryStateAtCursor(run, {time: 2, sequence: 3}).A, 2), [2, 0, 0], "same-time future event must not leak across the event cursor");
assert.deepEqual(temporal.positionAt(temporal.trajectoryStateAtCursor(run, {time: 2, sequence: 4}).A, 3), [102, 0, 0]);
assert.equal(temporal.riskStatesAtCursor(run, {time: 2, sequence: 5})[0].status, "RESOLVED");

console.log("viewer temporal-state tests passed");
