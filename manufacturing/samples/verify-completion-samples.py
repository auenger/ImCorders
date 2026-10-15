#!/usr/bin/env python3
"""Verify illustrative manufacturing samples, without network or system writes.

Download this file and desired JSON samples into one directory, then run:
  python3 verify-completion-samples.py system-recovery.json
With no arguments, all 11 samples must exist next to this script.
Checks cover arithmetic, identity, scope and sample rules, not real operations,
engineering safety, legal applicability, protocol conformance or certification.
"""
import json
import sys
from collections import Counter
from decimal import Decimal as D
from pathlib import Path


def distinct(values):
    assert len(values) == len(set(values)), 'Repeated identity'
    return set(values)


def partition(universe, *groups):
    universe = distinct(universe)
    groups = [distinct(x) for x in groups]
    assert set().union(*groups) == universe, 'Incomplete or extra scope'
    assert sum(map(len, groups)) == len(universe), 'Overlapping groups'


def recovery(j):
    source = {x['id']: x['quantity'] for x in j['source']}
    assert len(source) == len(j['source'])
    target = {x['sourceId']: x['quantity'] for x in j['restoredTarget']}
    assert len(target) == len(j['restoredTarget'])
    assert all(source[k] == v for k, v in target.items())
    assert j['opening'] + sum(target.values()) == j['expected']['restoredBalance']
    added = 0
    for key in j['deliveries']:
        if key not in target:
            target[key] = source[key]
            added += 1
        assert target[key] == source[key]
    assert target == source, 'Both directions must match'
    assert added == j['expected']['newPostings']
    assert len(target) == j['expected']['uniqueActions']
    assert j['opening'] + sum(target.values()) == j['expected']['finalBalance']


def downtime(j):
    finishes = {}
    for p in j['plans']:
        finish = p['available'] + p['setup'] + p['process'] + j['inspectionMinutes']
        assert finish == p['expectedFinish']
        assert max(0, finish - j['deadline']) == p['expectedDelay']
        finishes[p['id']] = finish
    assert finishes['PLAN-A'] - finishes['PLAN-B'] == j['expectedImprovement']


def service(j):
    partition(j['authorized'], j['received'], j['missing'])
    partition(j['received'], j['repaired'], j['scrapped'])
    assert distinct(j['redelivered']) == set(j['repaired'])
    assert distinct([x['serial'] for x in j['replacements']]) == set(j['repaired'])
    distinct([x['newPart'] for x in j['replacements']])
    distinct([x['oldPart'] for x in j['replacements']])
    for name, count in j['expected'].items():
        assert len(j[name]) == count


def machining(j):
    partition(j['parts'], j['scrapped'], j['atVendor'], j['held'], j['released'])
    partition(j['sentToVendor'], j['returned'], j['atVendor'])
    partition(j['returned'], j['released'], j['held'])
    assert distinct([x['part'] for x in j['installations']]) == set(j['released'])
    distinct([(x['unit'], x['position']) for x in j['installations']])
    units = Counter(x['unit'] for x in j['installations'])
    assert all(n == j['partsPerUnit'] for n in units.values())
    assert len(units) == j['expected']['readyUnits']
    assert j['unitDemand'] * j['partsPerUnit'] - len(j['released']) == j['expected']['missingParts']


def automotive(j):
    measured = distinct([x['serial'] for x in j['measurements']])
    assert measured <= distinct(j['serials'])
    outside = [x['serial'] for x in j['measurements'] if not D(j['lower']) <= D(x['value']) <= D(j['upper'])]
    assert outside == j['expected']['outside']
    assert len(measured) - len(outside) == j['expected']['within']
    assert len(set(j['serials']) - measured) == j['expected']['unmeasured']
    assert outside and set(j['held']) == set(j['serials'])
    assert len(j['held']) == j['expected']['held']


def food(j):
    assert sum(x['kg'] for x in j['inputs']) == j['foodKg'] + j['lossKg'] == j['expected']['inputKg']
    assert D(str(j['bags'])) * D(str(j['kgPerBag'])) == D(str(j['foodKg']))
    assert sum(x['bags'] for x in j['destinations']) == j['bags'] == j['expected']['candidateBags']
    assert sum(x['bags'] for x in j['destinations'] if x['kind'] == 'shipped') == j['expected']['shipped']
    assert [x['id'] for x in j['destinations'] if x.get('notificationAcknowledged') is False] == j['expected']['pendingAcknowledgment']


