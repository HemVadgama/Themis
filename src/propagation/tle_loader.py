from skyfield.api import Loader
from skyfield.iokit import parse_tle_file

def load_satellites(group='active'):
    load = Loader('data')

    max_days = 7.0
    name = group+'.tle'

    base = 'https://celestrak.org/NORAD/elements/gp.php'
    url = base + '?GROUP=' + group + '&FORMAT=tle'

    if not load.exists(name) or load.days_old(name) >= max_days:
        load.download(url, filename=name)

    ts = load.timescale()

    with load.open('active.tle') as f:
        satellites = list(parse_tle_file(f, ts))

    return satellites

def find_satellite_by_name(satellites, name):
    pass