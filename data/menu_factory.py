"""menu_factory.py — generate diverse, valid menus in the menu.json schema.

WHY: training across MANY different menus teaches the model the SKILL "order from
whatever menu is in my prompt" instead of memorizing one menu's items. That's what
makes the released model menu-agnostic — a new restaurant just drops in their menu,
no retraining (Path A). Every generated menu is schema-valid: build_index +
pricing.line_price work on it unchanged.

random_menu(rng) -> a menu dict (same shape as menu/menu.json).
"""
from __future__ import annotations

import random

SIZES3 = ["S", "M", "L"]

# Each theme supplies pools of (id, display_name, mods) for mains and
# (id, display_name, sized?) for sides/drinks, plus sauces + a combo label.
THEMES = {
    "burgers": {
        "mains": [("burger_classic", "Classic Burger", ["no_onion", "no_pickle", "extra_cheese", "add_bacon"]),
                  ("burger_double", "Double Stack", ["no_onion", "extra_cheese", "add_bacon"]),
                  ("sandwich_chicken", "Crispy Chicken Sandwich", ["no_mayo", "spicy", "add_lettuce"]),
                  ("nuggets_8", "8pc Nuggets", []),
                  ("veggie_wrap", "Veggie Wrap", ["no_sauce", "add_cheese"])],
        "sides": [("fries", "Fries", True), ("onion_rings", "Onion Rings", True), ("side_salad", "Side Salad", False)],
        "drinks": [("cola", "Cola", True), ("lemon_lime", "Lemon-Lime Soda", True),
                   ("shake", "Milkshake", True), ("water", "Water", True)],
        "sauces": ["ketchup", "bbq", "ranch", "honey_mustard"],
        "combo": "Combo",
    },
    "tacos": {
        "mains": [("taco_pastor", "Al Pastor Taco", ["no_onion", "extra_salsa", "add_cheese"]),
                  ("taco_carnitas", "Carnitas Taco", ["no_cilantro", "extra_salsa"]),
                  ("burrito_bean", "Bean Burrito", ["add_guac", "no_rice", "extra_cheese"]),
                  ("quesadilla", "Cheese Quesadilla", ["add_chicken", "add_steak"]),
                  ("nachos", "Loaded Nachos", ["no_jalapeno", "add_guac"])],
        "sides": [("chips_guac", "Chips & Guac", False), ("rice_beans", "Rice & Beans", False),
                  ("elote", "Street Corn", False)],
        "drinks": [("horchata", "Horchata", True), ("jarritos", "Jarritos", True),
                   ("agua_fresca", "Agua Fresca", True), ("water", "Water", True)],
        "sauces": ["salsa_verde", "salsa_roja", "crema", "hot_sauce"],
        "combo": "Plate",
    },
    "pizza": {
        "mains": [("pizza_margherita", "Margherita Pizza", ["extra_cheese", "add_mushroom", "no_basil"]),
                  ("pizza_pepperoni", "Pepperoni Pizza", ["extra_cheese", "add_mushroom"]),
                  ("calzone", "Calzone", ["add_ricotta", "no_sauce"]),
                  ("garlic_knots", "Garlic Knots", []),
                  ("wings", "Buffalo Wings", ["extra_spicy", "add_ranch"])],
        "sides": [("caesar", "Caesar Salad", False), ("breadsticks", "Breadsticks", False)],
        "drinks": [("cola", "Cola", True), ("root_beer", "Root Beer", True),
                   ("lemonade", "Lemonade", True), ("water", "Water", True)],
        "sauces": ["marinara", "ranch", "garlic_butter"],
        "combo": "Meal",
    },
    "cafe": {
        "mains": [("latte", "Latte", ["oat_milk", "extra_shot", "decaf"]),
                  ("cappuccino", "Cappuccino", ["oat_milk", "extra_shot"]),
                  ("cold_brew", "Cold Brew", ["add_vanilla", "add_caramel"]),
                  ("croissant", "Butter Croissant", ["warmed"]),
                  ("bagel", "Bagel & Cream Cheese", ["toasted", "no_cream_cheese"])],
        "sides": [("muffin", "Blueberry Muffin", False), ("cookie", "Chocolate Chip Cookie", False)],
        "drinks": [("drip_coffee", "Drip Coffee", True), ("iced_tea", "Iced Tea", True),
                   ("hot_chocolate", "Hot Chocolate", True), ("water", "Water", True)],
        "sauces": [],
        "combo": "Combo",
    },
    "deli": {
        "mains": [("sub_italian", "Italian Sub", ["no_onion", "extra_cheese", "add_peppers"]),
                  ("sub_turkey", "Turkey Club", ["no_mayo", "add_avocado"]),
                  ("blt", "BLT", ["extra_bacon", "no_tomato"]),
                  ("grilled_cheese", "Grilled Cheese", ["add_tomato", "add_bacon"]),
                  ("soup", "Soup of the Day", [])],
        "sides": [("chips", "Chips", False), ("pickle_spear", "Pickle Spear", False),
                  ("pasta_salad", "Pasta Salad", True)],
        "drinks": [("cola", "Cola", True), ("ginger_ale", "Ginger Ale", True),
                   ("iced_tea", "Iced Tea", True), ("water", "Water", True)],
        "sauces": ["mayo", "mustard", "italian_dressing"],
        "combo": "Combo",
    },
    "noodles": {
        "mains": [("pad_thai", "Pad Thai", ["extra_peanuts", "no_egg", "add_tofu"]),
                  ("ramen_shoyu", "Shoyu Ramen", ["extra_noodles", "add_egg", "no_pork"]),
                  ("fried_rice", "Fried Rice", ["add_shrimp", "no_egg"]),
                  ("dumplings", "Pork Dumplings", ["steamed", "fried"]),
                  ("spring_rolls", "Spring Rolls", [])],
        "sides": [("edamame", "Edamame", False), ("miso_soup", "Miso Soup", False)],
        "drinks": [("thai_tea", "Thai Iced Tea", True), ("green_tea", "Green Tea", True),
                   ("soda", "Soda", True), ("water", "Water", True)],
        "sauces": ["soy", "sriracha", "sweet_chili"],
        "combo": "Set",
    },
    "breakfast": {
        "mains": [("pancakes", "Stack of Pancakes", ["add_blueberries", "add_chocolate_chips"]),
                  ("omelette", "Cheese Omelette", ["add_ham", "add_mushroom", "no_cheese"]),
                  ("breakfast_burrito", "Breakfast Burrito", ["no_onion", "add_avocado", "extra_cheese"]),
                  ("french_toast", "French Toast", ["add_powdered_sugar"]),
                  ("hash_browns", "Hash Browns", [])],
        "sides": [("bacon_side", "Side of Bacon", False), ("fruit_cup", "Fruit Cup", False),
                  ("toast", "Toast", False)],
        "drinks": [("orange_juice", "Orange Juice", True), ("coffee", "Coffee", True),
                   ("milk", "Milk", True), ("water", "Water", True)],
        "sauces": ["syrup", "hot_sauce", "ketchup"],
        "combo": "Breakfast Combo",
    },
    "icecream": {
        "mains": [("sundae", "Hot Fudge Sundae", ["add_nuts", "no_cherry", "extra_fudge"]),
                  ("cone_vanilla", "Vanilla Cone", ["dipped", "add_sprinkles"]),
                  ("banana_split", "Banana Split", ["add_nuts", "extra_whip"]),
                  ("milkshake_choc", "Chocolate Shake", ["add_malt", "extra_whip"]),
                  ("float", "Root Beer Float", [])],
        "sides": [("waffle_cone", "Waffle Cone Upgrade", False), ("cookie_side", "Cookie", False)],
        "drinks": [("soda", "Soda", True), ("water", "Water", True), ("lemonade", "Lemonade", True)],
        "sauces": ["hot_fudge", "caramel", "strawberry"],
        "combo": "Treat Combo",
    },
    "bowls": {
        "mains": [("acai_bowl", "Açaí Bowl", ["add_granola", "add_peanut_butter", "no_banana"]),
                  ("poke_bowl", "Poke Bowl", ["extra_tuna", "no_rice", "add_avocado"]),
                  ("smoothie_bowl", "Smoothie Bowl", ["add_granola", "add_honey"]),
                  ("grain_bowl", "Grain Bowl", ["add_chicken", "no_dressing"]),
                  ("avocado_toast", "Avocado Toast", ["add_egg", "extra_avocado"])],
        "sides": [("fruit_side", "Fruit Cup", False), ("chia_pudding", "Chia Pudding", False)],
        "drinks": [("green_smoothie", "Green Smoothie", True), ("kombucha", "Kombucha", True),
                   ("coconut_water", "Coconut Water", True), ("water", "Water", True)],
        "sauces": [],
        "combo": "Bowl Combo",
    },
    "bbq": {
        "mains": [("brisket_plate", "Brisket Plate", ["extra_sauce", "no_pickle"]),
                  ("pulled_pork", "Pulled Pork Sandwich", ["add_slaw", "extra_sauce"]),
                  ("ribs_half", "Half Rack Ribs", ["extra_sauce"]),
                  ("smoked_wings", "Smoked Wings", ["add_ranch"]),
                  ("burnt_ends", "Burnt Ends", [])],
        "sides": [("mac_cheese", "Mac & Cheese", True), ("cornbread", "Cornbread", False),
                  ("coleslaw", "Coleslaw", False), ("baked_beans", "Baked Beans", True)],
        "drinks": [("sweet_tea", "Sweet Tea", True), ("lemonade", "Lemonade", True),
                   ("soda", "Soda", True), ("water", "Water", True)],
        "sauces": ["original_bbq", "spicy_bbq", "mustard_bbq"],
        "combo": "Plate",
    },
    "sushi": {
        "mains": [("roll_california", "California Roll", ["no_avocado", "extra_crab"]),
                  ("roll_spicy_tuna", "Spicy Tuna Roll", ["extra_spicy", "no_cucumber"]),
                  ("roll_dragon", "Dragon Roll", ["no_eel_sauce"]),
                  ("bento_box", "Bento Box", ["add_tempura", "no_rice"]),
                  ("chirashi", "Chirashi Bowl", ["extra_fish"])],
        "sides": [("miso_soup", "Miso Soup", False), ("seaweed_salad", "Seaweed Salad", False),
                  ("gyoza", "Gyoza", True)],
        "drinks": [("green_tea", "Green Tea", True), ("ramune", "Ramune Soda", True),
                   ("iced_tea", "Iced Tea", True), ("water", "Water", True)],
        "sauces": ["soy", "spicy_mayo", "eel_sauce", "ponzu"],
        "combo": "Set",
    },
    "indian": {
        "mains": [("tikka_masala", "Chicken Tikka Masala", ["extra_spicy", "mild", "add_naan"]),
                  ("paneer_tikka", "Paneer Tikka", ["extra_spicy", "no_onion"]),
                  ("samosa", "Samosa", ["add_chutney"]),
                  ("veg_biryani", "Veg Biryani", ["extra_spicy", "add_raita"]),
                  ("butter_chicken", "Butter Chicken", ["mild", "extra_sauce"])],
        "sides": [("garlic_naan", "Garlic Naan", False), ("basmati_rice", "Basmati Rice", True),
                  ("raita_side", "Raita", False)],
        "drinks": [("mango_lassi", "Mango Lassi", True), ("masala_chai", "Masala Chai", True),
                   ("soda", "Soda", True), ("water", "Water", True)],
        "sauces": ["mint_chutney", "tamarind", "raita"],
        "combo": "Thali",
    },
    "mediterranean": {
        "mains": [("chicken_shawarma", "Chicken Shawarma", ["extra_garlic", "no_onion", "add_feta"]),
                  ("falafel_wrap", "Falafel Wrap", ["no_tahini", "extra_hummus"]),
                  ("gyro_plate", "Gyro Plate", ["extra_tzatziki", "no_tomato"]),
                  ("kebab", "Beef Kebab", ["extra_spicy", "add_rice"]),
                  ("hummus_bowl", "Hummus Bowl", ["add_pita", "extra_olive_oil"])],
        "sides": [("pita", "Warm Pita", False), ("tabbouleh", "Tabbouleh", True), ("dolma", "Dolma", False)],
        "drinks": [("mint_lemonade", "Mint Lemonade", True), ("ayran", "Ayran", True),
                   ("turkish_coffee", "Turkish Coffee", True), ("water", "Water", True)],
        "sauces": ["tzatziki", "tahini", "harissa", "garlic_sauce"],
        "combo": "Plate",
    },
    "korean": {
        "mains": [("bibimbap", "Bibimbap", ["add_egg", "extra_gochujang", "no_beef"]),
                  ("bulgogi", "Beef Bulgogi", ["extra_spicy", "add_rice"]),
                  ("korean_wings", "Korean Fried Wings", ["soy_garlic", "spicy"]),
                  ("kimchi_fried_rice", "Kimchi Fried Rice", ["add_egg", "add_spam"]),
                  ("japchae", "Japchae", ["add_beef"])],
        "sides": [("kimchi", "Kimchi", False), ("mandu", "Mandu Dumplings", True), ("seaweed_soup", "Seaweed Soup", False)],
        "drinks": [("barley_tea", "Barley Tea", True), ("sikhye", "Sikhye", True),
                   ("soda", "Soda", True), ("water", "Water", True)],
        "sauces": ["gochujang", "soy_garlic", "sesame"],
        "combo": "Set",
    },
    "vietnamese": {
        "mains": [("pho_beef", "Beef Pho", ["extra_noodles", "no_onion", "add_brisket"]),
                  ("banh_mi", "Banh Mi", ["no_cilantro", "extra_pate", "add_jalapeno"]),
                  ("vermicelli_bowl", "Vermicelli Bowl", ["add_spring_roll", "no_fish_sauce"]),
                  ("spring_rolls", "Fresh Spring Rolls", []),
                  ("com_tam", "Broken Rice Plate", ["add_egg", "extra_pork"])],
        "sides": [("egg_roll", "Egg Roll", True), ("side_rice", "Steamed Rice", False)],
        "drinks": [("viet_coffee", "Vietnamese Coffee", True), ("coconut", "Coconut Water", True),
                   ("soda", "Soda", True), ("water", "Water", True)],
        "sauces": ["fish_sauce", "sriracha", "hoisin"],
        "combo": "Combo",
    },
    "greek": {
        "mains": [("souvlaki", "Pork Souvlaki", ["extra_tzatziki", "no_onion"]),
                  ("spanakopita", "Spanakopita", ["add_feta"]),
                  ("greek_salad_main", "Greek Salad", ["no_olives", "extra_feta", "add_chicken"]),
                  ("moussaka", "Moussaka", ["extra_bechamel"]),
                  ("lamb_gyro", "Lamb Gyro", ["no_tomato", "extra_onion"])],
        "sides": [("greek_fries", "Feta Fries", True), ("pita_side", "Pita", False), ("olives", "Olives", False)],
        "drinks": [("frappe", "Greek Frappé", True), ("lemonade", "Lemonade", True), ("water", "Water", True)],
        "sauces": ["tzatziki", "skordalia", "lemon_oregano"],
        "combo": "Plate",
    },
    "soulfood": {
        "mains": [("fried_chicken_plate", "Fried Chicken Plate", ["extra_crispy", "spicy", "add_gravy"]),
                  ("catfish", "Fried Catfish", ["extra_spicy"]),
                  ("smothered_pork", "Smothered Pork Chop", ["extra_gravy"]),
                  ("oxtails", "Braised Oxtails", ["extra_sauce"]),
                  ("mac_main", "Baked Mac & Cheese", ["add_breadcrumbs"])],
        "sides": [("collards", "Collard Greens", True), ("cornbread", "Cornbread", False),
                  ("candied_yams", "Candied Yams", True), ("black_eyed_peas", "Black-Eyed Peas", False)],
        "drinks": [("sweet_tea", "Sweet Tea", True), ("lemonade", "Lemonade", True),
                   ("soda", "Soda", True), ("water", "Water", True)],
        "sauces": ["hot_sauce", "gravy", "honey"],
        "combo": "Plate",
    },
    "seafood": {
        "mains": [("fish_and_chips", "Fish & Chips", ["extra_tartar", "no_lemon"]),
                  ("shrimp_basket", "Shrimp Basket", ["extra_cocktail", "grilled"]),
                  ("crab_cakes", "Crab Cakes", ["add_remoulade"]),
                  ("lobster_roll", "Lobster Roll", ["extra_butter", "no_celery"]),
                  ("clam_chowder", "Clam Chowder", [])],
        "sides": [("hush_puppies", "Hush Puppies", True), ("coleslaw", "Coleslaw", False), ("fries", "Fries", True)],
        "drinks": [("lemonade", "Lemonade", True), ("iced_tea", "Iced Tea", True), ("water", "Water", True)],
        "sauces": ["tartar", "cocktail", "remoulade", "old_bay"],
        "combo": "Basket",
    },
    "saladbar": {
        "mains": [("cobb_salad", "Cobb Salad", ["no_egg", "add_chicken", "extra_avocado"]),
                  ("caesar_main", "Chicken Caesar", ["no_crouton", "extra_parmesan"]),
                  ("quinoa_salad", "Quinoa Power Salad", ["add_salmon", "no_feta"]),
                  ("wrap_veggie", "Veggie Wrap", ["add_hummus", "no_onion"]),
                  ("soup_combo", "Soup & Half Salad", [])],
        "sides": [("garlic_bread", "Garlic Bread", False), ("fruit_cup", "Fruit Cup", False)],
        "drinks": [("kombucha", "Kombucha", True), ("iced_tea", "Iced Tea", True),
                   ("sparkling", "Sparkling Water", True), ("water", "Water", True)],
        "sauces": ["ranch", "balsamic", "caesar", "honey_mustard"],
        "combo": "Combo",
    },
    "juicebar": {
        "mains": [("green_juice", "Green Juice", ["add_ginger", "add_spirulina"]),
                  ("protein_shake", "Protein Shake", ["add_peanut_butter", "oat_milk"]),
                  ("mango_smoothie", "Mango Smoothie", ["add_chia", "no_yogurt"]),
                  ("acai_blend", "Açaí Blend", ["add_granola", "extra_berries"]),
                  ("wellness_shot", "Ginger Wellness Shot", [])],
        "sides": [("energy_ball", "Energy Ball", False), ("granola_cup", "Granola Cup", False)],
        "drinks": [("coconut_water", "Coconut Water", True), ("cold_brew", "Cold Brew", True),
                   ("water", "Water", True)],
        "sauces": [],
        "combo": "Combo",
    },
    "steakhouse": {
        "mains": [("ribeye", "Ribeye Steak", ["rare", "medium", "well_done", "add_butter"]),
                  ("sirloin", "Sirloin", ["medium_rare", "add_mushrooms"]),
                  ("steak_sandwich", "Steak Sandwich", ["no_onion", "extra_cheese"]),
                  ("grilled_salmon", "Grilled Salmon", ["no_lemon", "extra_dill"]),
                  ("chicken_breast", "Grilled Chicken Breast", ["extra_spicy"])],
        "sides": [("baked_potato", "Baked Potato", False), ("creamed_spinach", "Creamed Spinach", True),
                  ("mashed", "Mashed Potatoes", True), ("asparagus", "Grilled Asparagus", False)],
        "drinks": [("iced_tea", "Iced Tea", True), ("lemonade", "Lemonade", True),
                   ("soda", "Soda", True), ("water", "Water", True)],
        "sauces": ["a1", "peppercorn", "chimichurri", "garlic_butter"],
        "combo": "Dinner",
    },
    "hotpot": {
        "mains": [("beef_hotpot", "Beef Hot Pot", ["extra_spicy", "mild", "add_tofu"]),
                  ("seafood_hotpot", "Seafood Hot Pot", ["extra_spicy", "add_noodles"]),
                  ("veggie_hotpot", "Vegetable Hot Pot", ["add_mushroom", "extra_broth"]),
                  ("dumpling_soup", "Dumpling Soup", ["add_egg"]),
                  ("lamb_skewers", "Lamb Skewers", ["extra_cumin"])],
        "sides": [("steamed_buns", "Steamed Buns", True), ("bok_choy", "Bok Choy", False), ("noodles_side", "Noodles", False)],
        "drinks": [("jasmine_tea", "Jasmine Tea", True), ("lychee_soda", "Lychee Soda", True),
                   ("soy_milk", "Soy Milk", True), ("water", "Water", True)],
        "sauces": ["sesame_paste", "chili_oil", "soy"],
        "combo": "Set",
    },
}

