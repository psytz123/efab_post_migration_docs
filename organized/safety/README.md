# Safety Automation Toolkit

## Components
- `safety_zone_diff.py`: Compares Task API and Edge configuration safety zones. Supports JSON and YAML input.

## Usage
```bash
python safety_zone_diff.py --task-api path/to/task_api.json --edge path/to/edge_config.yaml --pretty --summary
```

### Sample Workflow
1. Export Task API safety zones via REST (`/tasks` schema endpoint).
2. Export Edge Agent configuration (`edge/agent/config.edge.yaml`).
3. Run the diff utility to highlight mismatches prior to OTA rollout.
4. Use the remediation hints to prepare fixes and attach the report to the deployment checklist.

### CI Integration
- `--fail-on-diff` returns exit code `2` when mismatches exist (useful for gating OTA rollouts).
- `--summary` prints a concise status line (`ok`/`action_required`) for manufacturing dashboards.

## Integration Tests
- Pytest fixtures validate JSON/YAML comparisons and remediation guidance (`tests/test_safety_zone_diff.py`).
- Wire into CI pipeline before OTA promotion (per ADR-004 follow-up).

## Next Steps
- Integrate with manufacturing test suite for automated E-stop validation.
- Surface remediation summary to the safety command center UI.
