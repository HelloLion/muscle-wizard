import libtcodpy as libtcod
import math
import textwrap
import shelve

SCREEN_WIDTH = 100
SCREEN_HEIGHT = 75

MAP_WIDTH = 100
MAP_HEIGHT = 68

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

MAX_ROOM_MONSTERS = 3
MAX_ROOM_ITEMS = 2

BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

INVENTORY_WIDTH = 50

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

LIMIT_FPS = 20

HEAL_AMOUNT = libtcod.random_get_int(0, 3, 6)
CORRUPT_RANGE = 6
CORRUPT_DAMAGE = libtcod.random_get_int(0, 10, 20)
GLITCH_NUM_TURNS = libtcod.random_get_int(0, 7, 15)
GLITCH_RANGE = 8
GRAV_RADIUS = libtcod.random_get_int(0, 2, 4)
GRAV_DAMAGE = libtcod.random_get_int(0, 9, 15)

color_dark_wall = libtcod.Color(31, 31, 31)
color_light_wall = libtcod.Color(95, 95, 95)
color_dark_ground = libtcod.Color(159, 159, 159)
color_light_ground = libtcod.Color(127, 127, 127)

LG = False
LW = False
DG = False
DW = False

distortion = 0
max_dist = 10000


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
	def __init__(self, x, y, char, name, color, blocks=False, caster=None, fighter=None, ai=None, item=None):
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
		
		self.item = item
		if self.item:
			self.item.owner = self
			
		self.caster = caster
		if self.caster:
			self.caster.owner = self
		
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
		
	def distance(self, x, y):
		#return the distance to some coordinates
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
		
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
	


class Item:
	def __init__(self, use_function=None, multi_use=False):
		self.use_function = use_function
		self.multi_use = multi_use
		
	def use(self):
		global distortion
		#just call the use_function
		if self.use_function is None:
			message('The ' + self.owner.name + ' cannot be used. Perhaps it has another purpose?')
		else:
			if self.use_function() != 'cancelled':
				if self.multi_use is False:
					inventory.remove(self.owner) #destroy after use unless it is canceled or is able to be used more than once
					distortion = distortion + 1
				
	#an item that can be picked up and used.
	def pick_up(self):
		#add to the player's inventory and remove from the map
		if len(inventory) >= 26:
			sarcasm = libtcod.random_get_int(0, 0, 100)
			if sarcasm <= 20: 
				message('You cannot carry any more items, puny man.', libtcod.dark_lime)
			elif sarcasm <= 40 and sarcasm > 20: 
				message('Do you really need ' + self.owner.name + '? Cause if you do, you better get rid of some of this other junk.', libtcod.dark_lime)
			elif sarcasm <= 60 and sarcasm > 40: 
				message('Hoarding is not healthy. You must shed some of your itmes before you can add this one to your horrid collection.', libtcod.dark_lime)
			elif sarcasm <= 80 and sarcasm > 60: 
				message('You must clear some space in your inventory before you can pick up ' + self.owner.name + '. Perhaps you should experiment with some magic potions?', libtcod.dark_lime)
			elif sarcasm <= 100 and sarcasm > 80: 
				message('You simply cannot carry anything more. It would be impossible. Even if you were to have the strength of ten men, you could not best the mysterious limit of 26 that plagues all adventurers.', libtcod.dark_lime)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			sarcasm = libtcod.random_get_int(0, 0, 100)
			if sarcasm <= 20: 
				message('You got yourself a shiny, new ' + self.owner.name + '. (Okay, maybe it was a little used.)', libtcod.lime)
			elif sarcasm <= 40 and sarcasm > 20: 
				message('I hope you know what you are doing by picking up ' + self.owner.name + '.', libtcod.lime)
			elif sarcasm <= 60 and sarcasm > 40: 
				message('You now have a ' + self.owner.name + '. Hooray greed!', libtcod.lime)
			elif sarcasm <= 80 and sarcasm > 60: 
				message('Pretty sweet ' + self.owner.name + ' you got there.', libtcod.lime)
			elif sarcasm <= 100 and sarcasm > 80: 
				message('Oh good, you finally got your own ' + self.owner.name + '. Now you can stop borrowing mine.', libtcod.lime)
				
	def drop(self):
		#add to the map and remove from player's inventory
		objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.x = player.x
		self.owner.y = player.y
		message('You dropped a ' + self.owner.name + '.', libtcod.yellow)
				
