#!/usr/bin/env python3
"""Read-only saved CISC alert-table key and same-name MSGF-ID validation.

Build recovered inventories once, reconstruct each same-name message-file
index once, do set-membership joins, check Guided select/Back, and hash the
original image before and after. Emit aggregate-only counts. No message text,
alert keys, object names or recovered bytes are output or committed.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from as400_alert_tables import AlertTableExplorer
from as400_capabilities import read_prefix
from as400_dasd import DASDImage
from as400_5250 import Guided5250
from as400_messages import MessageExplorer, decode_message_index, MAX_PRIMARY
from tools.validate_command_exploration import digest


def validate(path):
    before=digest(path)
    image=DASDImage(path)
    scan=image.scan()
    segments=image.recover_segments(scan)
    inventory=image.recover_objects(scan,segments)
    messages=MessageExplorer(image,inventory,segments)
    alerts=AlertTableExplorer(image,inventory,message_explorer=messages)
    messages.alert_explorer=alerts
    model=Guided5250(inventory,alert_loader=alerts.rows,message_loader=messages.rows)
    counts=Counter()
    msgid_sets={}
    saw_key=False
    saw_confirmed=False
    saw_reverse=False
    for obj in inventory.objects:
        if obj.type_code!="0E/09":
            continue
        counts["recovered alert-table primaries"]+=1
        try:
            keys,warnings,size=alerts.entries(obj)
        except (ValueError,OSError):
            counts["unrecoverable or unsupported alert-table primaries"]+=1
            continue
        counts["reconstructed saved 12-byte keys"]+=len(keys)
        counts["saved index warnings"]+=len(warnings)
        counts[f"page size {size}"]+=1
        sources=alerts._messages.get(obj.name.upper(),())
        counts["same-name recovered MSGF candidates"]+=len(sources)
        for source in sources:
            origin=(source.segment.start_lba,source.segment.virtual_address)
            if origin not in msgid_sets:
                try:
                    entries,msgwarnings=decode_message_index(
                        read_prefix(image,source.segment,MAX_PRIMARY),
                        source.segment.virtual_address)
                    msgid_sets[origin]={entry.identifier for entry in entries}
                    counts["reconstructed message-index IDs"]+=len(entries)
                    counts["message-index warnings"]+=len(msgwarnings)
                except (ValueError,OSError):
                    msgid_sets[origin]=None
                    counts["withheld same-name MSGF indexes"]+=1
        for key in keys:
            token=key.message_id_candidate
            counts["C-tag message-ID candidates"]+=bool(token)
            counts["opaque/other-tag keys"]+=(not bool(token))
            if not token:
                continue
            corroborated=sum(token in msgid_sets[(s.segment.start_lba,s.segment.virtual_address)]
                             for s in sources
                             if msgid_sets[(s.segment.start_lba,s.segment.virtual_address)] is not None)
            counts["independently corroborated exact MSGF ID links"]+=corroborated
            counts["candidate IDs without corroborated saved MSGF ID"]+=(corroborated==0)
            counts["ambiguous same-ID message-file candidates"]+=(corroborated>1)
            if corroborated and not saw_reverse:
                verified_source=next(
                    source for source in sources
                    if (msgid_sets[(source.segment.start_lba,
                                    source.segment.virtual_address)] is not None and
                        token in msgid_sets[(source.segment.start_lba,
                                             source.segment.virtual_address)]))
                model.show_evidence(dict(obj=verified_source, pattern=token),
                                    messages.rows)
                idx=next((i for i,row in enumerate(model.rows())
                          if (row.get("kind")=="message_action" and
                              row.get("name")==token and
                              row.get("request",{}).get("entry") is not None)),None)
                if idx is None:
                    raise ValueError("Independently verified MSGF ID is missing from Guided message view")
                model.selected=idx
                model.open_row(idx)
                if model.rows()[0]["name"]!="Index evidence":
                    raise ValueError("Saved message record detail did not open")
                rev=next((j for j,row in enumerate(model.rows())
                          if row.get("kind")=="alert_index_action" and
                          row.get("request",{}).get("entry") is not None),None)
                if rev is None:
                    raise ValueError("Exact-ID reverse alert link missing")
                model.selected=rev
                model.open_row(rev)
                if model.rows()[0]["name"]!="Saved alert-table key":
                    raise ValueError("Reverse message-to-alert key did not open")
                model.back()
                if model.selected!=rev:
                    raise ValueError("Reverse alert-key Back selection changed")
                model.back()
                if model.selected!=idx:
                    raise ValueError("Reverse saved-message Back selection changed")
                counts["reverse MSGF to alert-key/Back walkthroughs"]+=1
                saw_reverse=True
        if keys and not saw_key:
            model.show_evidence(dict(obj=obj),alerts.rows)
            i=next((i for i,r in enumerate(model.rows())
                    if r.get("kind")=="alert_index_action" and
                    r.get("request",{}).get("entry") is not None),None)
            if i is not None:
                model.selected=i;model.open_row(i)
                if model.rows()[0]["name"]!="Saved alert-table key":
                    raise ValueError("Alert-table key detail did not open")
                link=next((j for j,r in enumerate(model.rows())
                           if r.get("kind")=="message_action" and
                           r.get("request",{}).get("entry") is not None),None)
                if link is not None:
                    model.selected=link;model.open_row(link)
                    if model.rows()[0]["name"]!="Index evidence":
                        raise ValueError("Corroborated MSGF record action not opened")
                    model.back()
                    if model.selected!=link:
                        raise ValueError("Alert-to-message Back lost selection")
                    counts["corroborated message/Back walkthroughs"]+=1
                    saw_confirmed=True
                model.back()
                if model.selected!=i:
                    raise ValueError("Alert-key/Back lost selection")
                counts["alert key/Back walkthroughs"]+=1
                saw_key=True
    after=digest(path)
    if before!=after:
        raise ValueError("Original HDA SHA256 changed")
    return {"image_bytes":Path(path).stat().st_size,
            "sha256":after,
            "unchanged":True,
            "counts":dict(sorted(counts.items()))}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("image")
    print(json.dumps(validate(p.parse_args().image),indent=2))
