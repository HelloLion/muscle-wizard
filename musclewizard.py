import libtcodpy as libtcod
import math
import textwrap

SCREEN_WIDTH = 100
SCREEN_HEIGHT = 80

MAP_WIDTH = 100
MAP_HEIGHT = 73

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

MAX_ROOM_MONSTERS = 3

BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

LIMIT_FPS = 20

color_dark_wall = libtcod.Color(31, 31, 31)
color_light_wall = libtcod.Color(127, 127, 127)
color_dark_ground = libtcod.Color(31, 24, 15)
color_light_ground = libtcod.Color(127, 101, 63)

class Tile:
	#a tile of the map and its properties
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked
		
		self.explored = False
		
		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight
		
		
class Rect:
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h
		
	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)
		
	def intersect(self, other):
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
			self.y1 <= other.y2 and self.y2 >= other.y1)
		
class Object:
	#this is a generic object: the player, a monster, an item, the stairs...
	#it's always represented by a character on screen.
	def __init__(self, x, y, char, name, color, blocks=False, fighter=None, ai=None):
		self.x = x
		self.y = y
		self.char = char
		self.name = name
		self.color = color
		self.blocks = blocks
		self.fighter = fighter
		if self.fighter: #let the fighter component know who owns it
			self.fighter.owner = self
		
		self.ai = ai
		if self.ai: #let the ai component know who owns it
			self.ai.owner = self
	
	def move(self, dx, dy):
		#move by the given amount
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy
			
	def move_towards(self, target_x, target_y):
		#vector from this object to the target, and distance
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)
		
		#normalize it to length 1 (preserving direction), then round it and
		#convert to integer so the movement is restricted to the map grid
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)
		
	def distance_to(self, other):
		#return the distance to another object
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)
		
	def send_to_back(self):
		#make this object be drawn first
		global objects
		objects.remove(self)
		objects.insert(0, self)
	
	def draw(self):
		#set the color and then draw the character that represents this object at its position
		if libtcod.map_is_in_fov(fov_map, self.x, self.y):
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
		
	def clear(self):
		#erase the character that represents this object
		libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
	

		

		
class Fighter:
	def __init__(self, hp, defense, power, death_function=None):
		self.max_hp = hp
		self.hp = hp
		self.defense = defense
		self.power = power
		self.death_function = death_function
			
	def attack(self, target):
		#a simple formula for attack damage with some chance 
		luck = libtcod.random_get_int(0, -3, 3)
			
		basedmg = self.power - target.fighter.defense
		damage = basedmg + luck
		
		
		if damage > 0:
			#make the target take some damage
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' health.', libtcod.dark_red)
			target.fighter.take_damage(damage)
		else:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!', libtcod.light_green)
			
	def take_damage(self, damage):
		#apply damage if possible
		if damage > 0:
			self.hp -= damage
			
			#check for death.
			if self.hp <= 0:
				function = self.death_function
				if function is not None:
					function(self.owner)
		


class BasicMonster:
	def take_turn(self):
	#a basic monster takes its turn. If you can see it, it can see you
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
				
			#move towards player if far away
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)
					
			#close enough, attack! (if the player is still alive)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)
				

def is_blocked(x, y):
	if map[x][y].blocked:
		return True
	
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True
	
	return False
		
def create_room(room):
	global map
	
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False
			
def create_h_tunnel(x1, x2, y):
	global map
	
	for x in range(min(x1, x2), max(x1, x2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
		
def create_v_tunnel(y1, y2, x):
	global map
	
	for y in range(min(y1, y2), max(y1, y2) +1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
		
		
		
def make_map():
	global map, player
	
	#fill map with "blooked" tiles
	map = [[ Tile(True)
		for y in range(MAP_HEIGHT) ]
			for x in range(MAP_WIDTH) ]
			
	rooms = []
	num_rooms = 0
	
	for r in range(MAX_ROOMS):
		w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		
		x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
		y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
		
		new_room = Rect(x, y, w, h)
		
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break
				
		if not failed:
			create_room(new_room)
			
			place_objects(new_room)
			
			(new_x, new_y) = new_room.center()
			
			if num_rooms == 0:
				player.x = new_x
				player.y = new_y
				
			else:
				(prev_x, prev_y) = rooms[num_rooms-1].center()
				
				if libtcod.random_get_int(0, 0, 1) == 1:
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
					
				else:
					create_v_tunnel(prev_y, new_y, prev_x)
					create_h_tunnel(prev_x, new_x, new_y)
					
			rooms.append(new_room)
			num_rooms += 1
			
			
def place_objects(room):
	num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)
	
	for i in range(num_monsters):
		x = libtcod.random_get_int(0, room.x1, room.x2)
		y = libtcod.random_get_int(0, room.y1, room.y2)
		
		if not is_blocked(x, y):
			choice = libtcod.random_get_int(0, 0, 100)
			if choice < 20:
				#malicious robot
				fighter_component = Fighter(hp=15, defense=1, power =3, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 'R', 'malicious robot', libtcod.lightest_grey, blocks=True, ai=ai_component, fighter=fighter_component)
			elif choice < 40 and choice >= 20:
				#small dinosaur
				fighter_component = Fighter(hp=13, defense=1, power =4, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 'd', 'small dinosaur', libtcod.darkest_green, blocks=True, ai=ai_component, fighter=fighter_component)
			elif choice < 60 and choice >= 40:
				#floating brain
				fighter_component = Fighter(hp=8, defense=0, power =1, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 'b', 'floating brain', libtcod.light_pink, blocks=True, ai=ai_component, fighter=fighter_component)
			else:
				#imp
				fighter_component = Fighter(hp=10, defense=0, power =3, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 'i', 'imp', libtcod.light_red, blocks=True, ai=ai_component, fighter=fighter_component)
			
			objects.append(monster)


def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	#render a bar (HP, experience, etc)
	bar_width = int(float(value) / maximum * total_width)
	
	#render background
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
	
	#now render the bar on top
	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
		
	#sexy text
	libtcod.console_set_default_foreground(panel, libtcod.darkest_grey)
	libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER, name + ': ' + str(value) + '/' +str(maximum))

def message(new_msg, color = libtcod.white):
	#split msg if necessary
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
	
	for line in new_msg_lines:
		#if the buffer is full, remove the first line
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]
			
		#add the new line as a tuple
		game_msgs.append( (line, color) )

	
