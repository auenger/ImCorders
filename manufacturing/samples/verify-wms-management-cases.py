"""Recompute the declared WMS teaching cases; not a live WMS integration test.

Run next to wms-management-cases.json, or pass its path as the first argument.
"""
import json
import math
import sys
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(actual, expected, label):
    require(actual == expected, f"{label}: got {actual!r}, expected {expected!r}")


def ratio(numerator, denominator):
    # Missing facts remain unknown; a known zero denominator is not applicable.
    if numerator is None or denominator is None:
        return {"status": "unknown", "value": None}
    if denominator == 0:
        return {"status": "not-applicable", "value": None}
    return {"status": "known", "value": numerator / denominator}


def apply_events(events):
    seen = {}
    total = 0
    for event in events:
        key = event["id"]
        if key in seen:
            require(seen[key] == event, f"event content conflict: {key}")
            continue
        require(event["quantity"] >= 0, "negative shipment")
        seen[key] = dict(event)
        total += event["quantity"]
    return total


def verify(data):
    require(data["simulated"] is True, "simulation marker missing")
    c = data["counting"]
    aligned = dict(c["initial"])
    seen = {}
    for move in c["confirmedMoves"]:
        if move["id"] in seen:
            same(move, seen[move["id"]], "conflicting move")
            continue
        seen[move["id"]] = move
        require(move["quantity"] > 0, "invalid move quantity")
        aligned[move["source"]] -= move["quantity"]
        aligned[move["destination"]] += move["quantity"]
    same(aligned, c["counted"], "confirmed movement vs counted locations")
    same(aligned, c["expected"]["aligned"], "aligned ledger")
    same(sum(c["initial"].values()), sum(aligned.values()), "transfer conservation")
    same(sum(c["initial"][k] == c["counted"][k] for k in aligned), c["expected"]["initialExactLines"], "initial accurate rows")
    same(len(aligned), c["expected"]["totalLines"], "counted row denominator")
    review = c["reviewBranch"]
    adjusted = {k: aligned[k] + review["approvedAdjustment"][k] for k in aligned}
    same(adjusted, review["counted"], "approved adjustment vs reviewed fact")
    same(sum(adjusted.values()), c["expected"]["adjustedTotal"], "review total")

    p = data["picking"]
    same(p["delivered"], p["consumed"] + p["confirmedUnusedReturn"] + p["lineSideRemaining"], "delivered material whereabouts")
    before = p["approvedLimit"] - p["delivered"] - p["openWorkAllocation"]
    after = before + p["confirmedUnusedReturn"]
    same(before, p["expected"]["beforeReturn"], "allowance before return")
    same(after, p["expected"]["afterReturn"], "allowance after return")
    same(max(0, p["newRequest"] - after), p["expected"]["approvalNeeded"], "excess request")
    same(after + p["approvedAdditional"], p["expected"]["afterApproval"], "approved allowance")

    q = data["quality"]
    w, hold, exp = q["whereabouts"], q["containment"], q["expected"]
    same(sum(w.values()), q["receivedComponents"], "component whereabouts")
    same((w["wipInstalled"] + w["shippedInstalled"]) / q["partsPerProduct"], exp["associatedProducts"], "associated products")
    same(hold["warehouseConfirmed"], w["warehouseUnused"], "warehouse receipt")
    same(hold["lineSystemBlocked"], w["lineUnused"], "line system restriction")
    same(w["lineUnused"] - hold["linePhysicallyConfirmed"], exp["linePending"], "line physical pending")
    same(w["wipInstalled"] - hold["wipBlocked"], hold["wipConflict"], "wip pending")
    same(hold["wipConflict"], exp["wipPending"], "wip expected")
    same(w["shippedInstalled"] - hold["shippedFollowupConfirmed"], exp["shippedPending"], "shipped pending")
    same(all(exp[k] == 0 for k in ("linePending", "wipPending", "shippedPending")), exp["complete"], "closure status")

    i = data["integration"]
    applied = apply_events(i["deliveries"])
    same(applied, i["expected"]["appliedOnce"], "idempotent shipment")
    try:
        apply_events(i["deliveries"] + [i["conflictingRetry"]])
    except ValueError as exc:
        require("content conflict" in str(exc), "wrong rejection reason")
    else:
        raise ValueError("conflicting retry accepted")
    same(i["approvedCorrection"]["original"], i["deliveries"][0]["id"], "correction link")
    same(applied + i["approvedCorrection"]["delta"], i["expected"]["afterCorrection"], "approved correction")
    same(len({r["line"] for r in i["reconciliation"]}), len(i["reconciliation"]), "unique reconciliation lines")
    src = sum(r["source"] for r in i["reconciliation"])
    tgt = sum(r["target"] for r in i["reconciliation"])
    same(src, i["expected"]["sourceTotal"], "source total")
    same(tgt, i["expected"]["targetTotal"], "target total")
    same(sum(abs(r["source"] - r["target"]) for r in i["reconciliation"]), i["expected"]["unmatched"], "unmatched quantity")

    m = data["metrics"]
    shipped = set(m["shippedLineIds"])
    same(len(shipped), len(m["shippedLineIds"]), "shipment line IDs unique")
    require(all(r["lineId"] in shipped for r in m["errorReports"]), "error references an unshipped line")
    report_ids = {}
    for report in m["errorReports"]:
        if report["reportId"] in report_ids:
            same(report, report_ids[report["reportId"]], "conflicting error report")
        report_ids[report["reportId"]] = report
    errors = len({r["lineId"] for r in report_ids.values()})
    x = m["exceptions"]
    opened = x["opening"] + x["new"] + x["reopened"] - x["closed"] - x["voided"]
    require(0 <= x["openOverSla"] <= opened and 0 <= x["closedWithinSla"] <= x["closed"], "invalid exception subsets")
    require(0 <= m["exactFirstCountRows"] <= m["countedRows"], "invalid accurate row subset")
    require(0 <= m["slowMovingCandidateValue"] <= m["endingInventoryValue"], "invalid slow-moving subset")
    actual = {
        "stockAccuracy": ratio(m["exactFirstCountRows"], m["countedRows"])["value"],
        "errorLines": errors, "dispatchErrorRate": ratio(errors, len(shipped))["value"],
        "linesPerPersonHour": ratio(len(shipped), m["directPersonHoursForCompletedLines"])["value"],
        "openExceptions": opened,
        "closedOnTimeRate": ratio(x["closedWithinSla"], x["closed"])["value"],
        "openOverdueRate": ratio(x["openOverSla"], opened)["value"],
        "periodIssueTurnover": ratio(m["monthlyIssueCost"], m["averageInventoryCost"])["value"],
        "slowMovingCandidateShare": ratio(m["slowMovingCandidateValue"], m["endingInventoryValue"])["value"],
    }
    for key, value in actual.items():
        expected = m["expected"][key]
        require(value is not None and math.isclose(value, expected), f"metric mismatch: {key}")
    same(ratio(0, 0)["status"], "not-applicable", "zero denominator")
    same(ratio(None, 10)["status"], "unknown", "unknown numerator")
    return {"counting": "pass", "picking": "pass", "quality": "pass", "integration": "pass", "metrics": actual}


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("wms-management-cases.json")
    print(json.dumps(verify(json.loads(path.read_text())), ensure_ascii=False, indent=2))
