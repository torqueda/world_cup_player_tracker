#!/usr/bin/env python3
"""
Step 5 club normalization helper for the 2026 World Cup player-club map.

Inputs expected in --input-dir:
  clubs.csv
  player_club_at_callup.csv
  squad_entries.csv
  players.csv

This script is dependency-free and writes:
  clubs_normalized.csv
  player_club_at_callup_club_normalized.csv
  club_alias_map.csv
  club_normalization_review_queue.csv
  club_normalization_summary.csv
  pre_step5_audit.csv
  squad_entries_id_repaired.csv

Note: It applies a curated high-confidence alias map and leaves fuzzy/ambiguous cases in the review queue.
"""
import argparse, csv, os, re, unicodedata, collections
from difflib import SequenceMatcher

MERGE_GROUPS = {'AFC Bournemouth': ['AFC Bournemouth', 'Bournemouth'], 'AS Monaco': ['AS Monaco', 'Monaco'], 'AS Roma': ['AS Roma', 'Roma'], 'Al Ahli': ['Al Ahli', 'Al-Ahli'], 'Club América': ['Club América', 'América'], 'FC Augsburg': ['FC Augsburg', 'Augsburg'], 'Club Tijuana': ['Club Tijuana', 'Tijuana'], 'FC Midtjylland': ['FC Midtjylland', 'Midtjylland'], 'SC Freiburg': ['SC Freiburg', 'Freiburg'], 'Le Havre AC': ['Le Havre AC', 'Le Havre'], 'Pyramids FC': ['Pyramids FC', 'Pyramids'], 'St. Pauli': ['St. Pauli', 'St Pauli'], 'Union St.-Gilloise': ['Union St.-Gilloise', 'Union St-Gilloise', 'Royale-Union Saint Gilloise'], 'Viking FK': ['Viking FK', 'Viking'], 'Borussia Mönchengladbach': ['Borussia Mönchengladbach', 'Borussia Moenchengladbach'], 'Çaykur Rizespor': ['Çaykur Rizespor', 'Caykur Rizesport', 'Rizespor'], 'Paris Saint-Germain': ['Paris Saint-Germain', 'Paris Saint-Germian'], 'Dynamo Moscow': ['Dynamo Moscow', 'Dinamo Moscow'], 'TSG Hoffenheim': ['TSG Hoffenheim', 'Hoffenheim'], 'NK Maribor': ['NK Maribor', 'Maribor'], 'AJ Auxerre': ['AJ Auxerre', 'Auxerre'], 'VfL Wolfsburg': ['VfL Wolfsburg', 'Wolfsburg'], 'VfB Stuttgart': ['VfB Stuttgart', 'Stuttgart'], 'FCV Dender': ['FCV Dender', 'Dender'], 'Norwich City': ['Norwich City', 'Norwich'], 'Ipswich Town': ['Ipswich Town', 'Ipswich'], 'Wolverhampton Wanderers': ['Wolverhampton Wanderers', 'Wolverhampton'], 'Tigres UANL': ['Tigres UANL', 'Tigres'], 'West Ham United': ['West Ham United', 'West Ham'], 'Tottenham Hotspur': ['Tottenham Hotspur', 'Tottenham'], 'Espérance de Tunis': ['Espérance de Tunis', 'Esperance'], 'Feyenoord': ['Feyenoord', 'Feyenoord Rotterdam'], 'Internacional': ['Internacional', 'Internacional de Porto Alegre'], 'Brighton & Hove Albion': ['Brighton & Hove Albion', 'Brighton'], 'Newcastle United': ['Newcastle United', 'Newcastle'], 'Inter Milan': ['Inter Milan', 'Internazionale'], 'Sporting CP': ['Sporting CP', 'Sporting Lisbon'], 'PSV Eindhoven': ['PSV Eindhoven', 'PSV'], 'PAOK': ['PAOK', 'PAOK Salonika'], 'LASK': ['LASK', 'LASK Linz'], 'Copenhagen': ['Copenhagen', 'Kobenhavn'], 'Pumas UNAM': ['Pumas UNAM', 'Pumas'], 'Hamburger SV': ['Hamburger SV', 'Hamburg SV', 'Hamburg'], 'FC Nordsjælland': ['FC Nordsjælland', 'Nordsjaelland'], 'Al Ettifaq': ['Al Ettifaq', 'Al Etiffaq']}
def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def write_csv(path, rows, fieldnames):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)