class Caster:
	def __init__(self, quantum, alchemy):
		self.max_quantum = quantum
		self.quantum = quantum
		self.datamancy = datamancy
		
class Fighter:
	def __init__(self, hp, defense, power, energy, death_function=None):
		self.max_hp = hp
		self.hp = hp
		self.defense = defense
		self.power = power
		self.max_energy = energy
		self.energy = energy
		self.death_function = death_function
			
	def attack(self, target):
		#a simple formula for attack damage with some chance 
		luck = libtcod.random_get_int(0, -3, 3)
			
		basedmg = self.power - target.fighter.defense
		damage = basedmg + luck
		
		
		if damage > 0:
			#make the target take some damage
			if self.death_function is player_death:
				message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' health.', libtcod.light_red)
			else:
				message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' health.', libtcod.dark_red)
			target.fighter.take_damage(damage)
			
		else:
			if self.death_function is player_death:
				message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!', libtcod.dark_green)
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
					
	def heal(self, amount):
		#heal by the amount without going over the maximum
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp
		


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
				
class ConfusedMonster:
	#AI for a confused monster.
	def __init__(self, old_ai, num_turns=GLITCH_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns
		
	def take_turn(self):
		monster = self.owner
		if self.num_turns > 0: #check if still confused
			luck = libtcod.random_get_int(0, 0, 100)
			if luck < 80:
				#move in a random direction
				self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
				message('The ' + monster.name + ' bumbles around spitting out binary nonsense.', libtcod.light_grey)
			else:
				monster.fighter.take_damage(libtcod.random_get_int(0, 1, 4))
				message('The ' + monster.name + ' damages itself while spitting out binary nonsense.', libtcod.light_red)
			self.num_turns -= 1
			
		else: #restore the previous AI
			self.owner.ai = self.old_ai
			message('The ' + self.owner.name + ' has repaired its glitched drivers and is acting normally again', libtcod.light_orange)

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
			
def create_circular_room(room):
	global map
	#center of circle
	cx = (room.x1 + room.x2) / 2
	cy = (room.y1 + room.y2) / 2

	#radius of circle: make it fit nicely inside the room, by making the
	#radius be half the width or height (whichever is smaller)
	width = room.x2 - room.x1
	height = room.y2 - room.y1
	r = min(width, height) / 2

	#go through the tiles in the circle and make them passable
	for x in range(room.x1, room.x2 + 1):
		for y in range(room.y1, room.y2 + 1):
			if math.sqrt((x - cx) ** 2 + (y - cy) ** 2) <= r:
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
	global map, player, objects, stairs
	
	objects = [player]
	
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
			luck = libtcod.random_get_int(0, 0, 100)
			if luck > 70:
				create_circular_room(new_room)
			else:
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
	
	#create stairs at the center of the last room created
	stairs = Object(new_x, new_y, '<', 'stairs', libtcod.white)
	objects.append(stairs)
	stairs.send_to_back()
			
def place_objects(room):
	num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)
	
	for i in range(num_monsters):
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		if not is_blocked(x, y):
			choice = libtcod.random_get_int(0, 0, 100)
			if choice < 20:
				#malfunctioning service bot
				fighter_component = Fighter(hp=15, defense=1, power =3, energy=10, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 'r', 'malfunctioning service robot', libtcod.lightest_grey, blocks=True, ai=ai_component, fighter=fighter_component)
			elif choice < 40 and choice >= 20:
				#basic security robot
				fighter_component = Fighter(hp=13, defense=1, power =4, energy=10, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 's', 'security robot', libtcod.darkest_green, blocks=True, ai=ai_component, fighter=fighter_component)
			elif choice < 60 and choice >= 40:
				#brain in a jar
				fighter_component = Fighter(hp=8, defense=0, power =1, energy=10, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 'b', 'brain in a jar', libtcod.light_pink, blocks=True, ai=ai_component, fighter=fighter_component)
			else:
				#scrap metal
				fighter_component = Fighter(hp=10, defense=0, power =3, energy=10, death_function=monster_death)
				ai_component = BasicMonster()
				monster = Object(x, y, 'm', 'sentient scrap metal', libtcod.light_grey, blocks=True, ai=ai_component, fighter=fighter_component)
			
			objects.append(monster)
			
	num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)
	
	for i in range(num_items):
		#choose random spot for this item
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		#only place it if the tile is not blocked
		if not is_blocked(x, y):
			dice = libtcod.random_get_int(0, 0, 1000)
			if dice < 700:
				#create an oil can
				item_component = Item(use_function=cast_heal)
				item = Object(x, y, '!', 'oil can', libtcod.black, item=item_component)
			elif dice < 700+100:
				item_component = Item(use_function=cast_glitch)
				item = Object (x, y, '#', 'glitch script', libtcod.light_green, item=item_component)
			elif dice < 700+100+100:
				item_component = Item(use_function=cast_gravitywell)
				item = Object (x, y, ',', 'unstable anti-matter', libtcod.black, item=item_component)
			else:
				#create a database corrupter
				item_component = Item(use_function=cast_corrupt)
				item = Object(x, y, '#', 'database corrupt script', libtcod.light_green, item=item_component)
			
			objects.append(item)
			item.send_to_back() #items appear below other objects


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
	global strobe, first_time, distortion, max_dist
	global DG, DW, LG, LW
	
	if distortion > max_dist:
		distortion = max_dist
	
	if fov_recompute:
		if first_time:
			strobe = 10
			first_time = False

			distortion = 0
		else:
			dice = libtcod.random_get_int(0, 1, max_dist)
			if dice <= distortion:
				strobe = libtcod.random_get_int(0, 1, 10)
			else:
				strobe = 10
	
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		
		for y in range(MAP_HEIGHT):
			for x in range(MAP_WIDTH):
				visible = libtcod.map_is_in_fov(fov_map, x, y)
				wall = map[x][y].block_sight
				if not visible:
					if map[x][y].explored:
						if wall:
						
							if strobe == 1:
								dice = libtcod.random_get_int(0, 1, max_dist)
								if dice <= distortion:
									luck = libtcod.random_get_int(0, 1, 5)
									if luck == 1:
										libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
									elif luck == 2:
										libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
									elif luck == 3:
										libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
									elif luck == 4:
										libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
									else:
										libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.darker_green, libtcod.BKGND_SET)
									
							elif strobe == 2:
								dice = libtcod.random_get_int(0, 1, max_dist)
								if dice <= distortion:
									luck = libtcod.random_get_int(0, 1, 5)
									if luck == 1:
										libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
									elif luck == 2:
										libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
									elif luck == 3:
										libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
									elif luck == 4:
										libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
									else:
										libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.darker_blue, libtcod.BKGND_SET)
									
							elif strobe == 3:
								dice = libtcod.random_get_int(0, 1, max_dist)
								if dice <= distortion:
									luck = libtcod.random_get_int(0, 1, 5)
									if luck == 1:
										libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
									elif luck == 2:
										libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
									elif luck == 3:
										libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
									elif luck == 4:
										libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
									else:
										libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.darker_flame, libtcod.BKGND_SET)
								
							elif strobe == 4:
								dice = libtcod.random_get_int(0, 1, max_dist)
								if dice <= distortion:
									luck = libtcod.random_get_int(0, 1, 5)
									if luck == 1:
										libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
									elif luck == 2:
										libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
									elif luck == 3:
										libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
									elif luck == 4:
										libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
									else:
										libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.darker_pink, libtcod.BKGND_SET)
								
							else:
								dice = libtcod.random_get_int(0, 1, max_dist)
								if dice <= distortion and DW is False:
									luck = libtcod.random_get_int(0, 1, 5)
									if luck == 1:
										libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
									elif luck == 2:
										libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
									elif luck == 3:
										libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
									elif luck == 4:
										libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
									else:
										libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
									DW = True
								else:
									libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
									DW = False
						else:
							if strobe == 1:
								dice = libtcod.random_get_int(0, 1, max_dist)
								if dice <= distortion:
									luck = libtcod.random_get_int(0, 1, 5)
									if luck == 1:
										libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
									elif luck == 2:
										libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
									elif luck == 3:
										libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
									elif luck == 4:
										libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
									else:
										libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.dark_green, libtcod.BKGND_SET)
								
							elif strobe == 2:
								dice = libtcod.random_get_int(0, 1, max_dist)
								if dice <= distortion:
									luck = libtcod.random_get_int(0, 1, 5)
									if luck == 1:
										libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
									elif luck == 2:
										libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
									elif luck == 3:
										libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
									elif luck == 4:
										libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
									else:
										libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.dark_blue, libtcod.BKGND_SET)
								
							elif strobe == 3:
								dice = libtcod.random_get_int(0, 1, max_dist)
								if dice <= distortion:
									luck = libtcod.random_get_int(0, 1, 5)
									if luck == 1:
										libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
									elif luck == 2:
										libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
									elif luck == 3:
										libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
									elif luck == 4:
										libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
									else:
										libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.dark_flame, libtcod.BKGND_SET)
								
							elif strobe == 4:
								dice = libtcod.random_get_int(0, 1, max_dist)
								if dice <= distortion:
									luck = libtcod.random_get_int(0, 1, 5)
									if luck == 1:
										libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
									elif luck == 2:
										libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
									elif luck == 3:
										libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
									elif luck == 4:
										libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
									else:
										libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.dark_pink, libtcod.BKGND_SET)
								
							else:
								dice = libtcod.random_get_int(0, 1, max_dist)
								if dice <= distortion and DG is False:
									luck = libtcod.random_get_int(0, 1, 5)
									if luck == 1:
										libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
									elif luck == 2:
										libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
									elif luck == 3:
										libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
									elif luck == 4:
										libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
									else:
										libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
									DG = True
								else:
									libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
									DG = False
								
				else:
					if wall:
						if strobe == 1:
							dice = libtcod.random_get_int(0, 1, max_dist)
							if dice <= distortion:
								luck = libtcod.random_get_int(0, 1, 10)
								if luck == 1:
									libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
								elif luck == 2:
									libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
								elif luck == 3:
									libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
								elif luck == 4:
									libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
								elif luck == 5:
									libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
							else:
								libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
							
						elif strobe == 2:
							dice = libtcod.random_get_int(0, 1, max_dist)
							if dice <= distortion:
								luck = libtcod.random_get_int(0, 1, 10)
								if luck == 1:
									libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
								elif luck == 2:
									libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
								elif luck == 3:
									libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
								elif luck == 4:
									libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
								elif luck == 5:
									libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
							else:
								libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
							
						elif strobe == 3:
							dice = libtcod.random_get_int(0, 1, max_dist)
							if dice <= distortion:
								luck = libtcod.random_get_int(0, 1, 10)
								if luck == 1:
									libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
								elif luck == 2:
									libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
								elif luck == 3:
									libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								elif luck == 4:
									libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
								elif luck == 5:
									libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
							else:
								libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
							
						elif strobe == 4:
							dice = libtcod.random_get_int(0, 1, max_dist)
							if dice <= distortion:
								luck = libtcod.random_get_int(0, 1, 10)
								if luck == 1:
									libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
								elif luck == 2:
									libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								elif luck == 3:
									libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
								elif luck == 4:
									libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
								elif luck == 5:
									libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
							else:
								libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
							
						else:
							dice = libtcod.random_get_int(0, 1, max_dist)
							if dice <= distortion and LW is False:
								luck = libtcod.random_get_int(0, 1, 10)
								if luck == 1:
									libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
								elif luck == 2:
									libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
								elif luck == 3:
									libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
								elif luck == 4:
									libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								elif luck == 5:
									libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
								LW = True
							else:
								libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
								LW = False
							
					else:
						if strobe == 1:
							dice = libtcod.random_get_int(0, 1, max_dist)
							if dice <= distortion:
								luck = libtcod.random_get_int(0, 1, 10)
								if luck == 1:
									libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
								elif luck == 2:
									libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
								elif luck == 3:
									libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
								elif luck == 4:
									libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
								elif luck == 5:
									libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.light_green, libtcod.BKGND_SET)
							else:
								libtcod.console_set_char_background(con, x, y, libtcod.light_green, libtcod.BKGND_SET)
							
						elif strobe == 2:
							dice = libtcod.random_get_int(0, 1, max_dist)
							if dice <= distortion:
								luck = libtcod.random_get_int(0, 1, 10)
								if luck == 1:
									libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
								elif luck == 2:
									libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
								elif luck == 3:
									libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
								elif luck == 4:
									libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
								elif luck == 5:
									libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.light_blue, libtcod.BKGND_SET)
							else:
								libtcod.console_set_char_background(con, x, y, libtcod.light_blue, libtcod.BKGND_SET)
							
						elif strobe == 3:
							dice = libtcod.random_get_int(0, 1, max_dist)
							if dice <= distortion:
								luck = libtcod.random_get_int(0, 1, 10)
								if luck == 1:
									libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
								elif luck == 2:
									libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
								elif luck == 3:
									libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								elif luck == 4:
									libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
								elif luck == 5:
									libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.light_flame, libtcod.BKGND_SET)
							else:
								libtcod.console_set_char_background(con, x, y, libtcod.light_flame, libtcod.BKGND_SET)
							
						elif strobe == 4:
							dice = libtcod.random_get_int(0, 1, max_dist)
							if dice <= distortion:
								luck = libtcod.random_get_int(0, 1, 10)
								if luck == 1:
									libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
								elif luck == 2:
									libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								elif luck == 3:
									libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
								elif luck == 4:
									libtcod.console_set_char_background(con, x, y, libtcod.grey, libtcod.BKGND_SET)
								elif luck == 5:
									libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, libtcod.light_pink, libtcod.BKGND_SET)
							else:
								libtcod.console_set_char_background(con, x, y, libtcod.light_pink, libtcod.BKGND_SET)
							
						else:
							dice = libtcod.random_get_int(0, 1, max_dist)
							if dice <= distortion and LG is False:
								luck = libtcod.random_get_int(0, 1, 10)
								if luck == 1:
									libtcod.console_set_char_background(con, x, y, libtcod.yellow, libtcod.BKGND_SET)
								elif luck == 2:
									libtcod.console_set_char_background(con, x, y, libtcod.pink, libtcod.BKGND_SET)
								elif luck == 3:
									libtcod.console_set_char_background(con, x, y, libtcod.flame, libtcod.BKGND_SET)
								elif luck == 4:
									libtcod.console_set_char_background(con, x, y, libtcod.green, libtcod.BKGND_SET)
								elif luck == 5:
									libtcod.console_set_char_background(con, x, y, libtcod.blue, libtcod.BKGND_SET)
								else:
									libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
								LG = True
							else:
								libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
								LG = False
							
					map[x][y].explored = True
				
	for object in objects:
		if object != player:
			object.draw()
	player.draw()
		
	libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)
	
	#prepare to render GUI panel
	libtcod.console_set_default_background(panel, libtcod.grey)
	libtcod.console_clear(panel)
	
	#print sum messages son but do it 1 line at a time
	y = 1
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1
	
	#statz
	render_bar(1, 1, BAR_WIDTH, 'HEALTH', player.fighter.hp, player.fighter.max_hp, libtcod.light_sky, libtcod.darkest_green)
	render_bar(1, 5, BAR_WIDTH, 'DISTORT', distortion, max_dist, libtcod.cyan, libtcod.light_pink)
	
	libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'CURRENT FLOOR: ' + str(dungeon_level))
	
	
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
		fov_recompute = True
	else:
		player.move(dx, dy)
		fov_recompute = True

