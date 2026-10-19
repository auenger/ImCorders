#!/usr/bin/env python3
"""Verify teaching data only. No network access or production-system writes.
Download this script and either JSON sample into one folder, then run:
  python3 verify-wms-time-samples.py wms-fifo-fefo.json
With no arguments, both samples must exist alongside this script.
These checks do not verify actual WMS configuration, product quality or compliance.
"""
import copy
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

def dt(value):return datetime.fromisoformat(value)

def candidates(j,arrival=None):
    arrival=dt(arrival or j['demand']['arrivalAt'])
    threshold=arrival+timedelta(days=j['demand']['minimumRemainingDays'])
    accepted=[];excluded={}
    for row in j['stock']:
        assert 0<=row['reservedOther']<=row['quantity']
        reasons=[]
        if not row['qualityReleased']:reasons.append('quality_hold')
        if row['expiresAt'] is None:reasons.append('expiry_unknown')
        else:
            expiry=dt(row['expiresAt'])
            if expiry<=dt(j['snapshotAt']):reasons.append('expired_now')
            if expiry<threshold or expiry<=arrival:reasons.append('insufficient_remaining')
        free=row['quantity']-row['reservedOther']
        if free<=0:reasons.append('no_free_stock')
        if reasons:excluded[row['id']]=reasons
        else:accepted.append(dict(row,free=free))
    return accepted,excluded,threshold

def allocate(j,rows,policy):
    if policy=='FIFO':key=lambda x:(dt(x['receivedAt']),x['id'])
    elif policy=='FEFO':key=lambda x:(dt(x['expiresAt']),dt(x['receivedAt']),x['id'])
    else:raise ValueError(policy)
    remaining=j['demand']['quantity'];result=[]
    for row in sorted(rows,key=key):
        take=min(remaining,row['free'])
        if take>0:result.append(dict(lot=row['id'],quantity=take));remaining-=take
    return result,remaining

def verify_wms(j):
    assert j['illustrative'] and j['assumptions']
    assert len({x['id'] for x in j['stock']})==len(j['stock'])
    rows,excluded,threshold=candidates(j)
    assert excluded==j['expected']['excluded']
    assert threshold==dt(j['expected']['thresholdAt'])
    assert sum(x['quantity'] for x in j['stock'])==j['expected']['physical']
    assert sum(x['free'] for x in rows)==j['expected']['candidate']
    for policy in ['FIFO','FEFO']:
        plan,shortage=allocate(j,rows,policy)
        assert shortage==0 and plan==j['expected'][policy.lower()]
        assert sum(x['quantity'] for x in plan)==j['demand']['quantity']
    rows,_,_=candidates(j,j['delayedArrivalAt'])
    assert sum(x['free'] for x in rows)==j['expected']['delayedCandidate']
    assert allocate(j,rows,'FEFO')[1]==j['expected']['delayedShortage']
    # Date equality is allowed, while a quality hold remains a separate barrier.
    boundary=copy.deepcopy(j)
    next(x for x in boundary['stock'] if x['id']=='F3')['qualityReleased']=True
    assert 'F3' in {x['id'] for x in candidates(boundary)[0]}
    # Independent scan-time freeze scenario: the original plan is not permission.
    frozen=copy.deepcopy(j)
    next(x for x in frozen['stock'] if x['id']=='F2')['qualityReleased']=False
    assert 'F2' not in {x['id'] for x in candidates(frozen)[0]}
    receipts={};actualByLot={}
    for row in j['shortPickReceipts']:
        key=row['eventId']
        if key in receipts:assert receipts[key]==row
        else:
            receipts[key]=row
            actualByLot[row['lot']]=actualByLot.get(row['lot'],0)+row['quantity']
    plan={r['lot']:r['quantity'] for r in j['expected']['fefo']}
    assert all(0<=q<=plan[lot] for lot,q in actualByLot.items())
    assert sum(actualByLot.values())==j['expected']['picked']
    assert j['demand']['quantity']-sum(actualByLot.values())==j['expected']['incomplete']
    original=next(x for x in j['stock'] if x['id']==j['move']['lot'])
    assert j['move']['originalReceiptAt']==original['receivedAt']
    assert j['move']['expiresAt']==original['expiresAt']

