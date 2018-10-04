import sqlite3
import argparse
import glob

import toml
import jinja2

CONF_PATH = "./conf.toml"
RECIPES_PATH = "./recipes/*.toml"
TEMPLATES_PATH = "./templates/"
AUTHORS_PATH = "./authors/"

REQUIRED_FIELDS = (
    "title",
    "date_added",
    "author",
    "type",
    "ingredients",
    "directions"
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

class Site(object):
    def run(self):
        self.init_conf()
        self.init_db()

        recipes = self.parse_recipes()
        self.load_db(recipes)

        self.write_site()

    def init_conf(self):
        self.conf = open_toml(CONF_PATH)

    def init_db(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute("""
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    date_added INTEGER NOT NULL,
    author TEXT NOT NULL,
    type TEXT NOT NULL,
    cook_time INTEGER,
    prep_time INTEGER,

    ingredients BLOB NOT NULL,

    yield TEXT NOT NULL,
    serving_size TEXT NOT NULL,

    directions TEXT NOT NULL,

    nutrition BLOB
)""")
        self.db.execute("CREATE INDEX recipes_date_added ON recipes (date_added DESC)")

    def parse_recipes(self):
        recipe_filenames = [x for x in glob.glob(RECIPES_PATH) if "_example.toml" not in x]
        return [self.parse_recipe(filename) for filename in recipe_filenames]

    def parse_recipe(self, recipe_filename):
        recipe = open_toml(recipe_filename)

        for required_field in REQUIRED_FIELDS:
            if required_field not in recipe:
                err(f"Required field {required_field} not in recipe {recipe_filename}")

        if "nutrition" in recipe:
            for macro in recipe["nutrition"]:
                if macro not in NUTRITION_FIELDS:
                    err(f"{macro} is an unknown macronutrient in recipe {recipe_filename}")

if __name__ == "__main__":
    s = Site()
    s.run()