def menu(header, options, width):
	if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')
	
	#calculate total height for the header (after auto-wrap) and one line per option
	header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == '':
		header_height = 0
	height = len(options) + header_height
	
	#create an off-screen console that represent's the menu's window
	window = libtcod.console_new(width, height)
	
	#print the header, with auto-wrap
	libtcod.console_set_default_foreground(window, libtcod.lightest_amber)
	libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
	
	#print all the options
	y = header_height
	letter_index = ord('a')
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
		y += 1
		letter_index += 1
		
	#blit the contents of "window" to the root console
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 0.9, 0.6)
	
	#present the root console to the player and wait for a key-press
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)
	
	#convert ASCII code to an index
	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None
	

def msgbox(text, width=50):
	menu(text, [], width) #use menu() as a sort of "message box"
	

def inventory_menu(header):
	#show a menu with each item of the inventory
	if len(inventory) == 0:
		options = ['...']
		sarcasm = libtcod.random_get_int(0, 0, 100)
		if sarcasm <= 20: 
			message('You are free from the burden of attachment as your inventory is empty', libtcod.dark_lime)
		elif sarcasm <= 40 and sarcasm > 20: 
			message('Are you sure you know how to loot a dungeon? Because right now you have nothing to show for it.', libtcod.dark_lime)
		elif sarcasm <= 60 and sarcasm > 40: 
			message('Your inventory could not be more empty than this.', libtcod.dark_lime)
		elif sarcasm <= 80 and sarcasm > 60: 
			message('The only things in your inventory are some broken dreams.', libtcod.dark_lime)
		elif sarcasm <= 100 and sarcasm > 80: 
			message('I hope you were not counting on finding something useful here, because your inventory is empty.', libtcod.dark_lime)
		
	else:
		options = [item.name for item in inventory]
	
	index = menu(header, options, INVENTORY_WIDTH)

	#if item was chosen, return it
	if index is None or len(inventory) == 0: return None
	return inventory[index].item	

		