THEME_NAMES = list(THEMES)


def _price(rng, lo, hi):
    """A plausible price ending in .x9, in [lo, hi]."""
    base = rng.uniform(lo, hi)
    return round(int(base) + rng.choice([0.49, 0.79, 0.99, 0.29]), 2)


def _sized_prices(rng, lo, hi):
    s = _price(rng, lo, hi)
    return {"S": s, "M": round(s + rng.choice([0.4, 0.5, 0.6]), 2), "L": round(s + rng.choice([0.9, 1.0, 1.2]), 2)}


def random_menu(rng: random.Random) -> dict:
    """Build one schema-valid menu from a random theme."""
    theme = THEMES[rng.choice(THEME_NAMES)]

    mains_pool = rng.sample(theme["mains"], rng.randint(3, len(theme["mains"])))
    mains = {}
    for mid, name, mods in mains_pool:
        keep = [m for m in mods if rng.random() < 0.8]
        mains[mid] = {"name": name, "mods": keep, "price": _price(rng, 3, 10)}

    sides = {}
    for sid, name, sized in rng.sample(theme["sides"], rng.randint(2, len(theme["sides"]))):
        if sized:
            sides[sid] = {"name": name, "sizes": SIZES3, "prices": _sized_prices(rng, 2, 4)}
        else:
            sides[sid] = {"name": name, "sizes": [], "price": _price(rng, 2, 5)}

    drinks = {}
    for did, name, sized in rng.sample(theme["drinks"], rng.randint(2, len(theme["drinks"]))):
        is_water = "water" in did
        if sized:
            prices = {"S": 0.0, "M": 0.0, "L": 0.0} if is_water else _sized_prices(rng, 1, 4)
            drinks[did] = {"name": name, "sizes": SIZES3, "prices": prices}
        else:
            drinks[did] = {"name": name, "sizes": [], "price": 0.0 if is_water else _price(rng, 1, 4)}

    # 0-3 combos: main + side + drink, sized M/L
    combos = {}
    n_combo = rng.randint(0, 3)
    main_ids = list(mains)
    for k in range(min(n_combo, len(main_ids))):
        m = main_ids[k]
        base = _price(rng, 6, 12)
        combos[f"combo_{m}"] = {"name": f"{mains[m]['name']} {theme['combo']}", "sizes": ["M", "L"],
                                "includes": [m, "side", "drink"], "prices": {"M": base, "L": round(base + 1.0, 2)}}

    # mod prices: most free; a few "add_/extra_" mods cost extra
    mod_prices = {}
    for spec in mains.values():
        for m in spec["mods"]:
            if (m.startswith(("add_", "extra_")) and m not in mod_prices and rng.random() < 0.6):
                mod_prices[m] = rng.choice([0.5, 0.75, 1.0, 1.5])

    return {"combos": combos, "mains": mains, "sides": sides, "drinks": drinks,
            "sauces": theme["sauces"], "mod_prices": mod_prices, "currency": "USD"}
