# -*- coding: utf-8 -*-
"""Recompute eight declared teaching models, not live SAP behavior.

Run beside erp-sap-cases.json or pass its local path as the first argument.
Amounts in these cases are whole CNY; no tax, FX or rounding model is implied.
"""
import json
import sys
from datetime import date
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(actual, expected, label):
    require(actual == expected, f"{label}: got {actual!r}, expected {expected!r}")


def ledger(postings):
    seen, balances = {}, {}
    for posting in postings:
        identity = posting["id"]
        if identity in seen:
            same(posting, seen[identity], "conflicting accounting transaction")
            continue
        same(sum(posting["lines"].values()), 0, "balanced teaching journal")
        seen[identity] = posting
        for account, amount in posting["lines"].items():
            balances[account] = balances.get(account, 0) + amount
    return balances


def version_ready(version, plant, day, quantity):
    return bool(version and version["plant"] == plant and version["approved"] and version["consistent"]
                and date.fromisoformat(version["from"]) <= day <= date.fromisoformat(version["through"])
                and version["minLot"] <= quantity <= version["maxLot"])


def plan_mrp(m, supplies=None):
    require(m["restrictionsDisjoint"] is True, "sample subtraction requires disjoint restrictions")
    require(0 <= m["consumedForecast"] <= min(m["salesGood"], m["forecastGood"]), "invalid forecast consumption")
    require(m["minimumLotAndMultiple"] > 0, "invalid batch rule")
    gross = m["salesGood"] + m["forecastGood"] - m["consumedForecast"]
    demand = gross * m["componentPerGood"]
    eligible = m["physical"] - m["qualityRestricted"] - m["otherDemandReserved"]
    require(eligible >= 0, "negative candidate stock")
    supplies = m["openSupply"] if supplies is None else supplies
    require(len({s["id"] for s in supplies}) == len(supplies), "duplicate formal supply")
    require(all(isinstance(s["quantity"], int) and s["quantity"] >= 0 for s in supplies), "unknown or negative supply")
    timely = sum(s["quantity"] for s in supplies if s["usableDay"] <= m["neededDay"])
    shortage = max(0, demand - eligible - timely)
    lot = m["minimumLotAndMultiple"]
    proposal = ((shortage + lot - 1) // lot) * lot
    return {"grossGood": gross, "componentDemand": demand, "eligibleStock": eligible,
            "supplyByNeed": timely, "netShortage": shortage, "proposal": proposal,
            "surplusAfterNeed": eligible + timely + proposal - demand,
            "surplusD8": eligible + sum(s["quantity"] for s in supplies if s["usableDay"] <= 8) + proposal - demand}


def business_effects(events):
    seen, totals = {}, {"confirmation": 0, "issue": 0, "receipt": 0}
    for event in events:
        identity = event["businessId"]
        payload = {k: v for k, v in event.items() if k != "messageId"}
        if identity in seen:
            same(payload, seen[identity], "same business action has different content")
            continue
        require(event["kind"] in totals and event["quantity"] >= 0, "invalid action")
        seen[identity] = payload
        totals[event["kind"]] += event["quantity"]
    return totals, seen


def verify(data):
    require(data["simulated"] is True, "teaching marker missing")
    results = {}
    p = data["procurePay"]
    expected = p["expected"]
    same(p["invoiceStatus"], "posted-payment-blocked", "selected invoice scenario")
    same(p["received"] + p["approvedCancelledQuantity"], p["ordered"], "purchase quantity closure")
    order, received, invoice, credit = [p[k] * p["unitPrice"] for k in ("ordered", "received", "invoiced", "approvedCreditQuantity")]
    same(order, expected["orderValue"], "order value")
    same(received, expected["receiptValue"], "receipt value")
    same(invoice, expected["invoiceValue"], "invoice value")
    by_phase = {x["phase"]: x for x in p["postings"]}
    same(by_phase["receipt"]["lines"], {"inventory": received, "grir": -received}, "receipt postings")
    same(by_phase["invoice"]["lines"], {"grir": invoice, "payable": -invoice}, "invoice postings")
    same(by_phase["credit"]["lines"], {"grir": -credit, "payable": credit}, "credit postings")
    same(by_phase["credit"]["original"], by_phase["invoice"]["id"], "credit origin")
    before = ledger([by_phase["receipt"], by_phase["invoice"]])
    after = ledger([by_phase["receipt"], by_phase["invoice"], by_phase["credit"]])
    same(before["grir"], expected["grirBeforeCredit"], "GR/IR before correction")
    same(-before["payable"], expected["payableBeforeCredit"], "AP before correction")
    same(after["grir"], expected["grirAfterCredit"], "GR/IR after correction")
    same(-after["payable"], expected["payableAfterCredit"], "AP after correction")
    require(p["paymentEligibleAfterReview"] and after["grir"] == 0, "payment prerequisite missing")
    same(p["paidAndApplied"], -after["payable"], "approved payment application")
    same(by_phase["payment"]["lines"], {"payable": p["paidAndApplied"], "cash": -p["paidAndApplied"]}, "payment postings")
    final = ledger(p["postings"])
    same(final["payable"], expected["payableAfterPayment"], "AP after payment")
    same(ledger(p["postings"] + [by_phase["credit"]]), final, "duplicate credit is not applied twice")
    results["procurePay"] = {"grirBeforeCredit": before["grir"], "payableAfterCredit": -after["payable"], "finalPayable": final["payable"]}

    c = data["orderCash"]
    e = c["expected"]
    require(0 <= c["billedAndPosted"] <= c["shipped"] <= c["ordered"], "invalid delivery/billing subset")
    values = {"orderValue": c["ordered"] * c["unitPrice"], "unshippedValue": (c["ordered"] - c["shipped"]) * c["unitPrice"],
              "shippedUnbilledValue": (c["shipped"] - c["billedAndPosted"]) * c["unitPrice"], "billedValue": c["billedAndPosted"] * c["unitPrice"]}
    require(len({r["id"] for r in c["bankReceipts"]}) == len(c["bankReceipts"]), "duplicate bank receipt")
    require(all(0 <= r["applied"] <= r["amount"] for r in c["bankReceipts"]), "invalid receipt allocation")
    values["bankTotal"] = sum(r["amount"] for r in c["bankReceipts"])
    values["applied"] = sum(r["applied"] for r in c["bankReceipts"])
    values["unallocated"] = values["bankTotal"] - values["applied"]
    values["openReceivable"] = values["billedValue"] - values["applied"]
    values["overdueDays"] = max(0, (date.fromisoformat(c["asOf"]) - date.fromisoformat(c["dueDate"])).days)
    values["netBilledAfterCredit"] = values["billedValue"] - c["independentPriceCredit"]
    values["openAfterCredit"] = values["netBilledAfterCredit"] - values["applied"]
    same(values, e, "sales scope and open items")
    same(values["unshippedValue"] + values["shippedUnbilledValue"] + values["billedValue"], values["orderValue"], "order value bridge")
    results["orderCash"] = values

    k = data["costSettlement"]
    planned = sum(i["plannedQuantity"] * i["rate"] for i in k["costItems"])
    actual = sum(i["actualQuantity"] * i["rate"] for i in k["costItems"])
    same(planned, k["expected"]["standardTotal"], "cost baseline")
    same(actual, k["expected"]["actualFinalBeforeLate"], "final cost before late")
    for item in k["costItems"]:
        same((item["actualQuantity"] - item["plannedQuantity"]) * item["rate"], k["expected"][item["item"] + "Delta"], "cost item delta")
    snapshots = {s["id"]: s for s in k["snapshots"]}
    same(snapshots["K2"]["actual"], actual, "K2 actual")
    same(snapshots["K3"]["actual"], actual + k["approvedLateCost"], "K3 late cost")
    for s in k["snapshots"]:
        received = s["receivedGood"] * k["standardPerGood"]
        require(s["state"] in ("in-process", "finally-delivered"), "unknown order state")
        if s["state"] == "in-process":
            require(s["receivedGood"] < k["plannedGood"], "partial model needs unfinished units")
            wip, variance = s["actual"] - received, 0
        else:
            same(s["receivedGood"], k["plannedGood"], "final receipt quantity")
            wip, variance = 0, s["actual"] - received
        same(wip, s["expectedWip"], s["id"] + " WIP")
        same(variance, s["expectedVariance"], s["id"] + " variance")
    results["costSettlement"] = {s["id"]: {"wip": s["expectedWip"], "variance": s["expectedVariance"]} for s in k["snapshots"]}

    m = data["plantMaster"]
    day = date.fromisoformat(m["productionDate"])
    requirement = m["orderGood"] * m["componentPerGood"]
    for plant in m["plants"]:
        eligible = plant["physical"] - plant["restricted"]
        same(eligible, plant["expectedEligible"], "plant candidate stock")
        same(max(0, requirement - eligible), plant["expectedShortage"], "plant shortage")
        same(version_ready(plant["version"], plant["id"], day, m["orderGood"]), plant["expectedDefinitionReady"], "plant production definition")
    p200 = next(p for p in m["plants"] if p["id"] == "P200")
    same(version_ready(m["approvedP200Version"], "P200", day, m["orderGood"]), m["expectedAfterFix"]["definitionReady"], "approved plant fix")
    same(max(0, requirement - p200["expectedEligible"]), m["expectedAfterFix"]["shortage"], "definition fix does not create stock")
    results["plantMaster"] = {"requirement": requirement, "afterFix": m["expectedAfterFix"]}

    m = data["mrp"]
    mrp = plan_mrp(m)
    for key, value in mrp.items():
        same(value, m["expected"][key], "MRP " + key)
    delayed = [dict(s, usableDay=6) if s["id"] == "PO-D4" else dict(s) for s in m["openSupply"]]
    delayed_plan = plan_mrp(m, delayed)
    same(delayed_plan["netShortage"], m["expected"]["delayedD4Shortage"], "delayed supply shortage")
    same(delayed_plan["proposal"], m["expected"]["delayedD4Proposal"], "delayed supply lot")
    results["mrp"] = mrp

    a = data["atp"]
    free = a["physical"] - a["existingProtected"]
    require(free >= 0 and a["supplyDay"] > a["requestedDay"], "invalid ATP timing or stock")
    same(free, a["expected"]["freeStock"], "ATP free stock")
    same(a["requested"] - free, a["expected"]["requestedDayShortage"], "ATP early shortage")
    for confirmation, supply in zip(a["confirmations"], (a["originalSupply"], a["revisedSupply"])):
        first = min(a["requested"], free)
        later = min(a["requested"] - first, supply)
        same(confirmation["atDay3"], first, "ATP requested date")
        same(confirmation["atDay5"], later, "ATP future supply")
        same(confirmation["unconfirmed"], a["requested"] - first - later, "ATP unconfirmed")
    same(len(a["confirmations"]), 2, "retained ATP versions")
    results["atp"] = a["confirmations"]

    w = data["ewm"]
    derived = [
        {"id": "initial", "bulk": w["initial"], "psa": 0, "erp": w["initial"]},
        {"id": "staged", "bulk": w["initial"] - w["staged"], "psa": w["staged"], "erp": w["initial"]},
        {"id": "consumed", "bulk": w["initial"] - w["staged"], "psa": w["staged"] - w["consumed"], "erp": w["initial"] - w["consumed"]},
        {"id": "returned", "bulk": w["initial"] - w["staged"] + w["returnedUnused"], "psa": w["staged"] - w["consumed"] - w["returnedUnused"], "erp": w["initial"] - w["consumed"]},
    ]
    same(derived, w["snapshots"], "EWM location and ERP history")
    for s in derived:
        require(s["bulk"] >= 0 and s["psa"] >= 0, "negative stock")
        same(s["bulk"] + s["psa"], s["erp"], "same-scope ERP stock")
    same(derived[2]["erp"] - derived[2]["bulk"], w["expected"]["apparentBulkOnlyDifference"], "excluded PSA")
    same(derived[-1]["erp"], w["expected"]["finalTotal"], "return does not create new inventory")
    results["ewm"] = derived

    m = data["mes"]
    final_ops = [o for o in m["operations"] if o["final"]]
    same(len(final_ops), 1, "one final operation in teaching route")
    good, scrap = final_ops[0]["yield"], final_ops[0]["scrap"]
    same(good, m["expected"]["finalGood"], "final good yield")
    same(scrap, m["expected"]["scrap"], "final scrap")
    same(sum(o["yield"] for o in m["operations"]), m["expected"]["sumOperationYields"], "operation counts kept separate")
    totals, seen = business_effects(m["events"])
    same(totals["confirmation"], good, "ERP confirmation")
    same(totals["issue"], good + scrap, "component conservation")
    same(totals["issue"], m["expected"]["consumption"], "component consumption")
    same(totals["receipt"], good, "finished goods receipt not doubled")
    same(totals["receipt"], m["expected"]["finishedReceipt"], "expected receipt")
    same(m["initialMaterial"] - totals["issue"], m["expected"]["materialBalance"], "material ending balance")
    ref = seen.get(m["warehouseEvidence"]["refersTo"])
    require(ref is not None and ref["kind"] == "receipt", "warehouse evidence lacks original receipt")
    same(m["warehouseEvidence"]["quantity"], ref["quantity"], "warehouse evidence quantity")
    same(all(s == "applied" for s in m["failedState"].values()), m["expected"]["failedComplete"], "partial completion")
    same(all(s == "applied" for s in m["recoveredState"].values()), m["expected"]["recoveredComplete"], "recovered completion")
    results["mes"] = {"effects": totals, "materialBalance": m["initialMaterial"] - totals["issue"], "partialComplete": m["expected"]["failedComplete"]}
    return results


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("erp-sap-cases.json")
    print(json.dumps(verify(json.loads(path.read_text())), ensure_ascii=False, indent=2))
