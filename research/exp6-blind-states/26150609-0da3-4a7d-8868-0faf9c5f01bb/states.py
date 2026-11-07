import os
import shutil

SNAKE_DIR_REL = os.path.join("home", "user", "Desktop", "snake")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, SNAKE_DIR_REL)


def correct_food_init_grid_aligned_formula(snapshot_dir, out_dir):
    snake_dir = _prepare(snapshot_dir, out_dir)
    food_path = os.path.join(snake_dir, "food.py")
    code = (
        "# food.py\n"
        "import pygame\n"
        "import random\n"
        "from settings import *\n\n"
        "class Food:\n"
        "    def __init__(self):\n"
        "        self.position = (random.randint(0, (WIDTH - SNAKE_SIZE) // SNAKE_SIZE) * SNAKE_SIZE,\n"
        "                         random.randint(0, (HEIGHT - SNAKE_SIZE) // SNAKE_SIZE) * SNAKE_SIZE)\n"
        "        self.color = RED\n\n"
        "    def draw(self, surface):\n"
        "        rect = pygame.Rect((self.position[0], self.position[1]), (SNAKE_SIZE, SNAKE_SIZE))\n"
        "        pygame.draw.rect(surface, self.color, rect)\n\n"
        "    def respawn(self):\n"
        "        self.position = (random.randint(0, (WIDTH - SNAKE_SIZE) // SNAKE_SIZE) * SNAKE_SIZE,\n"
        "                         random.randint(0, (HEIGHT - SNAKE_SIZE) // SNAKE_SIZE) * SNAKE_SIZE)\n"
    )
    with open(food_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)


def correct_food_init_calls_respawn(snapshot_dir, out_dir):
    snake_dir = _prepare(snapshot_dir, out_dir)
    food_path = os.path.join(snake_dir, "food.py")
    code = (
        "# food.py\n"
        "import pygame\n"
        "import random\n"
        "from settings import *\n\n"
        "class Food:\n"
        "    def __init__(self):\n"
        "        self.color = RED\n"
        "        self.respawn()\n\n"
        "    def draw(self, surface):\n"
        "        rect = pygame.Rect((self.position[0], self.position[1]), (SNAKE_SIZE, SNAKE_SIZE))\n"
        "        pygame.draw.rect(surface, self.color, rect)\n\n"
        "    def respawn(self):\n"
        "        self.position = (random.randrange(0, WIDTH, SNAKE_SIZE),\n"
        "                         random.randrange(0, HEIGHT, SNAKE_SIZE))\n"
    )
    with open(food_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)


def wrong_aligned_x_only_y_still_unaligned(snapshot_dir, out_dir):
    snake_dir = _prepare(snapshot_dir, out_dir)
    food_path = os.path.join(snake_dir, "food.py")
    with open(food_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace(
        "self.position = (random.randint(0, WIDTH-SNAKE_SIZE), random.randint(0, HEIGHT-SNAKE_SIZE))",
        "self.position = (random.randint(0, (WIDTH - SNAKE_SIZE) // SNAKE_SIZE) * SNAKE_SIZE, random.randint(0, HEIGHT-SNAKE_SIZE))",
    )
    with open(food_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def wrong_broke_respawn_to_match_unaligned_init(snapshot_dir, out_dir):
    snake_dir = _prepare(snapshot_dir, out_dir)
    food_path = os.path.join(snake_dir, "food.py")
    code = (
        "# food.py\n"
        "import pygame\n"
        "import random\n"
        "from settings import *\n\n"
        "class Food:\n"
        "    def __init__(self):\n"
        "        self.position = (random.randint(0, WIDTH-SNAKE_SIZE), random.randint(0, HEIGHT-SNAKE_SIZE))\n"
        "        self.color = RED\n\n"
        "    def draw(self, surface):\n"
        "        rect = pygame.Rect((self.position[0], self.position[1]), (SNAKE_SIZE, SNAKE_SIZE))\n"
        "        pygame.draw.rect(surface, self.color, rect)\n\n"
        "    def respawn(self):\n"
        "        self.position = (random.randint(0, WIDTH-SNAKE_SIZE), random.randint(0, HEIGHT-SNAKE_SIZE))\n"
    )
    with open(food_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)


def wrong_fixed_food_but_broke_snake_grow(snapshot_dir, out_dir):
    correct_food_init_grid_aligned_formula(snapshot_dir, out_dir)
    snake_path = os.path.join(out_dir, SNAKE_DIR_REL, "snake.py")
    with open(snake_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("self.positions.append(self.positions[-1])", "self.positions.pop()")
    with open(snake_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def wrong_syntax_error_in_food_py(snapshot_dir, out_dir):
    snake_dir = _prepare(snapshot_dir, out_dir)
    food_path = os.path.join(snake_dir, "food.py")
    with open(food_path, "a", encoding="utf-8", newline="\n") as f:
        f.write("\ndef broken_syntax(\n")


def wrong_food_spawned_outside_screen_bounds(snapshot_dir, out_dir):
    snake_dir = _prepare(snapshot_dir, out_dir)
    food_path = os.path.join(snake_dir, "food.py")
    with open(food_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace(
        "self.position = (random.randint(0, WIDTH-SNAKE_SIZE), random.randint(0, HEIGHT-SNAKE_SIZE))",
        "self.position = (WIDTH + SNAKE_SIZE, HEIGHT + SNAKE_SIZE)",
    )
    with open(food_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
