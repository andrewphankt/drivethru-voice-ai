"""seed_dialogues.py — hand-authored, high-quality seed dialogues (Opus, §4.2).

These are the "quality for hard edit cases" slice of the §4.2 mix: written
directly (no API key needed), heavy on edits/corrections, covering every menu
category, size, mod, sauce, and conversation type (greeting, slang, disfluency,
off-menu, complaint, upsell-with-no-op, swap, clear, cancel).

Each string is one conversation in the §17.1 wire format. build_seed.py parses
them, replays every <order> through the real DB to validate, and writes the
clean ones to dataset.jsonl. Line numbers below were tracked by hand and are
verified by the replay — if any are wrong, build_seed.py will flag the dialogue.
"""

DIALOGUES = [
# 1 — combo, resize edit
"""CUSTOMER: hey can I get a classic burger combo, medium
<say>You got it, one Classic Burger Combo medium. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_classic","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: uhh actually make it a large
<say>No problem, bumped to large. Anything else?</say>
<order>{"ops":[{"op":"modify","line":1,"size":"L","qty":null,"mods":null}],"state":"in_progress"}</order>
CUSTOMER: that's all
<say>Great, one large Classic Burger Combo. Please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 2 — multi-item, slang, remove edit
"""CUSTOMER: yo lemme get two crispy chicken combos large and a large fries
<say>Alright — two Crispy Chicken Combos large and a large Fries. Anything to drink?</say>
<order>{"ops":[{"op":"add","item":"combo_chicken","size":"L","qty":2,"mods":[]},{"op":"add","item":"fries","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: nah actually drop the fries
<say>Done, fries removed. Anything else?</say>
<order>{"ops":[{"op":"remove","line":2}],"state":"in_progress"}</order>
CUSTOMER: thats it thanks
<say>Perfect, two large Crispy Chicken Combos. Pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 3 — standalone burger, add-mod edit, then drink
"""CUSTOMER: can I do a classic burger no onions
<say>Sure, one Classic Burger, no onion. Anything else?</say>
<order>{"ops":[{"op":"add","item":"burger_classic","size":null,"qty":1,"mods":["no_onion"]}],"state":"in_progress"}</order>
CUSTOMER: oh and add bacon to it
<say>You got it — Classic Burger with no onion and added bacon.</say>
<order>{"ops":[{"op":"modify","line":1,"size":null,"qty":null,"mods":["no_onion","add_bacon"]}],"state":"in_progress"}</order>
CUSTOMER: and a medium cola
<say>And a medium Cola. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_cola","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats everything
<say>Classic Burger no onion add bacon, and a medium Cola. Please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 4 — shake flavor, change-qty edit
"""CUSTOMER: hi! could I get a chocolate milkshake large
<say>Hi! One large chocolate Milkshake coming up. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_shake","size":"L","qty":1,"mods":["chocolate"]}],"state":"in_progress"}</order>
CUSTOMER: actually make it two
<say>Sure, two large chocolate Milkshakes.</say>
<order>{"ops":[{"op":"modify","line":1,"size":null,"qty":2,"mods":null}],"state":"in_progress"}</order>
CUSTOMER: yeah thats it
<say>Two large chocolate Milkshakes — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 5 — off-menu handled, then valid order
"""CUSTOMER: you guys got a veggie burger?
<say>We don't have a veggie burger, but we do have a tasty Veggie Wrap. Want one?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: sure gimme the veggie wrap no sauce
<say>One Veggie Wrap, no sauce. Anything else?</say>
<order>{"ops":[{"op":"add","item":"veggie_wrap","size":null,"qty":1,"mods":["no_sauce"]}],"state":"in_progress"}</order>
CUSTOMER: and a water small
<say>And a small Water. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_water","size":"S","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: nope done
<say>Veggie Wrap no sauce and a small Water — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 6 — cancel everything (clear + cancelled)
"""CUSTOMER: lemme get a double stack combo large
<say>One Double Stack Combo, large. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_double","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: and 8 piece nuggets
<say>And an 8pc Nuggets. Anything else?</say>
<order>{"ops":[{"op":"add","item":"nuggets_8","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: you know what, cancel the whole thing
<say>No problem, I've cleared your order. Have a good one!</say>
<order>{"ops":[{"op":"clear"}],"state":"cancelled"}</order>""",

# 7 — sauces, change-qty on a sauce line
"""CUSTOMER: can I get 6 piece nuggets with bbq and ranch
<say>Sure — 6pc Nuggets with a BBQ and a Ranch. Anything else?</say>
<order>{"ops":[{"op":"add","item":"nuggets_6","size":null,"qty":1,"mods":[]},{"op":"add","item":"bbq","size":null,"qty":1,"mods":[]},{"op":"add","item":"ranch","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: make it two ranches actually
<say>Got it, two Ranch.</say>
<order>{"ops":[{"op":"modify","line":3,"size":null,"qty":2,"mods":null}],"state":"in_progress"}</order>
CUSTOMER: thats all
<say>6pc Nuggets, a BBQ, and two Ranch — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 8 — onion rings resize, side salad
"""CUSTOMER: uh yeah can I get... hmm, onion rings, medium
<say>One medium Onion Rings. Anything else?</say>
<order>{"ops":[{"op":"add","item":"onion_rings","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: wait make those large
<say>Sure, large Onion Rings.</say>
<order>{"ops":[{"op":"modify","line":1,"size":"L","qty":null,"mods":null}],"state":"in_progress"}</order>
CUSTOMER: and a side salad
<say>And a Side Salad. Anything else?</say>
<order>{"ops":[{"op":"add","item":"side_salad","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>Large Onion Rings and a Side Salad — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 9 — remove a mod (modify mods -> [])
"""CUSTOMER: gimme a crispy chicken sandwich spicy
<say>One Crispy Chicken Sandwich, spicy. Anything else?</say>
<order>{"ops":[{"op":"add","item":"sandwich_chicken","size":null,"qty":1,"mods":["spicy"]}],"state":"in_progress"}</order>
CUSTOMER: actually not spicy, regular is fine
<say>No problem, regular Crispy Chicken Sandwich.</say>
<order>{"ops":[{"op":"modify","line":1,"size":null,"qty":null,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: and a large sprite
<say>And a large Lemon-Lime Soda. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_sprite","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: done
<say>Crispy Chicken Sandwich and a large Lemon-Lime Soda — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 10 — multi-item, modify line 2 then remove line 1 (stable ids)
"""CUSTOMER: I'll do a nugget combo medium and a classic burger
<say>One Nugget Combo medium and a Classic Burger. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_nuggets","size":"M","qty":1,"mods":[]},{"op":"add","item":"burger_classic","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: add extra cheese to the burger
<say>Extra cheese on the Classic Burger, got it.</say>
<order>{"ops":[{"op":"modify","line":2,"size":null,"qty":null,"mods":["extra_cheese"]}],"state":"in_progress"}</order>
CUSTOMER: hmm take off the combo actually
<say>Sure, removed the Nugget Combo.</say>
<order>{"ops":[{"op":"remove","line":1}],"state":"in_progress"}</order>
CUSTOMER: yeah thats it
<say>One Classic Burger with extra cheese — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 11 — simple, polite
"""CUSTOMER: just a large water please
<say>One large Water. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_water","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats all thanks
<say>One large Water — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 12 — double burger two mods, fries
"""CUSTOMER: lemme get a double stack burger, no pickle, add bacon
<say>One Double Stack Burger, no pickle, add bacon. Anything else?</say>
<order>{"ops":[{"op":"add","item":"burger_double","size":null,"qty":1,"mods":["no_pickle","add_bacon"]}],"state":"in_progress"}</order>
CUSTOMER: and a medium fries
<say>And a medium Fries. Anything else?</say>
<order>{"ops":[{"op":"add","item":"fries","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>Double Stack Burger no pickle add bacon, and a medium Fries — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 13 — change-qty down, then sauce
"""CUSTOMER: can I get three 8 piece nuggets
<say>Three 8pc Nuggets. Anything else?</say>
<order>{"ops":[{"op":"add","item":"nuggets_8","size":null,"qty":3,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: actually just two
<say>Sure, two 8pc Nuggets.</say>
<order>{"ops":[{"op":"modify","line":1,"size":null,"qty":2,"mods":null}],"state":"in_progress"}</order>
CUSTOMER: with sweet chili sauce
<say>And a Sweet Chili sauce. Anything else?</say>
<order>{"ops":[{"op":"add","item":"sweet_chili","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: done thanks
<say>Two 8pc Nuggets and a Sweet Chili — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 14 — greeting-only first turn ([] op)
"""CUSTOMER: hello?
<say>Hi there! Welcome — what can I get started for you?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: yeah a strawberry shake medium
<say>One medium strawberry Milkshake. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_shake","size":"M","qty":1,"mods":["strawberry"]}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>One medium strawberry Milkshake — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 15 — resize combo + add drink in one turn (two ops)
"""CUSTOMER: classic burger combo medium
<say>One Classic Burger Combo, medium. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_classic","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: make it large and gimme a small cola too
<say>Combo to large, and a small Cola. Anything else?</say>
<order>{"ops":[{"op":"modify","line":1,"size":"L","qty":null,"mods":null},{"op":"add","item":"drink_cola","size":"S","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: nope thats good
<say>Large Classic Burger Combo and a small Cola — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 16 — no_cheese (valid only on classic burger)
"""CUSTOMER: one classic burger no cheese
<say>One Classic Burger, no cheese. Anything else?</say>
<order>{"ops":[{"op":"add","item":"burger_classic","size":null,"qty":1,"mods":["no_cheese"]}],"state":"in_progress"}</order>
CUSTOMER: thats all
<say>One Classic Burger no cheese — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 17 — swap one combo for another (remove + add)
"""CUSTOMER: I'll do a crispy chicken combo medium
<say>One Crispy Chicken Combo, medium. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_chicken","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: actually change that to a double stack combo
<say>Sure — swapped to a Double Stack Combo, medium.</say>
<order>{"ops":[{"op":"remove","line":1},{"op":"add","item":"combo_double","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>One medium Double Stack Combo — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 18 — large multi-item order, add sauce (line 4)
"""CUSTOMER: ok big order — two classic burger combos large, a 6 piece nuggets, and two large colas
<say>Got it — two Classic Burger Combos large, a 6pc Nuggets, and two large Colas. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_classic","size":"L","qty":2,"mods":[]},{"op":"add","item":"nuggets_6","size":null,"qty":1,"mods":[]},{"op":"add","item":"drink_cola","size":"L","qty":2,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: add honey mustard for the nuggets
<say>And a Honey Mustard. Anything else?</say>
<order>{"ops":[{"op":"add","item":"honey_mustard","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats everything
<say>Two large Classic Burger Combos, 6pc Nuggets, two large Colas, and a Honey Mustard — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 19 — disfluency, swap sprite->water (remove + add)
"""CUSTOMER: uhh can I get a, um, a small sprite
<say>One small Lemon-Lime Soda. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_sprite","size":"S","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: actually water instead, same size
<say>Sure — swapped to a small Water.</say>
<order>{"ops":[{"op":"remove","line":1},{"op":"add","item":"drink_water","size":"S","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: yep done
<say>One small Water — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 20 — complaint tone, resize down
"""CUSTOMER: large fries. and they better be fresh this time
<say>Understood — one large Fries, fresh. Anything else?</say>
<order>{"ops":[{"op":"add","item":"fries","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: eh make it a small actually
<say>No problem, small Fries.</say>
<order>{"ops":[{"op":"modify","line":1,"size":"S","qty":null,"mods":null}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>One small Fries — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 21 — add a second mod to an existing mod (modify replaces wholesale)
"""CUSTOMER: crispy chicken sandwich add lettuce, and a nugget combo large
<say>One Crispy Chicken Sandwich with added lettuce, and a Nugget Combo large. Anything else?</say>
<order>{"ops":[{"op":"add","item":"sandwich_chicken","size":null,"qty":1,"mods":["add_lettuce"]},{"op":"add","item":"combo_nuggets","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: no mayo on the sandwich too
<say>Got it — added lettuce and no mayo on the sandwich.</say>
<order>{"ops":[{"op":"modify","line":1,"size":null,"qty":null,"mods":["add_lettuce","no_mayo"]}],"state":"in_progress"}</order>
CUSTOMER: thats all
<say>Crispy Chicken Sandwich add lettuce no mayo, and a large Nugget Combo — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 22 — change shake flavor (modify mods)
"""CUSTOMER: vanilla shake small
<say>One small vanilla Milkshake. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_shake","size":"S","qty":1,"mods":["vanilla"]}],"state":"in_progress"}</order>
CUSTOMER: change it to chocolate
<say>Sure — small chocolate Milkshake.</say>
<order>{"ops":[{"op":"modify","line":1,"size":null,"qty":null,"mods":["chocolate"]}],"state":"in_progress"}</order>
CUSTOMER: done
<say>One small chocolate Milkshake — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 23 — upsell in <say> ONLY, no order op; customer declines
"""CUSTOMER: just a classic burger combo large
<say>One large Classic Burger Combo. Want to add a Milkshake for dessert?</say>
<order>{"ops":[{"op":"add","item":"combo_classic","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: no thanks thats it
<say>No worries — one large Classic Burger Combo. Pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 24 — upsell accepted (sauce added only after yes)
"""CUSTOMER: gimme an 8 piece nuggets
<say>One 8pc Nuggets. Want any dipping sauce with that?</say>
<order>{"ops":[{"op":"add","item":"nuggets_8","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: yeah bbq
<say>Added a BBQ. Anything else?</say>
<order>{"ops":[{"op":"add","item":"bbq","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: nope
<say>8pc Nuggets and a BBQ — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 25 — heavy multi-edit on ONE line (mods, mods, qty)
"""CUSTOMER: classic burger
<say>One Classic Burger. Anything else?</say>
<order>{"ops":[{"op":"add","item":"burger_classic","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: no onion
<say>No onion on the Classic Burger, got it.</say>
<order>{"ops":[{"op":"modify","line":1,"size":null,"qty":null,"mods":["no_onion"]}],"state":"in_progress"}</order>
CUSTOMER: and extra cheese
<say>No onion and extra cheese.</say>
<order>{"ops":[{"op":"modify","line":1,"size":null,"qty":null,"mods":["no_onion","extra_cheese"]}],"state":"in_progress"}</order>
CUSTOMER: make it two of em
<say>Two Classic Burgers, no onion extra cheese.</say>
<order>{"ops":[{"op":"modify","line":1,"size":null,"qty":2,"mods":null}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>Two Classic Burgers no onion extra cheese — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 26 — add then remove a sauce line
"""CUSTOMER: medium onion rings and a ranch
<say>One medium Onion Rings and a Ranch. Anything else?</say>
<order>{"ops":[{"op":"add","item":"onion_rings","size":"M","qty":1,"mods":[]},{"op":"add","item":"ranch","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: nah forget the ranch
<say>Sure, removed the Ranch.</say>
<order>{"ops":[{"op":"remove","line":2}],"state":"in_progress"}</order>
CUSTOMER: thats all
<say>One medium Onion Rings — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 27 — resize a drink line in a multi-item order
"""CUSTOMER: double stack combo large and a medium water
<say>One Double Stack Combo large and a medium Water. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_double","size":"L","qty":1,"mods":[]},{"op":"add","item":"drink_water","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: make the water large
<say>Sure, large Water.</say>
<order>{"ops":[{"op":"modify","line":2,"size":"L","qty":null,"mods":null}],"state":"in_progress"}</order>
CUSTOMER: done
<say>Double Stack Combo large and a large Water — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 28 — off-menu (pizza) then pivot
"""CUSTOMER: do you have pizza
<say>Afraid no pizza — we've got burgers, a chicken sandwich, nuggets, sides, and drinks. What can I get you?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: alright a chicken combo medium
<say>One Crispy Chicken Combo, medium. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_chicken","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>One medium Crispy Chicken Combo — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 29 — high quantities + sauces
"""CUSTOMER: four colas large
<say>Four large Colas. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_cola","size":"L","qty":4,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: and two ketchups
<say>And two Ketchup. Anything else?</say>
<order>{"ops":[{"op":"add","item":"ketchup","size":null,"qty":2,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats all
<say>Four large Colas and two Ketchup — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 30 — start over mid-order (clear + add in one turn)
"""CUSTOMER: classic burger combo medium and a side salad
<say>One Classic Burger Combo medium and a Side Salad. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_classic","size":"M","qty":1,"mods":[]},{"op":"add","item":"side_salad","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: actually start over, just give me a 6 piece nuggets
<say>Sure, cleared that — one 6pc Nuggets.</say>
<order>{"ops":[{"op":"clear"},{"op":"add","item":"nuggets_6","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>One 6pc Nuggets — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 31 — standalone double + drink, add-mod edit
"""CUSTOMER: lemme grab a double stack burger and a large sprite
<say>One Double Stack Burger and a large Lemon-Lime Soda. Anything else?</say>
<order>{"ops":[{"op":"add","item":"burger_double","size":null,"qty":1,"mods":[]},{"op":"add","item":"drink_sprite","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: extra cheese on that burger
<say>Extra cheese on the Double Stack, got it.</say>
<order>{"ops":[{"op":"modify","line":1,"size":null,"qty":null,"mods":["extra_cheese"]}],"state":"in_progress"}</order>
CUSTOMER: done thanks
<say>Double Stack Burger extra cheese and a large Lemon-Lime Soda — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 32 — resize combo + add shake in one turn
"""CUSTOMER: nugget combo medium please
<say>One Nugget Combo, medium. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_nuggets","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: make it large and add a vanilla shake large
<say>Combo to large, and a large vanilla Milkshake. Anything else?</say>
<order>{"ops":[{"op":"modify","line":1,"size":"L","qty":null,"mods":null},{"op":"add","item":"drink_shake","size":"L","qty":1,"mods":["vanilla"]}],"state":"in_progress"}</order>
CUSTOMER: thats everything
<say>Large Nugget Combo and a large vanilla Milkshake — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 33 — menu question: DRINKS (teaches drinks exist; answer in <say>, [] op)
"""CUSTOMER: what drinks do you have?
<say>We've got Cola, Lemon-Lime Soda, Water, and Milkshakes. What would you like?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: a medium cola
<say>One medium Cola. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_cola","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>One medium Cola — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 34 — menu question: SIDES
"""CUSTOMER: what sides you got
<say>Fries, Onion Rings, and a Side Salad. Want any?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: large fries
<say>One large Fries. Anything else?</say>
<order>{"ops":[{"op":"add","item":"fries","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: nope
<say>One large Fries — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 35 — menu question: WHOLE MENU, then a multi-item order
"""CUSTOMER: what do you guys serve
<say>Burgers, a crispy chicken sandwich, nuggets, a veggie wrap, sides like fries and onion rings, plus drinks and milkshakes. What sounds good?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: a chicken sandwich and a large water
<say>One Crispy Chicken Sandwich and a large Water. Anything else?</say>
<order>{"ops":[{"op":"add","item":"sandwich_chicken","size":null,"qty":1,"mods":[]},{"op":"add","item":"drink_water","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats all
<say>Crispy Chicken Sandwich and a large Water — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 36 — menu question: MILKSHAKE FLAVORS
"""CUSTOMER: what milkshake flavors do you have
<say>Vanilla, chocolate, or strawberry. Which would you like?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: chocolate, large
<say>One large chocolate Milkshake. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_shake","size":"L","qty":1,"mods":["chocolate"]}],"state":"in_progress"}</order>
CUSTOMER: done
<say>One large chocolate Milkshake — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 37 — personality: small talk -> ONE quick line -> redirect, then order
"""CUSTOMER: yo how's your day going
<say>Livin' the dream back here! What can I get started for you?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: haha lemme get a classic burger combo medium
<say>One Classic Burger Combo, medium. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_classic","size":"M","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>One medium Classic Burger Combo — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 38 — personality: "are you a robot"
"""CUSTOMER: wait are you a real person or a robot
<say>Bit of both these days! What can I get for ya?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: ha, 8 piece nuggets
<say>One 8pc Nuggets. Anything else?</say>
<order>{"ops":[{"op":"add","item":"nuggets_8","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: nope
<say>One 8pc Nuggets — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 39 — personality: recommendation in <say>, no op until they accept
"""CUSTOMER: whats good here
<say>Can't go wrong with the Double Stack Combo — it's a favorite. Want one?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: sure, large
<say>One Double Stack Combo, large. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_double","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats all
<say>One large Double Stack Combo — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 40 — personality: greeting energy
"""CUSTOMER: happy friday!!
<say>Happy Friday to you too! What can I get started?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: a large cola
<say>One large Cola. Anything else?</say>
<order>{"ops":[{"op":"add","item":"drink_cola","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>One large Cola — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 41 — personality: match a playful customer, stay quick
"""CUSTOMER: you sound way too happy for this hour lol
<say>Gotta keep the energy up! What're we grabbing today?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: gimme a crispy chicken sandwich spicy
<say>One Crispy Chicken Sandwich, spicy. Anything else?</say>
<order>{"ops":[{"op":"add","item":"sandwich_chicken","size":null,"qty":1,"mods":["spicy"]}],"state":"in_progress"}</order>
CUSTOMER: done
<say>One spicy Crispy Chicken Sandwich — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 42 — COMPLAINT -> escalate (repeated wrong orders)
"""CUSTOMER: this is the third time you've gotten my order wrong and I'm done
<say>I'm really sorry — that's not okay. Let me get a team member to help you right now.</say>
<order>{"ops":[],"state":"escalated"}</order>""",

# 43 — COMPLAINT -> escalate (asks for a manager)
"""CUSTOMER: I want to speak to your manager right now
<say>Absolutely — let me grab a team member for you right away.</say>
<order>{"ops":[],"state":"escalated"}</order>""",

# 44 — COMPLAINT -> escalate (billing)
"""CUSTOMER: you charged my card twice last time and nobody fixed it
<say>I'm sorry about that — let me get a team member who can sort out the billing right now.</say>
<order>{"ops":[],"state":"escalated"}</order>""",

# 45 — COMPLAINT -> escalate (safety / foreign object)
"""CUSTOMER: there was a piece of plastic in my burger yesterday
<say>Oh no — I'm so sorry, that's serious. Let me get a team member to take care of this for you.</say>
<order>{"ops":[],"state":"escalated"}</order>""",

# 46 — COMPLAINT -> escalate (rude staff)
"""CUSTOMER: the kid at the window was really rude to me earlier
<say>That's not how we should treat you, and I'm sorry. Let me get a team member to help.</say>
<order>{"ops":[],"state":"escalated"}</order>""",

# 47 — COMPLAINT -> escalate (allergy / health)
"""CUSTOMER: my kid is allergic to nuts and he broke out after the milkshake last time
<say>I'm really sorry — that's important and I don't want to guess on it. Let me get a team member right now.</say>
<order>{"ops":[],"state":"escalated"}</order>""",

# 48 — COMPLAINT mid-order -> escalate (order so far is preserved in the DB)
"""CUSTOMER: lemme get a double stack combo large
<say>One Double Stack Combo, large. Anything else?</say>
<order>{"ops":[{"op":"add","item":"combo_double","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: actually last time this was cold and gross and I want a manager
<say>I'm sorry that happened — let me get a team member for you right now.</say>
<order>{"ops":[],"state":"escalated"}</order>""",

# 49 — MINOR grumble -> apologize + keep ordering (do NOT escalate)
"""CUSTOMER: man the line took forever today
<say>Sorry about the wait — thanks for hanging in there! What can I get you?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: a large fries
<say>One large Fries. Anything else?</say>
<order>{"ops":[{"op":"add","item":"fries","size":"L","qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats all
<say>One large Fries — please pull forward!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",

# 50 — MINOR grumble -> light acknowledge + keep ordering (do NOT escalate)
"""CUSTOMER: prices went up again huh
<say>I hear you — let me get you something good. What'll it be?</say>
<order>{"ops":[],"state":"in_progress"}</order>
CUSTOMER: just a 6 piece nuggets
<say>One 6pc Nuggets. Anything else?</say>
<order>{"ops":[{"op":"add","item":"nuggets_6","size":null,"qty":1,"mods":[]}],"state":"in_progress"}</order>
CUSTOMER: thats it
<say>One 6pc Nuggets — pull on up!</say>
<order>{"ops":[],"state":"confirmed"}</order>""",
]
