# Agent Context Management Summary
**Generated:** 2025-11-01T22:45:00Z

| Agent | Context Budget | Log File Convention | Notable Protocol Notes | Source |
|-------|----------------|---------------------|------------------------|--------|
| documentation-engineer | Keep summaries under 20KB; use `.agent-workspace/context/active/` | `.agent-workspace/logs/{date}-documentation-engineer.log` | Must apply ADRs for major decisions; enforce 5 core principles | E:\agents\...\08-support/documentation/documentation-engineer.md |
| data-engineer | Summaries <20KB; invoke `@context-compressor` if exceeded | `.agent-workspace/logs/{date}-data-engineer.log` | Pipeline work must follow plan→execute flow; reuse-first enforcement | E:\agents\...\06-data-ai/data/data-engineer.md |
| manufacturing-ai-consultant | Summaries <20KB | `.agent-workspace/logs/{date}-manufacturing-ai-consultant.log` | Coordinates manufacturing decisions; must update manifest & handoffs | E:\agents\...\07-specialized/manufacturing/manufacturing-ai-consultant.md |
| sre-engineer | Summaries <20KB | `.agent-workspace/logs/{date}-sre-engineer.log` | Reliability gating; verification requires real data; uses MCP tools | E:\agents\...\04-infrastructure/devops/sre-engineer.md |
| golang-pro | Summaries <20KB | `.agent-workspace/logs/{date}-golang-pro.log` | Enforces Go-specific quality gates; ties into MCP workflow | E:\agents\...\02-languages/systems/golang-pro.md |
| rust-engineer | Summaries <20KB | `.agent-workspace/logs/{date}-rust-engineer.log` | Zero-cost abstractions emphasis; follow MCP pattern before coding | E:\agents\...\02-languages/systems/rust-engineer.md |
| predictive-maintenance-specialist | Summaries <20KB | `.agent-workspace/logs/{date}-predictive-maintenance-specialist.log` | Requires manufacturing context and simulator validation | E:\agents\...\07-specialized/manufacturing/predictive-maintenance-specialist.md |

> All agents reference `AGENT_WORKSPACE_PROTOCOL.md` for the 8-step workflow and must log MCP usage (sequential thinking, pattern hunter, quality guardian, memory updates) per task.
