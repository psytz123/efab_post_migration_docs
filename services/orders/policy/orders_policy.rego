package orders.authz

default allow = false

roles := {
  "planner": {
    "actions": ["orders.create", "orders.read", "orders.update", "orders.lot.manage"],
    "description": "Create and manage production orders"
  },
  "scheduler": {
    "actions": ["orders.read", "orders.update_state", "orders.lot.manage"],
    "description": "Control release and scheduling"
  },
  "operator": {
    "actions": ["orders.read"],
    "description": "View-only access"
  },
  "admin": {
    "actions": ["orders.*"],
    "description": "Full administrative control"
  }
}

allow {
  input.jwt.claims["role"] == role
  role_actions := roles[role].actions
  required := input.action
  any(role_actions, func(a) {
    a == required || a == "orders.*"
  })
  input.site_id == input.jwt.claims["site_id"]
}

allow {
  input.jwt.claims["role"] == "admin"
}

# Deny if state transition invalid
deny[msg] {
  input.action == "orders.update_state"
  not valid_transition(input.resource.old_state, input.resource.new_state)
  msg := sprintf("invalid state transition %s -> %s", [input.resource.old_state, input.resource.new_state])
}

valid_transition(old, new) {
  allowed := {
    "draft": ["firm", "cancelled"],
    "firm": ["released", "cancelled"],
    "released": ["paused", "completed", "cancelled"],
    "paused": ["released", "cancelled"],
    "completed": [],
    "cancelled": []
  }
  new in allowed[old]
}