def handle_keys():
	global key;
	

	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
 
	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit' #exit game
 
	if game_state == 'playing':
		#movement keys
		if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
			player_move_or_attack(0, -1)
	 
		elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
			player_move_or_attack(0, 1)
	 
		elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
			player_move_or_attack(-1, 0)
	 
		elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
			player_move_or_attack(1, 0)
		
		elif key.vk == libtcod.KEY_KP7:
			player_move_or_attack(-1, -1)
		
		elif key.vk == libtcod.KEY_KP9:
			player_move_or_attack(1, -1)
		
		elif key.vk == libtcod.KEY_KP1:
			player_move_or_attack(1, -1)
		
		elif key.vk == libtcod.KEY_KP3:
			player_move_or_attack(1, 1)
		
		elif key.vk == libtcod.KEY_KP5:
			pass
		
		else:
			#test for other keys
			key_char = chr(key.c)
			
			if key_char == 'g':
				#pick up item
				for object in objects: #look for an item in tile
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break
			
			if key_char == 'i':
				#show the inventory
				chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.use()
					
			if key_char == 'd':
				#show the inventory, if an item is selected, drop it
				chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.drop()
					
			if key_char == '<':
				#go up stairs if player is on them
				if stairs.x == player.x and stairs.y == player.y:
					next_level()
					
			return 'didnt-take-turn'

