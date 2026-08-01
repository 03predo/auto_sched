
import logging

from team import Team

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
LOG = logging.getLogger(__name__)

if __name__ == "__main__":
    FOLDER_NAME = 'Base - Waterloo University District'
    SERVICE_TYPE_NAME = '[PM] Sunday Services - University'
    TEAM_NAME = 'Worship - Instrumentalists'
    MONTH = 8 # August

    instrumentalists= Team(FOLDER_NAME, SERVICE_TYPE_NAME, TEAM_NAME, MONTH)

    logging.info(f"Instrumentalists: {instrumentalists}")