def pharma(j):
    assert j['theoretical'] == j['packed'] + j['loss']
    assert j['packed'] == j['retained'] + j['pendingStock']
    assert D(j['packed']) / D(j['theoretical']) * 100 == D(j['expected']['yieldPercent'])
    assert all(j['review'].values()) == j['expected']['releaseAllowed']
    assert j['review']['labApproved'] and not j['review']['deviationClosed']


def chemical(j):
    total = sum(j['inputKg'])
    assert total - j['productKg'] - j['transitionKg'] - j['inventoryIncreaseKg'] == j['expected']['residualKg']
    assert total - j['productKg'] - j['transitionKg'] - j['alternativeInventoryIncreaseKg'] == j['expected']['alternativeResidualKg']
    assert sum(x['kg'] for x in j['tanks']) == j['productKg']


def semiconductor(j):
    wafers = distinct([x['wafer'] for x in j['slots']])
    distinct([x['slot'] for x in j['slots']])
    unique = {}
    for event in j['events']:
        assert event['wafer'] in wafers
        if event['eventId'] in unique:
            assert unique[event['eventId']] == event
        unique[event['eventId']] = event
    assert len(j['events']) == j['expected']['deliveries']
    assert len(unique) == j['expected']['uniqueEvents']
    start = {e['wafer'] for e in unique.values() if e['state'] == 'start'}
    end = {e['wafer'] for e in unique.values() if e['state'] == 'end'}
    assert start == wafers and end <= start and len(end) == j['expected']['completed']
    unknown = wafers - end
    assert unknown == set(j['expected']['unknown'])
    partition(wafers, j['released'], j['qualityHeld'], unknown)
    assert set(j['released']) | set(j['qualityHeld']) == end
    assert len(j['released']) == j['expected']['released']


def battery(j):
    cells = j['cells']; ids = distinct([x['id'] for x in cells])
    assert cells[0]['startM'] == 0 and cells[-1]['endM'] == j['rollLengthM']
    assert all(x['endM'] == y['startM'] for x, y in zip(cells, cells[1:]))
    assert all(x['startM'] < x['endM'] for x in cells)
    hit = {x['id'] for x in cells if x['startM'] < j['defect']['endM'] and x['endM'] > j['defect']['startM']}
    assert hit == set(j['preheld'])
    passed = [x['id'] for x in j['passed']]
    partition(ids, j['preheld'], passed, j['pending'], j['scrapped'])
    partition(j['tested'], passed, j['pending'], j['scrapped'])
    for name, values in [('preheld',j['preheld']),('passed',passed),('pending',j['pending']),('scrapped',j['scrapped'])]:
        assert len(values) == j['expected'][name]
    grades = {x['id']: 'A' if D(x['capacityAh']) >= D(j['gradeRule']['minimumA']) else 'B' if D(x['capacityAh']) >= D(j['gradeRule']['minimumB']) else 'below' for x in j['passed']}
    assert Counter(grades.values()) == {'A':j['expected']['gradeA'], 'B':j['expected']['gradeB']}
    assert distinct([x['cell'] for x in j['installations']]) == set(passed)
    distinct([(x['module'],x['position']) for x in j['installations']])
    modules = {x['module'] for x in j['installations']}
    assert len(modules) == j['expected']['modules']
    for module in modules:
        members = [x['cell'] for x in j['installations'] if x['module'] == module]
        assert len(members) == 10 and len({grades[x] for x in members}) == 1


def device(j):
    partition(j['devices'],j['released'],j['held'],j['scrapped'])
    shipped = distinct([x['serial'] for x in j['shipments']])
    partition(j['released'],shipped,j['stock'])
    assert distinct([x['serial'] for x in j['components']]) == set(j['devices'])
    candidate = {x['serial'] for x in j['components'] if x['batch'] == j['complaint']['candidateBatch']}
    assert j['complaint']['serial'] in candidate
    assert len(candidate) == j['expected']['candidateCount']
    assert Counter(x['customer'] for x in j['shipments'] if x['serial'] in candidate) == j['expected']['byCustomer']


CHECKS = {'system-recovery.json':recovery,'downtime-delivery.json':downtime,'service-return.json':service,'machining-assembly.json':machining,'automotive-quality.json':automotive,'food-traceability.json':food,'pharma-batch.json':pharma,'chemical-balance.json':chemical,'semiconductor-events.json':semiconductor,'battery-genealogy.json':battery,'medical-device-records.json':device}
paths = [Path(x) for x in sys.argv[1:]] or [Path(__file__).with_name(x) for x in CHECKS]
for path in paths:
    data = json.loads(path.read_text())
    assert data['illustrative'] is True and data['assumptions']
    CHECKS[path.name](data)
    print('PASS',path.name)
print('Sample consistency verified; no real factory or compliance claims verified.')