def target_monster(max_range=None):
				#returns a lcicked monster inside FOV up toa  range, or None of right-clicked
				while True:
					(x, y) = target_tile(max_range)
					if x is None: #player cancelled
						return None
						
					#return the first clicked monster or loop
					for obj in objects:
						if obj.x == x and obj.y == y and obj.fighter and obj != player:
							return obj
			
def target_tile(max_range=None):
	#return the position of a tile left-clicked in the player's FOV (optionally in a range)
	global key, mouse
	while True:
		#render the screen. this erases the inventory and shows the names of objects under the mouse
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
		render_all()
		
		(x, y) = (mouse.cx, mouse.cy)
		
		if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and (max_range is None or player.distance(x, y) <= max_range)):
			return (x, y)
			
		if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
			return (None, None)  #cancel if the player right-clicked or pressed Escape

			
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
	message('You have been destroyed. Your parts are quickly consumed by the surrounding automata.', libtcod.light_crimson)
	game_state = 'dead'
	
	#corpsify
	player.char = '%'
	player.color = libtcod.darkest_grey


def monster_death(monster):
	global distortion
	#transforms it into a corpse!
	message('You have overcome ' + monster.name + '!', libtcod.orange)
	monster.char = '%'
	monster.color = libtcod.darkest_grey
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()
	distortion = distortion + 1
	
