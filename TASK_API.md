# Task API — Contracts & Examples

## REST (OpenAPI excerpt)
```yaml
openapi: 3.1.0
info: { title: eFab Task API, version: 0.1.0 }
paths:
  /tasks:
    post:
      summary: Create a task intent bound to order/lot/context
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/TaskIntent' }
      responses:
        '202': { description: Accepted }
  /tasks/{id}:
    get:
      summary: Get task state
components:
  schemas:
    Verb: { type: string, enum: [walk_to, grasp, place, actuate, inspect, handoff] }
    SafetyZone:
      type: object
      properties:
        id: { type: string }
        max_speed_mps: { type: number }
        keepout: { type: array, items: { type: number } }
    TaskIntent:
      type: object
      required: [order_id, lot, cell, verbs]
      properties:
        order_id: { type: string }
        lot: { type: string }
        cell: { type: string }
        verbs:
          type: array
          items:
            type: object
            properties:
              verb: { $ref: '#/components/schemas/Verb' }
              args: { type: object, additionalProperties: true }
        safety_zone: { $ref: '#/components/schemas/SafetyZone' }
        deadline_utc: { type: string, format: date-time }
    Task:
      allOf:
        - { $ref: '#/components/schemas/TaskIntent' }
        - type: object
          properties:
            id: { type: string }
            state: { type: string, enum: [queued, running, paused, completed, failed] }
```

## gRPC (proto excerpt)
```proto
syntax = "proto3";
package efab.task;

message SafetyZone { string id = 1; double max_speed_mps = 2; repeated double keepout = 3; }

enum Verb { WALK_TO = 0; GRASP = 1; PLACE = 2; ACTUATE = 3; INSPECT = 4; HANDOFF = 5; }

message VerbCall { Verb verb = 1; map<string,string> args = 2; }

message TaskIntent {
  string order_id = 1;
  string lot = 2;
  string cell = 3;
  repeated VerbCall verbs = 4;
  optional SafetyZone safety_zone = 5;
  string deadline_utc = 6;
}

message Task { string id = 1; TaskIntent intent = 2; string state = 3; }

service TaskAPI {
  rpc CreateTaskIntent(TaskIntent) returns (Task);
  rpc GetTask(Task) returns (Task);
  rpc StreamTaskUpdates(Task) returns (stream Task);
}
```

## Event Topics
- `schedule.task.intent.created` | `schedule.task.intent.updated`
- `task.execution.update`
- `quality.inspection.result`
- `telemetry.robot.state`

## Example — Create TaskIntent
```http
POST /tasks HTTP/1.1
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "order_id": "SO-12345",
  "lot": "123A",
  "cell": "PackLine1",
  "verbs": [
    {"verb": "walk_to", "args": {"x":"1.2","y":"0.7"}},
    {"verb": "grasp",   "args": {"object":"pallet"}},
    {"verb": "place",   "args": {"x":"1.8","y":"0.7"}}
  ],
  "safety_zone": {"id":"packline1-zone","max_speed_mps":0.30,"keepout":[0,0,0,3,2,2]},
  "deadline_utc": "2025-11-01T23:59:59Z"
}
```
