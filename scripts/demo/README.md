# Demo and test stories

Stories used to test the pipeline (`python3 scripts/run_all.py <story.txt> runs/<name>`: a `.txt` file is read as a typed story, a `.wav` as speech). `stories.json` lists the same information for tools and tests.
The fables are retellings of public-domain Aesop fables. The spooky tales are original and kept at picture-book level: unsettling, no blood, no violence, nobody hurt; the image safety check stays on.
Each story is picked to stress something the pipeline has found hard (see [../../docs/limitations.md](../../docs/limitations.md)).

| File | Kind | Words | Contains | Stresses |
|---|---|---|---|---|
| `goldilocks.txt` | earlier test | 520 | four characters, five rooms | long story, four characters on one page, several rooms |
| `boat.txt` | earlier test | 73 | a grandfather and grandson in a boat, a fish, ducks | people inside a boat (still the weakest case), fishing rods, ducks flying up |
| `fox.txt` | earlier test | 77 | a fox and a hedgehog, snow, a lantern, a cave | two small animals, a lantern found then carried, two places |
| `mira.txt` | earlier test | 82 | a girl with glasses, a kite, a fisherman | a kite string that must snap, hair style, glasses |
| `arcania.txt` | earlier test | 88 | fantasy, a prince and a mage | group of mages, magic effects, a small wooden stick |
| `fables/ant_grasshopper.txt` | aesop fable | 128 | two tiny characters, summer then autumn then snow, a fiddle, a nest | season and weather change with the same characters, a held instrument, an underground home |
| `fables/boy_wolf.txt` | aesop fable | 140 | a boy, many villagers, sheep, a wolf, hill and village | crowds and flocks (many identical animals), groups the planner must reduce to one representative, an event the wolf scatters the flock |
| `fables/crow_pitcher.txt` | aesop fable | 122 | one bird, a tall pitcher, pebbles, water level rising | an object that changes state across pages (water rising), tiny details, the same single character on every page |
| `fables/dog_reflection.txt` | aesop fable | 107 | a dog, a bone, a bridge, a stream, a reflection | a character and its own reflection (duplicate figure trap), a dropped object, a bridge over water (standing on something) |
| `fables/fox_grapes.txt` | aesop fable | 104 | one animal, grapes high on a vine, jumping poses, a crow | a held or reached object out of reach, repeated jumping poses, a second animal in the tree |
| `fables/lion_mouse.txt` | aesop fable | 142 | huge size difference, a rope net, hunters, gnawing | a trapped character in a net, tiny character next to a huge one, ropes that must end up cut |
| `fables/north_wind_sun.txt` | aesop fable | 119 | personified wind and sun, a traveler in a cloak, a road and a tree | characters that are not people or animals, an outfit that changes between pages (cloak on, then off) |
| `fables/tortoise_hare.txt` | aesop fable | 150 | two animals of different speed, a crowd of onlookers, a flag, sleeping under a tree, a finish line | crowd page (many animals), a character that is asleep, the winner changes between pages |
| `fables/town_country_mouse.txt` | aesop fable | 128 | two similar mice, a field and a grand dining room, a cat | two look-alike characters that must stay different, two very different places, a chase |
| `spooky/attic_mirror.txt` | spooky tale | 155 | a girl and her reflection who moves on her own, a framed mirror, an attic | the girl and her reflection are two near identical figures (duplicate-character trap), a hand coming out of glass, a blanket thrown over an object |
| `spooky/house_lit_window.txt` | spooky tale | 170 | a hilltop house, a lit window, a ghost lady, two candles | a lit versus unlit candle, a ghost who must look translucent, indoor and outdoor, a storm |
| `spooky/inn_raven_rest.txt` | spooky tale | 220 | three named travelers, an innkeeper, an inn with many rooms, snow then green fields, a ruin | long story with four characters, many rooms, a place that changes completely between pages (inn to ruin), clocks and portraits with watching eyes |
| `spooky/lighthouse_ship.txt` | spooky tale | 149 | a lighthouse, a ghost ship, foggy sea, spiral stairs, faces at portholes | a boat on water, many faces in windows, night and fog, a small final detail (wet footprints) that is easy to miss |
| `spooky/night_train.txt` | spooky tale | 162 | a black train, an empty station, rows of still passengers, a conductor, a ticket | a crowd of passengers, a tall thin character, a held lantern, a small prop (ticket) that ends on a pillow |
| `spooky/scarecrow_stitch.txt` | spooky tale | 172 | a scarecrow that moves closer each night, a girl at a window, a cornfield, a baby crow | the same object in a different position on each page (field, gate, yard, bed), night scenes, a small animal held in hands |
| `spooky/whispering_well.txt` | spooky tale | 141 | a stone well, a bucket on a rope, a voice, a church | a rope that disappears, a bucket that ends up somewhere else, a tiny object (golden ring) as the final picture |
