import math

from request import request


class Galaxy(object):
	_report = None

	def __init__(self, game_number, cookies):
		self.game_number = game_number
		self.cookies = cookies

	def update_state(self):
		self._report = request('order', order='full_universe_report', game_number=game_number, cookies=cookies)

	@property
	def report(self):
		if not self._report:
			self.update_state()
		return self._report

	def __getattr__(self, attr):
		return self.report[attr]

	@property
	def admin(self):
		return self.players[self.report.admin]

	@property
	def fleets(self):
		# We use a dict {id: object} instead of a list [object] because the "list" is sparse - only visible ones present
		return {fleet_id: Fleet(id, galaxy=self) for fleet_id, fleet_data in self.report.fleets.items()}

	@property
	def game_state(self):
		if self.report.game_over: return 'finished'
		if not self.report.started: return 'not started'
		if self.report.paused: return 'paused'
		return 'running'

	@property
	def now(self):
		return self.report.now / 1000.0 # epoch time

	@property
	def player(self):
		return self.players[self.report.player_uid]

	@property
	def players(self):
		return [Player(player_id, galaxy=self) for player_id in range(len(self.report.players))]

	@property
	def stars(self):
		return [Star(star_id, galaxy=self) for star_id in range(len(self.report.stars))]

	@property
	def start_time(self):
		return self.report.start_time / 1000.0 # epoch time

	@property
	def turn_based(self):
		return self.report.turn_based == 1


class _HasGalaxy(object):
	"""A base class for classes that are contained in a galaxy."""
	def __init__(self, *args, **kwargs):
		"""A common feature of these classes is that, while they would normally be generated
		by a galaxy object, they may be created independently. By giving the nessecary game_number
		and cookies, it fetches a temporary galaxy object in order to get its info.
		For example, if you only cared about Fleet 42, you might use:
			myfleet = Fleet(42, game_number=game_number, cookies=cookies)
		instead of:
			galaxy = Galaxy(game_number, cookies)
			myfleet = galaxy.fleets[42]

		Inheritance note: Once this init is called, the parent galaxy is available as self.galaxy
		"""
		# all this kwargs.pop nonsense is because python2 doesn't allow def f(*args, key=default, ...)
		if 'game_number' in kwargs or 'cookies' in kwargs:
			game_number = kwargs.pop('game_number')
			cookies = kwargs.pop('cookies')
			galaxy = Galaxy(game_number, cookies)
		else:
			galaxy = kwargs.pop('galaxy')

		self.galaxy = galaxy


class _HasData(object):
	"""A base class for classes that have a block of response data they draw information from.
	It assumes this data is stored in self.data by init.
	It defines a getattr to search it, and further, points any names given in self.aliases to other attrs.
	self.aliases should have form: {'key': 'key_to_use_instead'}
	For example, to make self.name return self.n, you would set self.aliases = {'name': 'n'}
	"""
	data = {}
	aliases = {}

	def __getattr__(self, attr):
		if attr in aliases:
			return getattr(self, aliases[attr])
		return self.data[attr]


class Fleet(_HasGalaxy, _HasData):
	aliases = {
		'owner': 'player',
		'name': 'n',
		'ships': 'st',
		'fleet_id': 'uid',
	}

	def __init__(self, fleet_id, **kwargs):
		super(Fleet, self).__init__(**kwargs)
		self.data = self.galaxy.report.fleets[fleet_id]

	@property
	def waypoints(self):
		return [Star(star_id, galaxy=self.galaxy) for star in self.data.p]

	@property
	def player(self):
		return Player(self.data.puid, galaxy=self.galaxy)

	@property
	def x(self): return float(self.data.x)
	@property
	def y(self): return float(self.data.y)
	@property
	def lx(self): return float(self.data.lx)
	@property
	def ly(self): return float(self.data.ly)


class Star(_HasGalaxy, _HasData):
	aliases = {
		'owner': 'player',
		'name': 'n',
		'star_id': 'uid',
		'economy': 'e',
		'carriers': 'c',
		'garrison': 'g',
		'industry': 'i',
		'resources': 'r',
		'natural_resources': 'nr',
		'natural': 'nr',
		'science': 's',
		'ships': 'st',
	}

	def __init__(self, star_id, **kwargs):
		super(Star, self).__init__(**kwargs)
		self.data = self.galaxy.report.stars[star_id]

	@property
	def player(self):
		puid = self.data.puid
		return None if puid == -1 else Player(puid, galaxy=self.galaxy)

	@property
	def visible(self):
		return self.data.v == '1'

	@property
	def x(self): return float(self.data.x)
	@property
	def y(self): return float(self.data.y)

	# TODO how do we know if a fleet is on a star? does data.st include orbiting carriers? (prob not)
	# we should add a total ships including carriers.

	def distance(self, other, as_level=False):
		"""Return distance to other star.
		If as_level=True, convert the result into the minimum range level required.
		"""
		dist = math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
		if not as_level: return dist
		level = math.ceil(dist) - 3
		if level < 1: level = 1
		return level