def closest_monster(max_range):
		#find closest enemy, up to a maximum range, and in the player's FOV
		closest_enemy = None
		closest_dist = max_range + 1 #start with (slightly more than) max range
		
		for object in objects:
			if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
				#calculate the distance between object and player
				dist = player.distance_to(object)
				if dist < closest_dist: #it's closer, sor emember it
					closest_enemy = object
					closest_dist = dist
		return closest_enemy
	
def cast_heal():
	#heal the player
	if player.fighter.hp == player.fighter.max_hp:
		message('You do not require repair.', libtcod.orange)
		return 'cancelled'
	
	message ('The magic oil begins to repair your damaged systems.', libtcod.light_blue)
	player.fighter.heal(HEAL_AMOUNT)
	
def cast_corrupt():
	#find closest enemy (inside a maximum range) and damage it
	monster = closest_monster(CORRUPT_RANGE)
	if monster is None: #no enemy in range
		message('No enemy is close enough to strike.', libtcod.orange)
		return 'cancelled'
		
	#ZZZAP
	message('You download the corrupting file into the ' + monster.name + '. The ' + monster.name + ' begins to shoot sparks and smoke while giving off error messages.', libtcod.lighter_blue)
	monster.fighter.take_damage(CORRUPT_DAMAGE)

def cast_glitch():
	#find closest enemy in-range and glitch it
	message('Left-click an an enemy to download the glitch script into it', libtcod.cyan)
	monster = target_monster(GLITCH_RANGE)
	if monster is None: #no enemy found
		return 'cancelled'
	
	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai)
	monster.ai.owner = monster
	message('You download the glitching file into the ' + monster.name + '. The ' + monster.name + ' begins to behave erratically while spitting out binary nonsense.', libtcod.lighter_blue)
	
