import json
import logging
import tomllib
import requests
from typing import Any
from datetime import datetime
from requests.auth import HTTPBasicAuth

PCO_SECRETS = tomllib.load(open('secrets.toml', 'rb'))
LOG = logging.getLogger(__name__)

class Blockout:
    def __init__(self, start: str, end: str):
        self.start: datetime = datetime.fromisoformat(start)
        self.end: datetime = datetime.fromisoformat(end)

    def __str__(self) -> str:
        return (
            f"Blockout(start={self.start.date().isoformat()}, end={self.end.date().isoformat()})"
        )

class TeamPosition:
    def __init__(self, name: str, schedule_preference: str, skill_level: int):
        self.name: str = name
        self.schedule_preference: str = schedule_preference
        self.skill_level: int = skill_level

    def __str__(self) -> str:
        return (
            f"TeamPosition(name={self.name}, "
            f"schedule_preference={self.schedule_preference}, "
            f"skill_level={self.skill_level})"
        )
    
class TeamMember:
    def __init__(self, name: str, positions: list[TeamPosition], blockouts: list[Blockout]):
        self.name: str = name
        self.positions: list[TeamPosition] = positions
        self.blockouts: list[Blockout] = blockouts

    def __str__(self) -> str:
        positions_text = "\n".join(f"  - {position}" for position in self.positions) if self.positions else "  - (none)"
        blockouts_text = "\n".join(f"  - {blockout}" for blockout in self.blockouts) if self.blockouts else "  - (none)"
        return (
            f"TeamMember(name={self.name})\n"
            f"  Positions:\n{positions_text}\n"
            f"  Blockouts:\n{blockouts_text}"
        )

class Team:
    def __init__(self, folder_name: str, service_type_name: str, team_name: str, month: int):
        folder_id = get_folder_id(folder_name)
        service_type_id = get_service_type_id(service_type_name, folder_id)
        team_id = get_team_id(team_name, service_type_id)
        team_positions = get_team_positions(team_id)
        team_members_with_names = get_team_members(team_id)
        team_members_with_positions = add_positions_to_team_members(team_id, team_members_with_names, team_positions)
        team_members_with_blockouts = add_blockouts_to_team_members(team_id, team_members_with_positions, month)

        self.team_members: list[TeamMember] = []
        for _, member_data in team_members_with_blockouts.items():
            member = TeamMember(
                name=member_data['name'],
                positions=[
                    TeamPosition(
                        name=position['name'],
                        schedule_preference=position['schedule_preference'],
                        skill_level=0  # Placeholder for skill level
                    ) for position in member_data.get('positions', [])
                ],
                blockouts=[
                    Blockout(
                        start=blockout['start'],
                        end=blockout['end']
                    ) for blockout in member_data.get('blockouts', [])
                ]
            )
            self.team_members.append(member)

    def __str__(self) -> str:
        if not self.team_members:
            return "Team(no members)"

        members_text = "\n\n".join(str(member) for member in self.team_members)
        return f"Team\n{members_text}"

def get_response(url: str) -> dict[str, Any]:
    response = requests.get(
        url, 
        auth=HTTPBasicAuth(PCO_SECRETS['pco_app_id'], PCO_SECRETS['pco_secret']),
    )
    
    if response.status_code != 200:
        raise RuntimeError(f"Error: {response.status_code} - {response.text}")
        
    return response.json()

def get_folder_id(folder_name: str) -> str:
    url = f'https://api.planningcenteronline.com/services/v2/folders' 
    LOG.debug(f'Fetching folders from {url}')    

    folders = get_response(url)
    
    pretty_json = json.dumps(folders["data"], indent=4)
    LOG.debug(f"Found {pretty_json}")

    for f in folders.get('data', []):
        if f['attributes']['name'] == folder_name:
            LOG.info(f"Found folder '{folder_name}' with ID: {f['id']}")
            return f['id']
    
    raise RuntimeError(f"Folder '{folder_name}' not found in Planning Center Online.")

def get_service_type_id(service_type_name: str, folder_id: str) -> str:
    url = f'https://api.planningcenteronline.com/services/v2/folders/{folder_id}?include=service_types' 
    LOG.debug(f'Fetching service types from {url}')

    service_types = get_response(url)

    pretty_json = json.dumps(service_types["included"], indent=4)
    LOG.debug(f"Found {pretty_json}")

    for st in service_types.get('included', []):
        if st['attributes']['name'] == service_type_name:
            LOG.info(f"Found service type '{service_type_name}' with ID: {st['id']}")
            return st['id']
    
    raise RuntimeError(f"Service type '{service_type_name}' not found in Planning Center Online.")