def render_all():
	global fov_map, color_dark_wall, color_light_wall
	global color_dark_ground, color_light_ground
	global fov_recompute
	
	if fov_recompute:
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		
		for y in range(MAP_HEIGHT):
			for x in range(MAP_WIDTH):
				visible = libtcod.map_is_in_fov(fov_map, x, y)
				wall = map[x][y].block_sight
				if not visible:
					if map[x][y].explored:
						if wall:
							libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
						else:
							libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
				else:
					if wall:
						libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
					else:
						libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
					map[x][y].explored = True
				
	for object in objects:
		if object != player:
			object.draw()
	player.draw()
		
	libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)
	
	#prepare to render GUI panel
	libtcod.console_set_default_background(panel, libtcod.darkest_grey)
	libtcod.console_clear(panel)
	
	#print sum messages son but do it 1 line at a time
	y = 1
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1
	
	#statz
	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darkest_crimson)
	
	#display names of objects under mouse
	libtcod.console_set_default_foreground(panel, libtcod.light_gray)
	libtcod.console_print_ex(panel, MSG_X + 2, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
	
	#blit the contents of "panel" to the root console
	libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)
	
def player_move_or_attack(dx, dy):
	global fov_recompute
	
	#the coordinates the player is moving to/attacking
	x = player.x + dx
	y = player.y + dy
	
	target = None
	for object in objects:
		if object.fighter and object.x == x and object.y == y:
			target = object
			break
	
	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(dx, dy)
		fov_recompute = True

def handle_keys():
	global key;
	

	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
 
	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit' #exit game
 
	if game_state == 'playing':
		#movement keys
		if key.vk == libtcod.KEY_UP:
			player_move_or_attack(0, -1)
	 
		elif key.vk == libtcod.KEY_DOWN:
			player_move_or_attack(0, 1)
	 
		elif key.vk == libtcod.KEY_LEFT:
			player_move_or_attack(-1, 0)
	 
		elif key.vk == libtcod.KEY_RIGHT:
			player_move_or_attack(1, 0)
			
		else:
			return 'didnt-take-turn'
			
def get_names_under_mouse():
	global mouse
	
	#return a string with the names of all objects under the mouse
	(x, y) = (mouse.cx, mouse.cy)
	
	#create a list with the names of all objects at the mouse's coordinates and in FOV
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
		
	names = ', '.join(names)
	return names.capitalize()

			
def player_death(player):
	#oh no!
	global game_state
	message('You am no true Muscle Wizard!', libtcod.light_crimson)
	game_state = 'dead'
	
	#corpsify
	player.char = '%'
	player.color = libtcod.dark_red


def monster_death(monster):
	#transforms it into a corpse!
	message('You have overcome ' + monster.name + '!', libtcod.orange)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()

	
	
#main loop all up in dis
#u don't even kno
#this code be fresh and poppin
	
libtcod.console_set_custom_font('prestige12x12_gs_tc.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)

libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'MUSCLE WIZARD', False)
libtcod.sys_set_fps(LIMIT_FPS)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)

panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

#create player object
fighter_component = Fighter(hp=30, defense=2, power=6, death_function=player_death)
player = Object(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component)

#list of objects starting with player
objects = [player]

make_map()

fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in range(MAP_HEIGHT):
	for x in range(MAP_WIDTH):
		libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
		
fov_recompute = True
game_state = 'playing'
player_action = None

#create list of game messages, starts empty
game_msgs = []

#a warm welcoming message!
message('What ho, Muscle Wizard! Have thou what it takes to best mine dungeon?', libtcod.light_blue)

mouse = libtcod.Mouse()
key = libtcod.Key()

while not libtcod.console_is_window_closed():

	libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)

	render_all()

	libtcod.console_flush()
	
	#erase all objects at their old locations, before they move
	for object in objects:
		object.clear()

	
	#handle keys and exit game if needed
	player_action = handle_keys()
	if player_action == 'exit':
		break
	
	if game_state == 'playing' and player_action != 'didnt-take-turn':
		for object in objects:
			if object.ai:
				object.ai.take_turn()
	
