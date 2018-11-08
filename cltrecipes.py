import sqlite3
import argparse
import glob
import datetime
import pickle
import functools
import os

import toml
import jinja2

CONF_PATH = "./conf.toml"
RECIPES_PATH = "./recipes/*.toml"
EXAMPLE_RECIPE_PATH = "./recipes/_example.toml"
TEMPLATES_PATH = "./templates/"
AUTHORS_PATH = "./authors/"
OUTPUT_PATH = "./output/"
RECIPES_PER_PAGE = 10

REQUIRED_RECIPE_FIELDS = (
    "title",
    "date_added",
    "author",
    "type",
    "ingredients",
    "directions",
    "description"
    # XXX figure out nutrition later
)

OPTIONAL_RECIPE_FIELDS = (
    "cook_time",
    "prep_time",
    "yield",
    "serving_size",
    "nutrition"
)

NUTRITION_FIELDS = set((
    "calories",
    "total_fat",
    "saturated_fat",
    "trans_fat",
    "cholesterol",
    "sodium",
    "total_carbohydrates",
    "fiber",
    "sugars",
    "protein",
    "unsaturated_fat",
))

TODAY = datetime.date.today()
TODAY_INT = TODAY.year*10000 + TODAY.month*100 + TODAY.day

pickle_dumps = functools.partial(pickle.dumps, protocol=-1)

def err(msg):
    raise Exception(msg)

def err_exc(exception_obj, msg):
    err(f"{msg}: {exception_obj!s}")

def open_toml(filename):
    try:
        fd = open(filename)
    except Exception as e:
        err_exc(e, f"Unable to open {filename}")
    with fd:
        try:
            return toml.load(fd)
        except Exception as e:
            err_exc(e, f"Unable to parse {filename}")

def chunk(l, n):
    for i in range(0, len(l), n):
        yield l[i:i+n]

class Site(object):
    def run(self):
        self.init_conf()
        self.init_jinja()
        self.init_db()

        recipes = self.parse_recipes()
        self.load_db(recipes)

        self.write_site()

    def init_conf(self):
        self.conf = open_toml(CONF_PATH)

    def init_jinja(self):
        self.jinja = jinja2.Environment(
            loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
            autoescape=jinja2.select_autoescape(['html'])
        )

    def _write_template(self, template_name, output_filename, template_kwargs):
        template = self.jinja.get_template(template_name)
        try:
            os.mkdir(OUTPUT_PATH)
        except FileExistsError:
            pass
        output_filepath = os.path.join(OUTPUT_PATH, output_filename)
        with open(output_filepath, 'w') as fd:
            fd.write(template.render(**template_kwargs))

    def init_db(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.cur = self.db.cursor()
        self.cur.execute("""
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    title TEXT NOT NULL,
    date_added INTEGER NOT NULL,
    author TEXT NOT NULL,
    type TEXT NOT NULL,
    cook_time INTEGER,
    prep_time INTEGER,

    description TEXT NOT NULL,

    ingredients BLOB NOT NULL,

    yield TEXT,
    serving_size TEXT,

    directions TEXT NOT NULL,

    nutrition BLOB
)""")
        self.cur.execute("CREATE INDEX recipes_date_added ON recipes (date_added DESC)")

    def parse_recipes(self):
        recipe_filenames = glob.glob(RECIPES_PATH)
        try:
            recipe_filenames.remove(EXAMPLE_RECIPE_PATH)
        except ValueError:
            pass
        return [self.parse_recipe(filename) for filename in recipe_filenames]

    def parse_recipe(self, recipe_filename):
        recipe = open_toml(recipe_filename)
        # grab basename, strip .toml
        recipe["filename"] = os.path.basename(recipe_filename)[:-5]

        for required_field in REQUIRED_RECIPE_FIELDS:
            if required_field not in recipe:
                err(f"Required field {required_field} not in recipe {recipe_filename}")

        if "nutrition" in recipe:
            for macro in recipe["nutrition"]:
                if macro not in NUTRITION_FIELDS:
                    err(f"{macro} is an unknown macronutrient in recipe {recipe_filename}")

        if not isinstance(recipe["ingredients"], list):
            err("ingredients must be a list")

        if len(recipe["ingredients"]) == 0:
            err("ingredients must not be empty")
        return recipe

    def load_db(self, recipes):
        [self.insert_recipe(recipe) for recipe in recipes]

    def insert_recipe(self, recipe):
        self.cur.execute("""
INSERT INTO recipes
    (id, title, date_added, author, type, ingredients, directions,
     description, filename)
VALUES
    (NULL, ?, ?, ?, ?, ?, ?, ?, ?)
""", (recipe["title"], TODAY_INT, recipe["author"], recipe["type"],
      pickle_dumps(recipe["ingredients"]), recipe["directions"],
      recipe["description"], recipe["filename"]))
        recipe_id = self.cur.lastrowid

        for field in OPTIONAL_RECIPE_FIELDS:
            if field in recipe:
                self.cur.execute(f"""
UPDATE recipes SET {field} = ? WHERE id = ?
""", (recipe[field], recipe_id))

    def write_site(self):
        self.write_front_pages()
        self.write_recipe_pages()
        #self.write_tag_index()

    def write_front_pages(self):
        self.cur.execute("""
SELECT
    id
    , filename
    , title
    , date_added
    , author
    , description
FROM recipes
ORDER BY date_added DESC
""")
        recipes = self.cur.fetchall()
        chunks = list(chunk(recipes, RECIPES_PER_PAGE))
        page_cnt = len(chunks)
        for page_idx, page in enumerate(chunks):
            page_idx += 1
            self.write_front_page(page, page_idx, page_cnt)

    def write_front_page(self, chunk_list, page_idx, page_cnt):
        output_filename = "index.html" if page_idx == 1 else f"index{page_idx}.html"
        self._write_template("front_page.html", output_filename,
            {"recipes": chunk_list, "page_idx": page_idx, "page_cnt": page_cnt})

    def write_recipe_pages(self):
        self.cur.execute("""
SELECT
    id
    , filename
    , title
    , date_added
    , author
    , description
    , type
    , ingredients
    , directions
FROM recipes
""")
        for recipe in self.cur:
            recipe = dict(recipe)
            recipe["ingredients"] = pickle.loads(recipe["ingredients"])
            # XXX fix up the timestamp here too
            output_filename = f'recipe_{recipe["filename"]}.html'
            self._write_template("recipe.html", output_filename,
                {"recipe": recipe})


if __name__ == "__main__":
    s = Site()
    s.run()