def exposure_minutes(j,at):
    total=0;lastEnd=None
    for interval in j['exposureIntervals']:
        start=dt(interval['start']);end=dt(interval['end']) if interval['end'] else at
        assert interval['end'] is None or end>=start
        assert lastEnd is None or start>=lastEnd
        total+=max(0,(min(at,end)-start).total_seconds()/60)
        lastEnd=end
    return total

def start_allowed(j,at):
    if not j['coverageComplete']:return None
    b=j['batch'];r=j['rules']
    return (dt(b['previousOperationCompletedAt'])<=at<dt(b['previousOperationCompletedAt'])+timedelta(minutes=r['maximumWaitMinutes'])
        and dt(b['openedAt'])<=at<dt(b['openedAt'])+timedelta(minutes=r['openUseMinutes'])
        and at<dt(b['expiresAt']) and exposure_minutes(j,at)<r['maximumExposureMinutes'])

def route_allowed(j,start,end):
    if not start_allowed(j,start):return False
    if end is None:return False
    assert end>=start
    return (end<dt(j['batch']['expiresAt'])
        and end<dt(j['batch']['openedAt'])+timedelta(minutes=j['rules']['openUseMinutes'])
        and exposure_minutes(j,end)<j['rules']['maximumExposureMinutes'])

def verify_wip(j):
    assert j['illustrative'] and j['assumptions']
    b=j['batch'];r=j['rules'];e=j['expected'];asof=dt(j['asOf'])
    exposure=exposure_minutes(j,asof)
    assert exposure==e['exposureAtAsOf']
    assert r['maximumExposureMinutes']-exposure==e['remainingExposure']
    wait=dt(b['previousOperationCompletedAt'])+timedelta(minutes=r['maximumWaitMinutes'])
    opened=dt(b['openedAt'])+timedelta(minutes=r['openUseMinutes'])
    continuous=asof+timedelta(minutes=e['remainingExposure'])
    assert wait==dt(e['waitDeadline']) and opened==dt(e['openUseDeadline'])
    assert continuous==dt(e['continuousExposureDeadline'])
    assert min(wait,opened,dt(b['expiresAt']),continuous)==dt(e['earliestStartBoundary'])
    assert dt(j['qualifiedPause']['start'])==dt(j['exposureIntervals'][0]['end'])
    assert dt(j['qualifiedPause']['end'])==dt(j['exposureIntervals'][1]['start'])
    for scenario in j['scenarios']:
        start=dt(scenario['start']);end=dt(scenario['end']) if scenario['end'] else None
        assert start_allowed(j,start)==scenario['expectedStartAllowed']
        assert route_allowed(j,start,end)==scenario['expectedRouteAllowed']
        assert exposure_minutes(j,start)==scenario['expectedStartExposure']
        if end:assert exposure_minutes(j,end)==scenario['expectedEndExposure']
    children=j['split']['children']
    assert len({x['id'] for x in children})==len(children)
    assert not j['split']['parentCurrent']
    assert sum(x['quantityKg'] for x in children)==b['quantityKg']
    assert all(x['inheritsFrom']==b['id'] for x in children)
    assert not j['returnEvent']['resetsClocks']
    # Both child contexts inherit the same historical timestamps and rule version.
    for child in children:
        inherited=copy.deepcopy(j);inherited['batch']=dict(b,id=child['id'],quantityKg=child['quantityKg'])
        assert not start_allowed(inherited,dt(j['returnEvent']['at']))
    late=j['lateStartEvent'];assert late['trustedSourceTime']
    assert dt(late['receivedAt'])>dt(late['occurredAt'])
    assert start_allowed(j,dt(late['occurredAt']))==e['lateTrustedStartAllowed']
    assert not start_allowed(j,dt(late['receivedAt']))
    unknown=copy.deepcopy(j);unknown['coverageComplete']=False
    assert start_allowed(unknown,dt(j['scenarios'][0]['start'])) is None

CHECKS={'wms-fifo-fefo.json':verify_wms,'wip-time-windows.json':verify_wip}
if __name__=='__main__':
    paths=[Path(x) for x in sys.argv[1:]] or [Path(__file__).with_name(x) for x in CHECKS]
    for path in paths:
        CHECKS[path.name](json.loads(path.read_text()));print('PASS',path.name)
    print('Teaching sample consistency verified; no real system or process was verified.')