def cast_gravitywell():
	#ask the player for a target tile for the gravity well
	message('Left-click to choose a target tile to throw the unstable anti-matter, or right-click to cancel.', libtcod.cyan)
	(x, y) = target_tile()
	if x is None: return 'cancelled'
	message('Hunks of metal go flying as a gravity well forms and tears things within ' + str(GRAV_RADIUS) + ' tiles asunder!', libtcod.darker_grey)
	
	for obj in objects:
		if obj.distance(x, y) <= GRAV_RADIUS and obj.fighter:
			message('Pieces of ' + obj.name + ' get torn off!', libtcod.flame)
			obj.fighter.take_damage(GRAV_DAMAGE)
			
			
#++++++++++++++THIS SHIT RIGHT HERE, THIS SHIT BE BLANDVVV.

def next_level():
	global dungeon_level
	#advance to the next level
	message('You head up the stairs, onto the next level of the Nexus.', libtcod.light_violet)
	
	dungeon_level += 1
	
	make_map()
	initialize_fov()


			
def new_game():
	global player, inventory, game_msgs, game_state, first_time, dungeon_level
	
	dungeon_level = 1
	
	#create object representing the player
	fighter_component = Fighter(hp=30, defense=2, power=6, energy=20, death_function=player_death)
	player = Object(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component)
	
	#generate map
	make_map()
	initialize_fov()
	
	game_state = 'playing'
	first_time = True
	inventory = []
	game_msgs = []
	
	#a warm welcoming message!
	message('Welcome to the Nexus, brave automaton. Will you learn the secrets of this place or perish like so many others at the hands of the mysterious Nexus?', libtcod.light_blue)
	
def initialize_fov():
	global fov_recompute, fov_map
	fov_recompute = True
	
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
	
	libtcod.console_clear(con)

def play_game():
	global key, mouse
	
	player_action = None

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
			save_game()
			break
		
		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in objects:
				if object.ai:
					object.ai.take_turn()
	
def main_menu():
	img = libtcod.image_load('GEAR.png')
	
	while not libtcod.console_is_window_closed():
		libtcod.image_blit_2x(img, 0, 0, 0)
		
		choice = menu('', ['New Game', 'Continue Game', 'Quit'], 24)
		
		if choice == 0:
			new_game()
			play_game()
		
		if choice == 1:
			try:
				load_game()
			except:
				msgbox('\n No save game to load.\n', 24)
				continue
			play_game()
		
		elif choice == 2:
			break
	
def save_game():
	global distortion
	#open a new empty shelve to write game data
	file = shelve.open('savegame', 'n')
	file['map'] = map
	file['objects'] = objects
	file['player_index'] = objects.index(player)
	file['inventory'] = inventory
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file['distortion'] = distortion
	file['stairs_index'] = object.index(stairs)
	file['dungeon_level'] = dungeon_level
	file.close()

def load_game():
	global map, objects, player, inventory, game_msgs, game_state, distortion, first_time
	global stairs, dungeon_level
	
	file = shelve.open('savegame', 'r')
	map = file['map']
	objects = file['objects']
	player = objects[file['player_index']]
	inventory = file['inventory']
	game_msgs = file['game_msgs']
	game_state = file['game_state']
	distortion = file['distortion']
	stairs = objects[file['stairs_index']]
	dungeon_level = file['dungeon level']
	first_time = False
	file.close()
	
	initialize_fov()
	


#main loop all up in dis
#u don't even kno
#this code be fresh and poppin
	
libtcod.console_set_custom_font('prestige12x12_gs_tc.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)

libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'GEAR: WIZARD OF THE TECHNO NEXUS', False)
libtcod.sys_set_fps(LIMIT_FPS)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)

panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

main_menu()
