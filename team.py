import logging
from datetime import datetime
from pco import get_team
from sheets import get_team_health_sheet

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
        team_health_sheet = get_team_health_sheet()
        team_members_json = get_team(folder_name, service_type_name, team_name, month)

        logging.info(f"Formatting team members from json data")
        logging.debug(f"Team members JSON data: {team_members_json}")
        self.team_members: list[TeamMember] = []
        for _, member_data in team_members_json.items():
            for position in member_data.get('positions', []):
                def first_last(name: str) -> str:
                    parts = name.split()
                    if len(parts) < 2:
                        return name.strip().lower()
                    return f"{parts[0]} {parts[-1]}".lower()

                member_entry = next((item for item in team_health_sheet.get_all_records() if first_last(str(item['Name'])) == first_last(member_data['name'])), None)
                if member_entry:
                    skill_level = member_entry.get('Hands', 0)
                else:
                    logging.warning(f"Member '{member_data['name']}' with position '{position['name']}' not found in team health sheet. Defaulting skill level to 0.")
                    skill_level = 0
                position['skill_level'] = skill_level
            member = TeamMember(
                name=member_data['name'],
                positions=[
                    TeamPosition(
                        name=position['name'],
                        schedule_preference=position['schedule_preference'],
                        skill_level=position['skill_level']
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