def strip_accents(s):
    if s is None: return ""
    repl={"ø":"o","Ø":"O","đ":"d","Đ":"D","ð":"d","Ð":"D","þ":"th","Þ":"Th","ł":"l","Ł":"L","ß":"ss","æ":"ae","Æ":"AE","œ":"oe","Œ":"OE"}
    for k,v in repl.items():
        s=s.replace(k,v)
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def basic_norm(s):
    s=strip_accents(s or '').lower().replace('&',' and ')
    s=re.sub(r'[^a-z0-9]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

def trailing_hash(pid):
    return (pid or '').split('_')[-1]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input-dir', required=True)
    ap.add_argument('--output-dir', required=True)
    args=ap.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    players=read_csv(os.path.join(args.input_dir,'players.csv'))
    old_clubs=read_csv(os.path.join(args.input_dir,'clubs.csv'))
    old_pcc=read_csv(os.path.join(args.input_dir,'player_club_at_callup.csv'))
    old_squad=read_csv(os.path.join(args.input_dir,'squad_entries.csv'))

    current_player_ids={r['player_id'] for r in players}
    repair_map={}
    for old_pid in sorted(({r['player_id'] for r in old_pcc}|{r['player_id'] for r in old_squad})-current_player_ids):
        cands=[pid for pid in current_player_ids if trailing_hash(pid)==trailing_hash(old_pid)]
        if len(cands)==1:
            repair_map[old_pid]=cands[0]

    club_by_id={r['club_id']:r for r in old_clubs}
    clubs_by_name=collections.defaultdict(list)
    for r in old_clubs:
        clubs_by_name[r['club_name']].append(r)
    pcc_counts=collections.Counter(r['club_id'] for r in old_pcc)
    teams_by_clubid=collections.defaultdict(collections.Counter)
    for r in old_pcc:
        teams_by_clubid[r['club_id']][r['team']]+=1

    canonical_for_old_id={}
    canonical_names_by_id={}
    canonical_aliases_by_id=collections.defaultdict(list)
    alias_rule_by_old_id={}
    alias_conf_by_old_id={}
    for canon, aliases in MERGE_GROUPS.items():
        present=[a for a in aliases if a in clubs_by_name]
        if not present:
            continue
        pref=clubs_by_name[canon][0] if canon in clubs_by_name else clubs_by_name[present[0]][0]
        canon_id=pref['club_id']
        canonical_names_by_id[canon_id]=canon
        for a in present:
            for row in clubs_by_name[a]:
                canonical_for_old_id[row['club_id']]=canon_id
                canonical_aliases_by_id[canon_id].append(row['club_name'])
                alias_rule_by_old_id[row['club_id']]='auto_merge_curated_alias'
                alias_conf_by_old_id[row['club_id']]='high'
    for r in old_clubs:
        if r['club_id'] not in canonical_for_old_id:
            cid=r['club_id']
            canonical_for_old_id[cid]=cid
            canonical_names_by_id[cid]=r['club_name']
            canonical_aliases_by_id[cid].append(r['club_name'])
            alias_rule_by_old_id[cid]='unchanged'
            alias_conf_by_old_id[cid]='not_applicable'

    canonical_player_counts=collections.Counter()
    teams_by_canon=collections.defaultdict(collections.Counter)
    for r in old_pcc:
        cid=canonical_for_old_id[r['club_id']]
        canonical_player_counts[cid]+=1
        teams_by_canon[cid][r['team']]+=1

    normalized_clubs=[]
    seen=set()
    for old in old_clubs:
        cid=canonical_for_old_id[old['club_id']]
        if cid in seen: continue
        seen.add(cid)
        base=club_by_id[cid]
        canon_name=canonical_names_by_id[cid]
        aliases=sorted(set(canonical_aliases_by_id[cid]), key=lambda x: (x != canon_name, x))
        normalized_clubs.append({
            'club_id': cid, 'wikidata_id': base.get('wikidata_id',''),
            'club_name': canon_name, 'club_name_ascii': strip_accents(canon_name),
            'country': base.get('country',''), 'league': base.get('league',''),
            'city': base.get('city',''), 'stadium': base.get('stadium',''),
            'club_lat': '', 'club_lon': '', 'club_source_url': base.get('club_source_url',''),
            'geo_source': '', 'manual_review_flag': 'FALSE',
            'notes': ('Merged aliases/source variants: ' + '; '.join(aliases) + '. ' if len(aliases)>1 else '') + 'Wikidata/league/city/stadium pending Step 5b/Step 6.',
            'player_count_at_callup': canonical_player_counts[cid],
            'alias_count': len(aliases),
        })
    normalized_clubs.sort(key=lambda r: basic_norm(r['club_name']))

    alias_map=[]
    for old in sorted(old_clubs, key=lambda r: basic_norm(r['club_name'])):
        cid=old['club_id']; canon_id=canonical_for_old_id[cid]
        alias_map.append({
            'raw_club_id': cid, 'raw_club_name': old['club_name'], 'raw_club_name_ascii': old.get('club_name_ascii') or strip_accents(old['club_name']),
            'canonical_club_id': canon_id, 'canonical_club_name': canonical_names_by_id[canon_id],
            'alias_rule': alias_rule_by_old_id[cid], 'merge_confidence': alias_conf_by_old_id[cid],
            'player_count_for_raw_club_id': pcc_counts[cid],
            'teams_using_raw_club_id': '; '.join(f'{t}:{c}' for t,c in teams_by_clubid[cid].most_common()),
            'normalization_notes': 'No normalization merge applied.' if cid==canon_id and len(set(canonical_aliases_by_id[canon_id]))==1 else f"Collapsed source variant to canonical club '{canonical_names_by_id[canon_id]}'.",
        })

    pcc_out=[]
    for r in old_pcc:
        old_pid=r['player_id']; new_pid=repair_map.get(old_pid, old_pid)
        old_cid=r['club_id']; canon_id=canonical_for_old_id[old_cid]
        out=dict(r)
        out['player_id']=new_pid; out['club_id']=canon_id
        notes=[]
        if r.get('notes'): notes.append(r['notes'])
        if old_pid!=new_pid: notes.append(f'Repaired player_id from {old_pid} to {new_pid}.')
        if old_cid!=canon_id: notes.append(f"Normalized club_id from {old_cid} to {canon_id} ({canonical_names_by_id[canon_id]}).")
        out['notes']=' '.join(notes)
        out['original_player_id']=old_pid; out['original_club_id']=old_cid
        out['canonical_club_name']=canonical_names_by_id[canon_id]
        out['club_normalization_rule']=alias_rule_by_old_id[old_cid]
        pcc_out.append(out)

    squad_out=[]
    for r in old_squad:
        old_pid=r['player_id']; new_pid=repair_map.get(old_pid, old_pid)
        out=dict(r); out['player_id']=new_pid
        out['original_player_id']=old_pid
        out['player_id_repair_note']='' if old_pid==new_pid else f'Repaired player_id from {old_pid} to {new_pid}.'
        squad_out.append(out)

    rows_by_id={r['club_id']:r for r in normalized_clubs}
    ids=list(rows_by_id)
    review=[]; n=1
    for i,a_id in enumerate(ids):
        a=rows_by_id[a_id]['club_name']; an=basic_norm(a); toks_a=set(an.split())
        for b_id in ids[i+1:]:
            b=rows_by_id[b_id]['club_name']; bn=basic_norm(b); toks_b=set(bn.split())
            if not toks_a or not toks_b: continue
            common=toks_a&toks_b
            overlap=len(common)/min(len(toks_a),len(toks_b))
            ratio=SequenceMatcher(None,an,bn).ratio()
            include=False; reason=[]
            if ratio>=0.88 and overlap>=0.45:
                include=True; reason.append(f'high string similarity {ratio:.2f}')
            if overlap==1.0 and min(len(an),len(bn))>=6:
                include=True; reason.append('one name is token subset of the other')
            if common and ratio>=0.75 and any(t in common for t in ['barcelona','newcastle','nacional','santos','independiente','al','athletic','orlando','brugge']):
                include=True; reason.append('shared high-risk club/location token')
            if include and common:
                review.append({
                    'review_id': f'club_norm_review_{n:04d}',
                    'issue_type': 'possible_duplicate_or_name_collision',
                    'club_id_a': a_id, 'club_name_a': a, 'player_count_a': canonical_player_counts[a_id],
                    'teams_a': '; '.join(f'{t}:{c}' for t,c in teams_by_canon[a_id].most_common(8)),
                    'club_id_b': b_id, 'club_name_b': b, 'player_count_b': canonical_player_counts[b_id],
                    'teams_b': '; '.join(f'{t}:{c}' for t,c in teams_by_canon[b_id].most_common(8)),
                    'similarity_score': f'{ratio:.3f}', 'token_overlap': f'{overlap:.3f}',
                    'candidate_reason': '; '.join(reason),
                    'recommended_action': 'manual_review_before_merge',
                    'notes': 'Not auto-merged by this pass; verify club identity, country, league, and Wikidata QID before merging.',
                })
                n+=1
    review.sort(key=lambda r: (-float(r['similarity_score']), r['club_name_a'], r['club_name_b']))

    summary=[
        {'metric':'current_players_rows','value':len(players),'notes':'From players.csv.'},
        {'metric':'old_clubs_rows','value':len(old_clubs),'notes':'Input Step 2 clubs.csv.'},
        {'metric':'normalized_canonical_clubs','value':len(normalized_clubs),'notes':'clubs_normalized.csv rows.'},
        {'metric':'canonical_club_reduction','value':len(old_clubs)-len(normalized_clubs),'notes':'Old club rows collapsed.'},
        {'metric':'auto_merge_groups','value':len(MERGE_GROUPS),'notes':'Curated high-confidence club-name groups applied.'},
        {'metric':'review_queue_rows','value':len(review),'notes':'Candidates not auto-merged.'},
        {'metric':'player_id_repairs_applied','value':len(repair_map),'notes':'Repairs where old Step 2 IDs no longer joined to current players.'},
        {'metric':'geocoding_filled','value':0,'notes':'Intentionally blank; geocode after approval.'},
    ]

    audit=[
        {'check':'players_row_count','status':'PASS' if len(players)==1248 else 'WARN','value':len(players),'notes':'Expected one row per player.'},
        {'check':'player_id_unique','status':'PASS' if len({r["player_id"] for r in players})==len(players) else 'WARN','value':len({r["player_id"] for r in players}),'notes':'player_id should be stable and unique.'},
        {'check':'old_step2_join_to_current_players','status':'PASS' if not repair_map else 'WARN','value':len(repair_map),'notes':'Any repaired player_id should be reviewed before replacing source sheets.'},
    ]

    club_fields=['club_id','wikidata_id','club_name','club_name_ascii','country','league','city','stadium','club_lat','club_lon','club_source_url','geo_source','manual_review_flag','notes','player_count_at_callup','alias_count']
    write_csv(os.path.join(args.output_dir,'clubs_normalized.csv'), normalized_clubs, club_fields)
    write_csv(os.path.join(args.output_dir,'club_alias_map.csv'), alias_map, list(alias_map[0]))
    write_csv(os.path.join(args.output_dir,'player_club_at_callup_club_normalized.csv'), pcc_out, list(old_pcc[0])+['original_player_id','original_club_id','canonical_club_name','club_normalization_rule'])
    write_csv(os.path.join(args.output_dir,'squad_entries_id_repaired.csv'), squad_out, list(old_squad[0])+['original_player_id','player_id_repair_note'])
    write_csv(os.path.join(args.output_dir,'club_normalization_review_queue.csv'), review, list(review[0]) if review else ['review_id','issue_type','club_id_a','club_name_a','player_count_a','teams_a','club_id_b','club_name_b','player_count_b','teams_b','similarity_score','token_overlap','candidate_reason','recommended_action','notes'])
    write_csv(os.path.join(args.output_dir,'club_normalization_summary.csv'), summary, ['metric','value','notes'])
    write_csv(os.path.join(args.output_dir,'pre_step5_audit.csv'), audit, ['check','status','value','notes'])

if __name__ == '__main__':
    main()
