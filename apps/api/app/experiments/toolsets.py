"""An experiment may remove tools, but may never grant publication privileges."""

from app.agent.tools.react_tools import ReactToolValidationError


class RestrictedToolset:
    def __init__(self, source, allowed):
        self.source = source
        self.allowed = frozenset(allowed)

    def public_catalog(self):
        return [item for item in self.source.public_catalog() if item["name"] in self.allowed]

    async def execute(self, decision, **kwargs):
        if decision.tool_name not in self.allowed:
            raise ReactToolValidationError("Tool is excluded from this experimental condition")
        # The real registry re-checks publication/withdrawal/code identity here.
        return await self.source.execute(decision, **kwargs)


def summarize_tool_pairs(rows, added_tools):
    counts = {
        "newly_solved": 0,
        "regressed": 0,
        "newly_solved_with_successful_added_tool": 0,
        "assessable_pairs": 0,
        "error_pairs": 0,
    }
    for row in rows:
        base = row["conditions"].get("base_tools")
        extended = row["conditions"].get("extended_tools")
        if row.get("error_type") or any(
            item is None or item.get("error_type") for item in (base, extended)
        ):
            counts["error_pairs"] += 1
            continue
        counts["assessable_pairs"] += 1
        newly_solved = not base.get("accepted_round") and bool(extended.get("accepted_round"))
        counts["newly_solved"] += newly_solved
        counts["regressed"] += bool(base.get("accepted_round")) and not extended.get(
            "accepted_round"
        )
        counts["newly_solved_with_successful_added_tool"] += newly_solved and any(
            trace["success"]
            and trace["tool_name"] in added_tools
            and bool(trace.get("tool_publication"))
            for round_result in extended.get("rounds", [])
            for trace in round_result["snapshot"]["tool_traces"]
        )
    counts["note"] = "Execution differences, not proof of causal or expressive capability gain."
    return counts


async def compare_capabilities(tasks, root, *, added_tools, **kwargs):
    from app.experiments.decisions import compare_decisions

    return await compare_decisions(
        tasks,
        root,
        intervention="tools",
        added_tools=added_tools,
        **kwargs,
    )
