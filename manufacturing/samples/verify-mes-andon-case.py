# -*- coding: utf-8 -*-
"""Validate the declared teaching case; no live MES or machine control.
Usage: python3 verify-mes-andon-case.py mes-andon-case.json
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


def stamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(case):
    require(case['simulated'] is True, 'teaching data required')
    times = {k: stamp(v) for k, v in case['timeline'].items()}
    now = stamp(case['asOf'])
    order = ['raised', 'accepted', 'arrived', 'handled', 'verified', 'approved', 'resumed', 'closed']
    require(all(times[a] <= times[b] for a, b in zip(order, order[1:])), 'invalid lifecycle ordering')
    require(times['raised'] <= times['stopped'] <= times['resumed'] <= now, 'invalid stop interval')
    require(all(t <= now for t in times.values()), 'future fact beyond snapshot')
    require(times['raised'] <= times['alarmAcknowledged'], 'invalid alarm acknowledgement')
    require(all(case.get(k) for k in ['caseId', 'assetId', 'ruleVersion', 'acceptedBy', 'verificationRef', 'approvalRef', 'resumeRef', 'closeRef']), 'missing identity, owner or closure evidence')
    require(all(isinstance(case['rules'][k], (int, float)) and not isinstance(case['rules'][k], bool) and case['rules'][k] > 0 for k in ['acceptMinutes', 'restoreMinutes']), 'invalid threshold')
    alarms = {}
    for alarm in case['alarms']:
        require(alarm['id'] not in alarms, 'duplicate alarm definition')
        require(alarm['assetId'] == case['assetId'], 'unapproved asset merge')
        require(times['raised'] <= stamp(alarm['activeAt']) <= stamp(alarm['clearedAt']) <= times['verified'], 'invalid alarm interval')
        alarms[alarm['id']] = alarm
    links = case['approvedAlarmLinks']
    require({x['alarmId'] for x in links} == set(alarms) and len(links) == len(alarms) and all(x['basis'] for x in links), 'missing approved correlation')
    messages, event_payloads = {}, {}
    for event in case['deliveries']:
        alarm = alarms[event['alarmId']]
        payload = (event['alarmId'], event['assetId'], event['activeAt'])
        require(payload == (alarm['id'], alarm['assetId'], alarm['activeAt']), 'conflicting alarm payload')
        require(event['messageId'] not in messages or messages[event['messageId']] == payload, 'message identity conflict')
        messages[event['messageId']] = payload
        event_payloads[event['alarmId']] = payload
    require(set(event_payloads) == set(alarms), 'missing original event delivery')
    expected_due = {}
    for rule, start, end, threshold in [('accept', 'raised', 'accepted', 'acceptMinutes'), ('restore', 'stopped', 'resumed', 'restoreMinutes')]:
        due = times[start] + timedelta(minutes=case['rules'][threshold])
        if now >= due and times[end] > due:
            expected_due[(case['caseId'], rule, due.isoformat(), case['ruleVersion'])] = True
    receipts = {}
    for event in case['escalations']:
        key = (case['caseId'], event['rule'], stamp(event['dueAt']).isoformat(), event['ruleVersion'])
        require(key in expected_due and event['resultRef'], 'unsupported escalation or missing receipt')
        require(key not in receipts or receipts[key] == event['resultRef'], 'duplicate escalation produced new action')
        receipts[key] = event['resultRef']
    require(set(receipts) == set(expected_due), 'missing required escalation')
    def minutes(a, b):
        return (times[b] - times[a]).total_seconds() / 60
    result = dict(acceptMinutes=minutes('raised', 'accepted'), arrivalMinutes=minutes('raised', 'arrived'), responsePhasesMinutes=[minutes(a, b) for a, b in zip(order[:6], order[1:7])], callToResumeMinutes=minutes('raised', 'resumed'), downtimeMinutes=minutes('stopped', 'resumed'), administrativeMinutes=minutes('resumed', 'closed'), caseMinutes=minutes('raised', 'closed'), deliveryCount=len(case['deliveries']), alarmEventCount=len(event_payloads), businessCaseCount=1, uniqueEscalations=len(receipts))
    require(sum(result['responsePhasesMinutes']) == result['callToResumeMinutes'], 'phase reconciliation failed')
    require(result == case['expected'], 'declared metrics disagree with original records')
    return result


if __name__ == '__main__':
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('mes-andon-case.json')
    print(json.dumps(verify(json.loads(source.read_text())), ensure_ascii=False, indent=2))
