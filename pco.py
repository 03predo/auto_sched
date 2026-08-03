import json
import logging
import requests
from datetime import datetime
from typing import Any
from requests.auth import HTTPBasicAuth

PCO_SECRETS = json.load(open('secrets/pco.json', 'rb'))
LOG = logging.getLogger(__name__)

def _fetch_page(url: str) -> dict[str, Any]:
    response = requests.get(
        url,
        auth=HTTPBasicAuth(PCO_SECRETS['pco_app_id'], PCO_SECRETS['pco_secret']),
    )

    if response.status_code != 200:
        raise RuntimeError(f"Error: {response.status_code} - {response.text}")

    return response.json()

def get_response(url: str) -> dict[str, Any]:
    """Fetch a URL from the PCO API, following pagination if the response
    is a list (i.e. `data` is a list rather than a single object).

    PCO list endpoints default to 25 items per page and expose the next
    page via `links.next`. Single-resource endpoints (e.g. a request for
    one folder) return `data` as a dict and are not paginated, so they're
    returned as-is.
    """
    first_page = _fetch_page(url)

    if not isinstance(first_page.get('data'), list):
        # Single-resource response; nothing to paginate.
        return first_page

    all_data: list[Any] = list(first_page['data'])
    included_by_key: dict[tuple[str, str], Any] = {
        (item['type'], item['id']): item for item in first_page.get('included', [])
    }

    next_url = first_page.get('links', {}).get('next')
    page_count = 1
    while next_url:
        page_count += 1
        LOG.debug(f"Fetching page {page_count} from {next_url}")
        page = _fetch_page(next_url)

        all_data.extend(page.get('data', []))
        for item in page.get('included', []):
            included_by_key[(item['type'], item['id'])] = item

        next_url = page.get('links', {}).get('next')

    result = dict(first_page)
    result['data'] = all_data
    if included_by_key:
        result['included'] = list(included_by_key.values())
    # A fully-paginated response has no more "next" page.
    result['links'] = {k: v for k, v in first_page.get('links', {}).items() if k != 'next'}

    if page_count > 1:
        LOG.info(f"Paginated response: fetched {page_count} pages, {len(all_data)} total items.")

    return result

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
            
            schedule_preference = assignment['attributes']['schedule_preference']
            if schedule_preference == "Once a month":
                schedule_preference = 1
            elif schedule_preference == "Twice a month":
                schedule_preference = 2
            elif schedule_preference == "Three times a month":
                schedule_preference = 3
            elif schedule_preference == "As often as needed":
                schedule_preference = 5
            else:
                raise RuntimeError(f"Unknown schedule preference '{schedule_preference}' for person '{team_members[person_id]['name']}' and position '{team_positions[position_id]['name']}'.")
            team_members[person_id]['positions'].append({
                "name": team_positions[position_id]['name'],
                "schedule_preference": schedule_preference,
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