def get_team_id(team_name: str, service_type_id: str) -> str:
    url = f'https://api.planningcenteronline.com/services/v2/service_types/{service_type_id}/teams' 
    LOG.debug(f'Fetching teams from {url}')

    teams = get_response(url)

    pretty_json = json.dumps(teams["data"], indent=4)
    LOG.debug(f"Found {pretty_json}")

    for team in teams.get('data', []):
        if team['attributes']['name'] == team_name:
            LOG.info(f"Found team '{team_name}' with ID: {team['id']}")
            return team['id']
    
    raise RuntimeError(f"Team '{team_name}' not found in Planning Center Online.")

def get_team_members(team_id: str) -> dict[str, Any]:
    url = f'https://api.planningcenteronline.com/services/v2/teams/{team_id}?include=people' 
    LOG.debug(f'Fetching team members from {url}')
    resp = get_response(url)

    pretty_json = json.dumps(resp["included"], indent=4)
    LOG.debug(f"Found {pretty_json}")

    team_members: dict[str, Any]= {}
    for person in resp.get('included', []):
        team_members[person['id']] = {
            'name': person['attributes']['first_name'] + ' ' + person['attributes']['last_name'],
        }
    
    LOG.debug(f"Team member names: {json.dumps(team_members, indent=4)}")
    LOG.info(f"Found {len(team_members)} team members.")
    return team_members

def get_team_positions(team_id: str) -> dict[str, Any]:
    url = f'https://api.planningcenteronline.com/services/v2/teams/{team_id}?include=team_positions'
    LOG.debug(f"Fetching team positions from {url}")
    resp = get_response(url)
    team_positions: dict[str, Any] = {}
    for position in resp.get('included', []):
        team_positions[position['id']] = {
            'name': position['attributes']['name'],
        }
    LOG.debug(f"Team positions: {json.dumps(team_positions, indent=4)}") 
    LOG.info(f"Found {len(team_positions)} team positions.")
    return team_positions
    
def add_positions_to_team_members(team_id: str, team_members: dict[str, Any], team_positions: dict[str, Any]) -> dict[str, Any]:
    url = f'https://api.planningcenteronline.com/services/v2/teams/{team_id}?include=person_team_position_assignments' 
    LOG.debug(f"Fetching person position assignments from {url}")
    resp = get_response(url)
    for assignment in resp.get('included', []):
        person_id = assignment['relationships']['person']['data']['id']
        position_id = assignment['relationships']['team_position']['data']['id']
        if person_id in team_members:
            LOG.debug(f"Assigning position '{team_positions[position_id]['name']}' to person '{team_members[person_id]['name']}'")
            if team_members[person_id].get('positions') is None:
                team_members[person_id]['positions'] = []
            
            team_members[person_id]['positions'].append({
                "name": team_positions[position_id]['name'],
                "schedule_preference": assignment['attributes']['schedule_preference'],
            })
        else:
            raise RuntimeError(f"Person ID '{person_id}' not found in team members while processing position assignments.")

    LOG.debug(f"Team members with positions: {json.dumps(team_members, indent=4)}")
    LOG.info(f"Assigned positions to team members.")

    return team_members

def add_blockouts_to_team_members(team_id: str, team_members: dict[str, Any], month: int) -> dict[str, Any]:
    for person_id in team_members.keys():
        url = f'https://api.planningcenteronline.com/services/v2/people/{person_id}/blockouts?filter=future' 
        LOG.debug(f"Fetching person blockouts from {url}")
        resp = get_response(url)
        for blockout in resp.get('data', []):
            blockout_start = datetime.fromisoformat(blockout['attributes']['starts_at'])
            blockout_end = datetime.fromisoformat(blockout['attributes']['ends_at'])
            if blockout_start.month == month or blockout_end.month == month:
                LOG.debug(f"Adding blockout '{blockout_start}' to person '{team_members[person_id]['name']}'")
                if team_members[person_id].get('blockouts') is None:
                    team_members[person_id]['blockouts'] = []
                team_members[person_id]['blockouts'].append({
                    'start': blockout['attributes']['starts_at'],
                    'end': blockout['attributes']['ends_at']
                })

    LOG.debug(f"Team members with blockouts: {json.dumps(team_members, indent=4)}")
    LOG.info(f"Added blockouts to team members for month '{month}'.")

    return team_members

def get_team(folder_name: str, service_type_name: str, team_name: str, month: int) -> dict[str, Any]:
    folder_id = get_folder_id(folder_name)
    service_type_id = get_service_type_id(service_type_name, folder_id)
    team_id = get_team_id(team_name, service_type_id)
    team_members = get_team_members(team_id)
    team_positions = get_team_positions(team_id)
    team_members_with_positions = add_positions_to_team_members(team_id, team_members, team_positions)
    team_members_with_blockouts = add_blockouts_to_team_members(team_id, team_members_with_positions, month)

    
    return team_members_with_blockouts