# Golden Commander QA Matrix v2.1

Purpose: deterministic Commander and Deck Analysis QA focused on composite strategy detection, false-positive avoidance, and reason-builder quality. Expectations are phrased as broad rules rather than commander-specific hacks.

## Coverage Targets

- Enchantments / Auras / Equipment / Voltron
- Artifacts / artifact tokens / artifact recursion
- Graveyard / reanimator / self-mill / discard
- Tokens / sacrifice / aristocrats
- Counters / proliferate / modified
- Lands / landfall / land recursion
- Spellslinger / copy spells / storm-like
- Combat damage / attack triggers / extra combat
- Typal
- Lifegain
- Blink / ETB
- Exile / impulse draw / cast from exile
- Colorless / Eldrazi / high mana value
- Political / donation / goad / forced combat
- Weird restrictions: mana value limits, once-per-turn triggers, only during your turn, from graveyard, cast not copy

## QA Priority

The most important pass/fail signal is not only what the app detects, but what it avoids detecting. A case should fail if the app recommends adjacent cards that look textually similar but do not support the commander's actual strategic plan.

---

# Commander Lookup Cases


## Sythis, Harvest's Hand

Color identity:
- G/W

Expected primary themes:
- enchantment value engine
- enchantress card advantage

Expected secondary themes:
- lifegain support
- low-mana permanent density

Should recommend:
- cheap enchantments and enchantress payoffs, such as Utopia Sprawl or Mesa Enchantress
- protection for a permanent-based engine, such as Sterling Grove or Greater Auramancy

Should avoid:
- generic lifegain without enchantment density
- Aura Voltron packages that assume the commander attacks

Reason quality notes:
- The app should understand that the commander rewards casting enchantments repeatedly, not merely gaining life.
- It must not overclaim that every lifegain card is synergistic unless it also supports the enchantment engine.

Edge-case pressure:
- The commander has lifegain text, but the deck is usually enchantment velocity first and lifegain second.

## Tuvasa the Sunlit

Color identity:
- G/W/U

Expected primary themes:
- enchantment count scaling
- enchantress Voltron

Expected secondary themes:
- card draw from first enchantment each turn
- Aura-based commander damage

Should recommend:
- low-cost Auras that protect or grow the commander, such as Shielded by Faith or All That Glitters
- enchantress effects and enchantment ramp, such as Sanctum Weaver

Should avoid:
- generic creature Voltron with equipment-only packages
- pillow-fort enchantments that do not advance draw, protection, or damage

Reason quality notes:
- The app should connect enchantment density to both card flow and commander damage pressure.
- It must not assume all enchantress decks are noncombat toolbox decks.

Edge-case pressure:
- This is a hybrid enchantress/Voltron case where either side alone can produce bad recommendations.

## Zur the Enchanter

Color identity:
- W/U/B

Expected primary themes:
- enchantment tutor toolbox
- control-oriented enchantment package

Expected secondary themes:
- mana value restriction
- attack-trigger tutoring

Should recommend:
- enchantments with mana value 3 or less that function as removal, protection, or engines, such as Necropotence or Grasp of Fate
- evasion and protection that help Zur attack safely

Should avoid:
- high-mana enchantments that Zur cannot tutor
- generic Esper control cards with no enchantment/toolbox role

Reason quality notes:
- The app should understand the mana value limit on Zur's tutoring.
- It must not recommend enchantments only because they are powerful if they cannot be found by Zur.

Edge-case pressure:
- The commander is often misread as generic enchantress, but the defining pattern is restricted tutoring.

## Go-Shintai of Life's Origin

Color identity:
- W/U/B/R/G

Expected primary themes:
- Shrine enchantment toolbox
- enchantment recursion

Expected secondary themes:
- specific subtype required
- five-color permanent value

Should recommend:
- Shrines and enchantment support that multiply triggered value, such as Sanctum of All
- mana fixing and enchantment recursion, such as Sterling Grove or Replenish

Should avoid:
- generic five-color goodstuff
- typal creature support that ignores Shrines being enchantments

Reason quality notes:
- The app should understand that Shrine density is a subtype constraint inside an enchantment shell.
- It must not treat this as generic typal creature swarm.

Edge-case pressure:
- Shrines are enchantments with a subtype, so both subtype and card type matter.

## Light-Paws, Emperor's Voice

Color identity:
- W

Expected primary themes:
- Aura Voltron
- Aura tutor chain

Expected secondary themes:
- mana value restriction
- commander damage pressure

Should recommend:
- low-cost Auras that protect, give evasion, or scale power, such as Hyena Umbra or Ethereal Armor
- tutor-compatible Auras that keep the chain efficient

Should avoid:
- equipment packages
- high-cost Auras that break the curve or cannot be chained efficiently

Reason quality notes:
- The app should understand that Aura sequencing and mana value restrictions drive recommendations.
- It must not recommend every strong Aura if it weakens the tutor chain.

Edge-case pressure:
- This catches systems that see enchantments but miss commander-damage pressure and MV constraints.

## Sram, Senior Edificer

Color identity:
- W

Expected primary themes:
- low-cost Voltron value
- Aura/Equipment card draw

Expected secondary themes:
- cheap commander engine
- artifact/enchantment cast density

Should recommend:
- cheap Auras and Equipment that replace themselves through Sram, such as Bonesplitter or Sentinel's Eyes
- protection that keeps a small draw engine alive

Should avoid:
- generic artifact recursion
- expensive Equipment packages with no curve support

Reason quality notes:
- The app should explain that Sram turns small equipment/auras into velocity.
- It must not overclaim artifact recursion just because Equipment are artifacts.

Edge-case pressure:
- Equipment are artifacts, but the strategy is low-cost cast density and commander damage, not graveyard loops.

## Wyleth, Soul of Steel

Color identity:
- R/W

Expected primary themes:
- Voltron combat draw
- Aura/Equipment aggression

Expected secondary themes:
- attack-trigger card advantage
- commander damage pressure

Should recommend:
- Auras and Equipment that make attacks safe and profitable, such as Sword of the Animist or All That Glitters
- evasion, protection, and cheap interaction

Should avoid:
- generic Boros token swarm
- combat tricks that do not stay on the commander

Reason quality notes:
- The app should understand that Wyleth draws on attacking while suited up.
- It must not call this combat-damage value; the trigger is attack-based.

Edge-case pressure:
- Attack trigger vs combat damage trigger is the important deterministic distinction.

## Galea, Kindler of Hope

Color identity:
- G/W/U

Expected primary themes:
- top-deck Aura/Equipment value
- Voltron equipment-enchantress hybrid

Expected secondary themes:
- card selection from library top
- commander damage pressure

Should recommend:
- Auras and Equipment with strong board impact, plus top-deck manipulation such as Sensei's Divining Top
- protection/evasion for a suited attacker

Should avoid:
- generic enchantment-only pillow fort
- artifact recursion packages

Reason quality notes:
- The app should understand the commander supports casting equipment/auras from the library top.
- It must not overclaim graveyard or recursion synergy.

Edge-case pressure:
- This hybrid can confuse systems that require one pure Voltron card type.

## Emry, Lurker of the Loch

Color identity:
- U

Expected primary themes:
- artifact recursion
- graveyard artifact value

Expected secondary themes:
- self-mill
- cost reduction from artifacts

Should recommend:
- cheap artifacts that sacrifice or replace themselves, such as Mishra's Bauble or Chromatic Star
- artifact payoff and protection for a graveyard engine

Should avoid:
- generic reanimator for large creatures
- artifact tokens without sacrifice/recursion purpose

Reason quality notes:
- The app should understand Emry casts artifacts from the graveyard.
- It must not call this generic graveyard reanimator.

Edge-case pressure:
- The graveyard matters, but only artifact cards are directly reusable.

## Osgir, the Reconstructor

Color identity:
- R/W

Expected primary themes:
- artifact graveyard reconstruction
- artifact token copies

Expected secondary themes:
- artifact sacrifice setup
- mana value scaling

Should recommend:
- artifacts worth sacrificing and copying, such as Ichor Wellspring or Solemn Simulacrum
- artifact ramp and graveyard setup

Should avoid:
- creature-token go-wide recommendations
- generic Boros equipment Voltron

Reason quality notes:
- The app should connect sacrifice/exile from graveyard to artifact copy value.
- It must not treat all tokens as creature-token swarm.

Edge-case pressure:
- Osgir creates artifact token copies, so token detection must be artifact-aware.

## Mishra, Eminent One

Color identity:
- U/B/R

Expected primary themes:
- artifact copy value
- artifact attack pressure

Expected secondary themes:
- temporary artifact tokens
- artifact count matters

Should recommend:
- artifacts with strong triggered or combat value when copied, such as Combustible Gearhulk or Ichor Wellspring
- ways to protect and recur key artifacts

Should avoid:
- generic artifact recursion as the primary plan
- nonartifact attack-trigger aggro

Reason quality notes:
- The app should understand the commander makes temporary artifact copies for value.
- It must not overclaim graveyard recursion unless the sample supports it.

Edge-case pressure:
- The copy is temporary and attacking, which is different from permanent token swarm.

## Breya, Etherium Shaper

Color identity:
- W/U/B/R

Expected primary themes:
- artifact tokens
- artifact sacrifice control

Expected secondary themes:
- artifact count matters
- sacrifice outlet

Should recommend:
- artifact-token makers and payoffs, such as Thopter Spy Network or Sai, Master Thopterist
- artifact recursion and interaction that use expendable artifacts

Should avoid:
- generic creature aristocrats without artifact support
- Voltron equipment packages

Reason quality notes:
- The app should identify artifact fodder and activated sacrifice utility.
- It must not reduce Breya to generic four-color goodstuff.

Edge-case pressure:
- She is both token maker and outlet, so systems may overweight only one half.

## Urza, Lord High Artificer

Color identity:
- U

Expected primary themes:
- artifact mana engine
- artifact count scaling

Expected secondary themes:
- artifact token creation
- repeatable value engine

Should recommend:
- cheap artifacts and artifact tokens that become mana sources, such as Mox Amber or Thopter Spy Network
- mana sinks and interaction for a large mana engine

Should avoid:
- artifact recursion as primary without graveyard evidence
- Equipment Voltron

Reason quality notes:
- The app should understand artifacts are converted into mana and a Construct scales with artifact count.
- It must not recommend recursion just because the deck has artifacts.

Edge-case pressure:
- This is a key false-positive trap: artifacts does not equal artifact recursion.

## Jan Jansen, Chaos Crafter

Color identity:
- R/W/B

Expected primary themes:
- artifact token conversion
- artifact sacrifice engine

Expected secondary themes:
- treasure_creation
- artifact_token_creation

Should recommend:
- cheap artifact fodder and token doublers, such as Servo Schematic or Mondrak, Glory Dominus
- untap or artifact-synergy pieces that support repeated activation

Should avoid:
- generic aristocrats that only care about creatures dying
- equipment Voltron

Reason quality notes:
- The app should explain the exchange loop between artifact creatures and Treasure.
- It must not recommend sacrifice payoffs that require creature death unless enough creature fodder exists.

Edge-case pressure:
- This pressures distinction between artifact sacrifice, creature death, and Treasure production.

## Magda, Brazen Outlaw

Color identity:
- R

Expected primary themes:
- Treasure engine
- artifact/Dragon tutor

Expected secondary themes:
- specific subtype support
- artifact token creation

Should recommend:
- Dwarves or tapping enablers that create Treasures, such as Springleaf Drum
- artifact and Dragon payoffs that are worth tutoring

Should avoid:
- generic red artifact recursion
- Dragon typal without Treasure support

Reason quality notes:
- The app should understand Treasure quantity enables tutoring.
- It must not treat Magda as only Dwarf typal or only Dragon typal.

Edge-case pressure:
- The commander bridges subtype, artifact tokens, and tutoring.

## Lonis, Cryptozoologist

Color identity:
- G/U

Expected primary themes:
- Clue token value
- creature ETB investigation

Expected secondary themes:
- artifact tokens
- creature-based value

Should recommend:
- cheap creatures that trigger investigate, such as Coiling Oracle or Elvish Visionary
- artifact-token payoffs and ways to use Clues

Should avoid:
- Treasure-specific payoffs with no Clue support
- generic Simic landfall

Reason quality notes:
- The app should recognize Clues as artifact tokens and card-advantage resources.
- It must not collapse all artifact tokens into Treasure.

Edge-case pressure:
- This is the clean artifact-token-but-not-Treasure case.

## Muldrotha, the Gravetide

Color identity:
- B/G/U

Expected primary themes:
- graveyard permanent value
- recursive midrange engine

Expected secondary themes:
- self-mill
- permanent-type diversity

Should recommend:
- self-mill and reusable permanents, such as Satyr Wayfinder or Seal of Primordium
- interaction on permanents that can be recast

Should avoid:
- instant/sorcery flashback packages as the main plan
- single-shot reanimation-only packages

Reason quality notes:
- The app should understand Muldrotha plays permanents from graveyard by type.
- It must not call every graveyard card reanimator support.

Edge-case pressure:
- This catches graveyard value versus reanimator confusion.

## Meren of Clan Nel Toth

Color identity:
- B/G

Expected primary themes:
- creature recursion engine
- sacrifice value

Expected secondary themes:
- death triggers
- experience counters

Should recommend:
- sacrifice outlets and creatures with ETB/death value, such as Viscera Seer or Sakura-Tribe Elder
- graveyard setup that fuels repeatable recursion

Should avoid:
- artifact recursion
- generic self-mill with no creatures to recur

Reason quality notes:
- The app should explain how death, experience counters, and recursion form an engine.
- It must not overclaim aristocrats unless death payoffs are actually present.

Edge-case pressure:
- Meren can be reanimator or aristocrats depending on support cards.

## Karador, Ghost Chieftain

Color identity:
- W/B/G

Expected primary themes:
- creature graveyard recursion
- self-mill value

Expected secondary themes:
- cost reduction
- creature toolbox

Should recommend:
- creatures with ETB utility and self-mill, such as Stitcher's Supplier or Eternal Witness
- sacrifice outlets if the deck wants loops

Should avoid:
- artifact recursion
- spell-slinger graveyard packages

Reason quality notes:
- The app should understand the commander casts creatures from graveyard.
- It must not recommend noncreature graveyard payoffs as if Karador supports them directly.

Edge-case pressure:
- The permanent type restriction is the detection pressure.

## Chainer, Nightmare Adept

Color identity:
- B/R

Expected primary themes:
- discard-to-reanimate
- graveyard haste aggression

Expected secondary themes:
- discard payoff
- graveyard recursion

Should recommend:
- discard outlets and creatures worth recurring, such as Faithless Looting or Archon of Cruelty
- sacrifice outlets that reset reanimated creatures when useful

Should avoid:
- generic Rakdos sacrifice without reanimation
- spell-copy packages

Reason quality notes:
- The app should connect discard as setup, not just card disadvantage.
- It must not overclaim aristocrats from sacrifice pieces alone.

Edge-case pressure:
- The discard signal should support reanimation rather than become madness/hellbent by default.

## Sidisi, Brood Tyrant

Color identity:
- B/G/U

Expected primary themes:
- self-mill creature value
- Zombie token production

Expected secondary themes:
- graveyard setup
- creature token creation

Should recommend:
- creature-heavy self-mill cards, such as Mesmeric Orb or Stitcher's Supplier
- graveyard payoffs that reward creatures entering the graveyard

Should avoid:
- generic Zombie typal swarm
- noncreature spell-mill packages

Reason quality notes:
- The app should understand the deck wants creatures milled to create Zombies and fuel graveyard value.
- It must not treat every Zombie output as typal tribal.

Edge-case pressure:
- This is self-mill token production, not a normal Zombie lord deck.

## Araumi of the Dead Tide

Color identity:
- U/B

Expected primary themes:
- graveyard encore value
- ETB/death reuse

Expected secondary themes:
- self-mill
- mana efficiency

Should recommend:
- creatures with strong ETB/death triggers, such as Gray Merchant of Asphodel or Mulldrifter
- self-mill and protection for a graveyard activation engine

Should avoid:
- generic reanimator that keeps creatures permanently
- artifact recursion

Reason quality notes:
- The app should understand encore creates temporary attacking token copies.
- It must not claim the commander permanently reanimates creatures.

Edge-case pressure:
- Encore combines graveyard, tokens, and combat in a rules-specific way.

## Korvold, Fae-Cursed King

Color identity:
- B/R/G

Expected primary themes:
- sacrifice value engine
- Treasure/token-fueled card draw

Expected secondary themes:
- commander damage pressure
- artifact token creation

Should recommend:
- repeatable fodder and sacrifice sources, such as Dockside Extortionist or Tireless Provisioner
- protection for a large commander engine

Should avoid:
- generic Dragon typal
- combat-only Voltron packages

Reason quality notes:
- The app should understand Korvold rewards sacrificing any permanent.
- It must not treat him as Dragon typal because of creature type.

Edge-case pressure:
- This is a major false-positive trap for typal and generic Jund value.

## Teysa Karlov

Color identity:
- W/B

Expected primary themes:
- aristocrats death-trigger doubling
- token sacrifice value

Expected secondary themes:
- death trigger
- token fodder

Should recommend:
- creature death payoffs and fodder, such as Blood Artist or Requiem Angel
- sacrifice outlets and token makers

Should avoid:
- generic lifegain without death triggers
- artifact sacrifice packages with no creature deaths

Reason quality notes:
- The app should explain death-trigger amplification.
- It must not recommend sacrifice cards unless they feed creature death triggers.

Edge-case pressure:
- Teysa distinguishes creature-death aristocrats from broader sacrifice.

## Elas il-Kor, Sadistic Pilgrim

Color identity:
- W/B

Expected primary themes:
- aristocrats drain
- creature ETB/death life swing

Expected secondary themes:
- lifegain trigger
- death trigger

Should recommend:
- cheap creatures, token fodder, and sacrifice outlets, such as Doomed Traveler or Viscera Seer
- lifegain/drain payoffs that care about repeated small events

Should avoid:
- generic lifegain lifetotal cards with no creature flow
- equipment Voltron

Reason quality notes:
- The app should connect creature entering and dying to drain/lifegain loops.
- It must not call this pure lifegain if the deck lacks lifegain payoffs.

Edge-case pressure:
- This bridges lifegain and aristocrats without being a generic life-total deck.

## Yawgmoth, Thran Physician

Color identity:
- B

Expected primary themes:
- sacrifice control engine
- -1/-1 counter card draw

Expected secondary themes:
- sacrifice outlet
- counter placement

Should recommend:
- undying creatures and expendable creature fodder, such as Young Wolf or Zulaport Cutthroat
- protection for a fragile engine commander

Should avoid:
- generic aristocrats without counter synergy
- proliferate as primary unless poison/counter plan is present

Reason quality notes:
- The app should understand sacrifice is tied to card draw and -1/-1 counters.
- It must not assume all counter decks want proliferate.

Edge-case pressure:
- This is counters but not necessarily proliferate.

## Jadar, Ghoulcaller of Nephalia

Color identity:
- B

Expected primary themes:
- repeatable token fodder
- sacrifice support

Expected secondary themes:
- creature token creation
- death trigger support

Should recommend:
- sacrifice outlets and death payoffs, such as Skullclamp or Bastion of Remembrance
- cards that exploit one disposable Zombie each turn

Should avoid:
- Zombie typal swarm as primary
- artifact-token payoffs

Reason quality notes:
- The app should see the decayed token as recurring fodder.
- It must not overclaim Zombie typal just because the token is a Zombie.

Edge-case pressure:
- This tests token fodder versus typal swarm.

## Chatterfang, Squirrel General

Color identity:
- B/G

Expected primary themes:
- creature token multiplication
- sacrifice removal engine

Expected secondary themes:
- creature token creation
- sacrifice outlet

Should recommend:
- token makers that Chatterfang can multiply, such as Tireless Provisioner or Scute Swarm
- aristocrat or sacrifice payoffs if the sample supports them

Should avoid:
- artifact-token-only engines
- generic Squirrel typal without token production

Reason quality notes:
- The app should understand replacement-style token multiplication.
- It must not recommend Treasure-only payoffs unless Treasures are central.

Edge-case pressure:
- Chatterfang can use Treasures, but the broader strategy is creature-token conversion and sacrifice.

## Ghired, Conclave Exile

Color identity:
- R/G/W

Expected primary themes:
- large token populate
- combat token pressure

Expected secondary themes:
- creature token creation
- attack trigger

Should recommend:
- high-impact creature tokens and populate support, such as Phyrexian Processor or Parallel Lives
- ramp and haste for large-token combat

Should avoid:
- small aristocrat token fodder
- artifact token packages

Reason quality notes:
- The app should understand populate wants meaningful creature tokens to copy.
- It must not treat all token decks as sacrifice fodder decks.

Edge-case pressure:
- This pressures big-token populate versus go-wide aristocrats.

## Adrix and Nev, Twincasters

Color identity:
- G/U

Expected primary themes:
- token doubling value
- creature or artifact token scaling

Expected secondary themes:
- creature token creation
- artifact token creation

Should recommend:
- token makers with strong baseline value, such as Avenger of Zendikar or Tireless Provisioner
- draw/ramp that supports a token engine

Should avoid:
- typal swarm without token creation
- proliferate/counter packages unless sample supports them

Reason quality notes:
- The app should explain that the commander doubles token output regardless of token type.
- It must not assume artifact tokens or creature tokens exclusively without deck evidence.

Edge-case pressure:
- This is a broad token doubler that needs sample context.

## Atraxa, Praetors' Voice

Color identity:
- W/U/B/G

Expected primary themes:
- proliferate engine
- multi-counter value

Expected secondary themes:
- lifelink/keyword body
- planeswalker or poison support

Should recommend:
- cards using counters that scale with proliferate, such as planeswalkers or Evolution Sage
- interaction and ramp for a four-color engine

Should avoid:
- generic +1/+1 counter cards only
- lifegain as primary because Atraxa has lifelink

Reason quality notes:
- The app should understand proliferate needs counter-bearing permanents or players.
- It must not assume a specific Atraxa build without deck evidence.

Edge-case pressure:
- Atraxa is a broad commander; deterministic detection must follow support cards.

## Ezuri, Claw of Progress

Color identity:
- G/U

Expected primary themes:
- experience counter growth
- small-creature +1/+1 counters

Expected secondary themes:
- creature ETB density
- counter placement

Should recommend:
- cheap creatures with power 2 or less, such as Elvish Visionary or Coiling Oracle
- evasive creatures that use Ezuri counters well

Should avoid:
- generic proliferate as primary
- large-creature ramp packages that do not trigger experience

Reason quality notes:
- The app should understand the power restriction for experience counters.
- It must not recommend big creatures just because the deck has counters.

Edge-case pressure:
- Experience counters are player counters, not the same as +1/+1 counter placement.

## Tekuthal, Inquiry Dominus

Color identity:
- U

Expected primary themes:
- proliferate amplification
- counter strategy support

Expected secondary themes:
- counter_type_specific
- repeatable value engine

Should recommend:
- repeatable proliferate and permanents that accumulate counters, such as Everflowing Chalice or Tezzeret's Gambit
- protection for the commander

Should avoid:
- generic +1/+1 counter swarm with no proliferate payoffs
- spell-slinger because of blue instants

Reason quality notes:
- The app should understand Tekuthal doubles proliferate outcomes.
- It must not treat it as a complete archetype without counter-bearing support.

Edge-case pressure:
- The commander is an amplifier, not the original source of all counters.

## Lae'zel, Vlaakith's Champion

Color identity:
- W

Expected primary themes:
- counter amplification
- planeswalker/+1/+1 counter support

Expected secondary themes:
- counter placement
- counter_type_specific

Should recommend:
- cards that place counters on creatures, planeswalkers, or players, such as The Ozolith or Basri Ket
- protection and board development

Should avoid:
- proliferate as primary without proliferate cards
- generic white Voltron

Reason quality notes:
- The app should explain additional-counter replacement logic.
- It must not say Lae'zel proliferates.

Edge-case pressure:
- This is counters but not proliferate.

## Chishiro, the Shattered Blade

Color identity:
- R/G

Expected primary themes:
- modified creature tokens
- Aura/Equipment/counter support

Expected secondary themes:
- equipment_payoff
- counter_placement

Should recommend:
- ways to modify creatures with Auras, Equipment, or counters, such as Rancor or Ring of Valkas
- creature-token and go-wide support that benefits from modification

Should avoid:
- generic Voltron focused only on commander damage
- proliferate as primary

Reason quality notes:
- The app should understand modified includes equipped, enchanted, or countered creatures.
- It must not reduce the deck to Equipment-only or counter-only.

Edge-case pressure:
- Modified is a composite condition that can be satisfied multiple ways.

## Shalai and Hallar

Color identity:
- R/G/W

Expected primary themes:
- +1/+1 counters as damage engine
- counter placement payoff

Expected secondary themes:
- lifegain not primary
- combo potential

Should recommend:
- repeatable +1/+1 counter placement, such as Hardened Scales or Conclave Mentor
- protection for the damage engine

Should avoid:
- generic Naya combat aggro
- proliferate-only packages without counter placement

Reason quality notes:
- The app should connect counter placement to direct damage.
- It must not recommend lifegain just because of colors or bodies.

Edge-case pressure:
- This tests counter placement as win condition, not merely board growth.

## Kodama of the West Tree

Color identity:
- G

Expected primary themes:
- modified creature ramp
- combat damage ramp

Expected secondary themes:
- evasion_needed
- counter/equipment/aura support

Should recommend:
- ways to modify evasive creatures, such as Rancor or Snakeskin Veil
- creature-based ramp and protection

Should avoid:
- generic landfall
- Voltron-only commander damage packages

Reason quality notes:
- The app should understand modified creatures need to connect in combat.
- It must not overclaim landfall because the commander finds lands.

Edge-case pressure:
- This is ramp from combat damage, not lands-matter payoff.

## Omnath, Locus of Creation

Color identity:
- R/G/W/U

Expected primary themes:
- landfall value engine
- multi-land-drop ramp

Expected secondary themes:
- lifegain burst
- mana generation

Should recommend:
- extra land drops and fetch lands, such as Exploration or Fabled Passage
- landfall payoffs and protection for a four-color engine

Should avoid:
- generic Elemental typal
- lifegain as the main plan

Reason quality notes:
- The app should understand multiple landfall thresholds in one turn.
- It must not recommend generic lifegain cards as core synergy.

Edge-case pressure:
- The commander has lifegain, mana, and damage text, but landfall sequencing drives all of it.

## Aesi, Tyrant of Gyre Strait

Color identity:
- G/U

Expected primary themes:
- extra land play value
- landfall card draw

Expected secondary themes:
- ramp
- large_card_draw

Should recommend:
- extra land drops and lands-to-hand effects, such as Azusa, Lost but Seeking or Cultivate
- interaction that protects a six-mana engine

Should avoid:
- generic sea monster typal
- graveyard land recursion unless the deck supports it

Reason quality notes:
- The app should understand Aesi is a lands-matter draw engine.
- It must not overclaim land recursion from landfall alone.

Edge-case pressure:
- This is landfall without needing graveyard loops.

## Tatyova, Benthic Druid

Color identity:
- G/U

Expected primary themes:
- landfall draw/lifegain
- ramp value engine

Expected secondary themes:
- extra_land_play
- large_card_draw

Should recommend:
- extra land drops, ramp spells, and bounce lands, such as Simic Growth Chamber
- ways to convert cards and life into board advantage

Should avoid:
- generic lifegain
- typal Merfolk recommendations

Reason quality notes:
- The app should explain that land ETBs provide draw and life.
- It must not treat Tatyova as Merfolk typal.

Edge-case pressure:
- Creature type is a false-positive trap here.

## The Gitrog Monster

Color identity:
- B/G

Expected primary themes:
- land graveyard value
- land sacrifice draw engine

Expected secondary themes:
- discard_payoff
- land_recursion

Should recommend:
- lands that sacrifice or dredge/self-mill enablers, such as Dakmor Salvage or Life from the Loam
- discard outlets and land recursion

Should avoid:
- generic creature reanimator
- landfall-only ramp with no graveyard use

Reason quality notes:
- The app should connect lands entering the graveyard to card draw.
- It must not call this generic reanimator.

Edge-case pressure:
- This is a lands/graveyard bridge where land card type is essential.

## Lord Windgrace

Color identity:
- B/R/G

Expected primary themes:
- land recursion planeswalker value
- discard lands for advantage

Expected secondary themes:
- land_recursion
- discard_payoff

Should recommend:
- lands with sacrifice value and land recursion, such as Strip Mine or Splendid Reclamation
- ramp and protection for a planeswalker commander

Should avoid:
- generic Jund sacrifice
- creature reanimator

Reason quality notes:
- The app should understand discarding lands and recurring lands are the engine.
- It must not recommend normal discard-matters cards unless they support land recursion.

Edge-case pressure:
- Planeswalker commander plus lands-matter creates classification pressure.

## Titania, Protector of Argoth

Color identity:
- G

Expected primary themes:
- land sacrifice recursion
- Elemental token payoff

Expected secondary themes:
- land_recursion
- creature_token_creation

Should recommend:
- sacrifice lands and land recursion, such as Zuran Orb or Crucible of Worlds
- ways to protect or leverage large Elemental tokens

Should avoid:
- generic Elemental typal
- landfall without lands going to graveyard

Reason quality notes:
- The app should understand lands going to the graveyard are the token trigger.
- It must not recommend Elemental lords as primary support.

Edge-case pressure:
- This is lands-in-graveyard token production, not generic landfall.

## Veyran, Voice of Duality

Color identity:
- U/R

Expected primary themes:
- spellslinger trigger doubling
- magecraft/prowess scaling

Expected secondary themes:
- instant_sorcery_payoff
- copy_spell_payoff

Should recommend:
- cheap instants/sorceries and magecraft payoffs, such as Opt or Storm-Kiln Artist
- protection for a commander-centric spell engine

Should avoid:
- generic Izzet control without cast triggers
- big sorceries with no velocity

Reason quality notes:
- The app should understand Veyran doubles triggered abilities from casting/copying spells.
- It must not claim copied spells are cast.

Edge-case pressure:
- This pressures cast/copy distinction.

## Mizzix of the Izmagnus

Color identity:
- U/R

Expected primary themes:
- experience-counter spell cost reduction
- big spell payoff

Expected secondary themes:
- cost_reduction
- instant_sorcery_payoff

Should recommend:
- instants and sorceries that scale with cost reduction, such as Stroke of Genius or Comet Storm
- cheap interaction to build experience safely

Should avoid:
- creature-based counters/proliferate as primary
- generic storm without cost-scaling

Reason quality notes:
- The app should explain experience counters reduce instant/sorcery costs.
- It must not treat +1/+1 counter support as relevant.

Edge-case pressure:
- Experience counters are player counters and the payoff is spell mana efficiency.

## Zada, Hedron Grinder

Color identity:
- R

Expected primary themes:
- single-target spell copying
- go-wide creature pump/cantrip

Expected secondary themes:
- targeting_payoff
- copy_spell_payoff

Should recommend:
- cheap spells that target only Zada and scale across creatures, such as Expedite or Crimson Wisps
- token makers to increase copy count

Should avoid:
- generic storm cards that do not target creatures
- Voltron combat tricks for only one attacker

Reason quality notes:
- The app should understand that targeting Zada copies spells for each other creature.
- It must not say Zada casts the copies.

Edge-case pressure:
- This is copy-spell payoff tied to targeting and board width.

## Kess, Dissident Mage

Color identity:
- U/B/R

Expected primary themes:
- graveyard spell reuse
- Grixis spellslinger control

Expected secondary themes:
- instant_sorcery_payoff
- graveyard_recursion

Should recommend:
- cheap interaction and high-value instants/sorceries, such as Counterspell or Faithless Looting
- self-mill/discard that stocks spells

Should avoid:
- creature reanimator
- artifact recursion

Reason quality notes:
- The app should understand Kess casts one instant/sorcery from graveyard each turn.
- It must not recommend creature graveyard packages as direct synergy.

Edge-case pressure:
- Graveyard matters, but spell card type is the restriction.

## Kykar, Wind's Fury

Color identity:
- U/R/W

Expected primary themes:
- noncreature spell tokens
- spellslinger sacrifice mana

Expected secondary themes:
- spell_cast_trigger
- creature_token_creation

Should recommend:
- cheap noncreature spells and payoffs for Spirit tokens, such as Skullclamp or Jeskai Ascendancy
- mana sinks or storm-like finishers

Should avoid:
- Spirit typal swarm as primary
- artifact-token Treasure packages

Reason quality notes:
- The app should see noncreature spells making creature tokens that can become mana.
- It must not treat the tokens as artifact Treasures.

Edge-case pressure:
- This is spells-to-creature-tokens-to-mana, a multi-step signal.

## Kalamax, the Stormsire

Color identity:
- G/U/R

Expected primary themes:
- instant-speed copy spells
- tap-state spell payoff

Expected secondary themes:
- instant_speed_play
- copy_spell_payoff

Should recommend:
- instants worth copying and safe ways to tap Kalamax, such as Expansion // Explosion or Springleaf Drum
- protection and interaction to play on opponents' turns

Should avoid:
- sorcery-speed spellslinger packages
- generic Dinosaur typal

Reason quality notes:
- The app should understand the first instant each turn is copied only if Kalamax is tapped.
- It must not ignore timing and tap-state restrictions.

Edge-case pressure:
- This has a 'first instant each turn' condition that simple keyword detection misses.

## Isshin, Two Heavens as One

Color identity:
- R/W/B

Expected primary themes:
- attack-trigger doubling
- combat value engine

Expected secondary themes:
- attack_trigger
- creature_token_creation

Should recommend:
- creatures and enchantments with attack triggers, such as Myriad creatures or Professional Face-Breaker
- combat protection and board development

Should avoid:
- combat-damage triggers as if they double
- generic extra combat without attack-trigger support

Reason quality notes:
- The app should understand Isshin doubles attack triggers, not combat damage triggers.
- It must not recommend cards that trigger only on damage as direct commander synergy.

Edge-case pressure:
- This is one of the most important attack-vs-damage false-positive tests.

## Aurelia, the Warleader

Color identity:
- R/W

Expected primary themes:
- extra combat pressure
- attack-step aggression

Expected secondary themes:
- commander_damage_pressure
- attack_trigger

Should recommend:
- haste, protection, and attack-trigger payoffs that benefit from extra combats, such as Sword of the Animist
- ramp to support a six-mana combat commander

Should avoid:
- generic Boros equipment only if no commander-damage plan exists
- aristocrats sacrifice packages

Reason quality notes:
- The app should explain that extra combat multiplies attack opportunities.
- It must not call Aurelia an attack-trigger doubler.

Edge-case pressure:
- Extra combat is related to attack triggers but is not the same mechanic.

## Edric, Spymaster of Trest

Color identity:
- G/U

Expected primary themes:
- combat-damage card draw
- evasive go-wide tempo

Expected secondary themes:
- combat_damage_trigger
- evasion_needed

Should recommend:
- cheap evasive creatures and extra-turn/tempo support, such as Faerie Seer or Triton Shorestalker
- protection for a draw engine

Should avoid:
- Voltron commander-damage packages
- generic Simic landfall

Reason quality notes:
- The app should understand Edric rewards many creatures dealing combat damage to players.
- It must not recommend single-threat Voltron cards as core support.

Edge-case pressure:
- This is combat damage but not Voltron.

## Marisi, Breaker of the Coil

Color identity:
- R/G/W

Expected primary themes:
- combat-damage goad control
- forced combat pressure

Expected secondary themes:
- combat_damage_trigger
- goad_payoff

Should recommend:
- evasive creatures and combat enablers that reliably deal player damage, such as Whispersilk Cloak
- protection and board-political payoffs

Should avoid:
- Voltron-only commander damage
- generic Naya token swarm with no evasion

Reason quality notes:
- The app should connect combat damage to goad and opponent combat control.
- It must not overclaim extra combat or Voltron.

Edge-case pressure:
- This pressures combat-damage detection plus political/forced-combat identity.

## Karlach, Fury of Avernus

Color identity:
- R

Expected primary themes:
- extra combat attacker
- combat step multiplier

Expected secondary themes:
- attack_trigger
- commander_damage_pressure

Should recommend:
- attack-trigger permanents and ways to keep attackers alive through multiple combats
- ramp and protection for repeated attacks

Should avoid:
- combat-damage draw as primary
- generic red spellslinger

Reason quality notes:
- The app should understand the commander creates an additional combat when attacking for the first time.
- It must not confuse extra combat with attack-trigger doubling.

Edge-case pressure:
- This checks once-per-turn/first-time attack restrictions.

## Winota, Joiner of Forces

Color identity:
- R/W

Expected primary themes:
- attack-trigger creature cheating
- non-Human/Human composition

Expected secondary themes:
- attack_trigger
- specific_subtype_required

Should recommend:
- cheap non-Human attackers and high-impact Humans, such as Ornithopter or Angrath's Marauders
- protection for a fragile attack engine

Should avoid:
- generic Human typal swarm
- equipment Voltron

Reason quality notes:
- The app should understand the deck needs non-Humans to trigger and Humans to hit.
- It must not recommend only one side of the creature-type split.

Edge-case pressure:
- This is typal-adjacent but not generic typal.

## Edgar Markov

Color identity:
- W/B/R

Expected primary themes:
- Vampire typal aggro
- token pressure from eminence

Expected secondary themes:
- specific_subtype_required
- creature_token_creation

Should recommend:
- cheap Vampires and Vampire lords, such as Stromkirk Captain or Captivating Vampire
- draw/protection that sustains aggression

Should avoid:
- generic aristocrats unless death payoffs are present
- non-Vampire token swarm

Reason quality notes:
- The app should understand Vampire spell density matters because of eminence.
- It must not require Edgar to be on battlefield for the token trigger.

Edge-case pressure:
- Eminence is a commander-zone edge case.

## The Ur-Dragon

Color identity:
- W/U/B/R/G

Expected primary themes:
- Dragon typal ramp
- high-mana creature payoff

Expected secondary themes:
- cost_reduction
- attack_trigger

Should recommend:
- Dragon cost reducers and ramp, such as Dragonspeaker Shaman or Urza's Incubator
- card advantage and protection for expensive threats

Should avoid:
- generic five-color goodstuff
- small creature typal swarm

Reason quality notes:
- The app should explain cost reduction for Dragons and attack payoff.
- It must not recommend non-Dragon big creatures as primary support.

Edge-case pressure:
- This is typal plus high-mana-value construction pressure.

## Miirym, Sentinel Wyrm

Color identity:
- G/U/R

Expected primary themes:
- Dragon ETB copy tokens
- typal high-impact creatures

Expected secondary themes:
- specific_subtype_required
- creature_token_creation

Should recommend:
- Dragons with strong ETB or attack effects, such as Terror of the Peaks
- ramp and protection for a six-mana commander

Should avoid:
- generic token doublers without Dragon density
- non-Dragon clone packages as primary

Reason quality notes:
- The app should understand Miirym copies nontoken Dragons entering.
- It must not recommend token swarm cards that do not involve Dragons.

Edge-case pressure:
- This is typal plus token copying, not generic tokens.

## Wilhelt, the Rotcleaver

Color identity:
- U/B

Expected primary themes:
- Zombie sacrifice value
- decayed token replacement

Expected secondary themes:
- death_trigger
- specific_subtype_required

Should recommend:
- Zombies that benefit from dying and sacrifice outlets, such as Gravecrawler or Carrion Feeder
- Zombie lords only when they support the sacrifice/token plan

Should avoid:
- generic Zombie combat swarm only
- artifact aristocrats

Reason quality notes:
- The app should understand nontoken Zombies dying create decayed Zombie fodder.
- It must not overprioritize generic Zombie lords over sacrifice engines.

Edge-case pressure:
- Typal and aristocrats overlap, but the death loop is the key.

## Lathril, Blade of the Elves

Color identity:
- B/G

Expected primary themes:
- Elf typal go-wide
- combat damage token production

Expected secondary themes:
- specific_subtype_required
- combat_damage_trigger

Should recommend:
- Elf ramp/lords and evasion/protection for Lathril, such as Elvish Archdruid or Timberwatch Elf
- ways to tap ten Elves profitably

Should avoid:
- generic Golgari sacrifice as primary
- Voltron without Elf board support

Reason quality notes:
- The app should connect Elf count to the activated drain condition.
- It must not treat Lathril as only commander-damage Voltron.

Edge-case pressure:
- Combat damage makes tokens, but Elf density completes the plan.

## Giada, Font of Hope

Color identity:
- W

Expected primary themes:
- Angel typal ramp
- counter-scaling Angels

Expected secondary themes:
- specific_subtype_required
- counter_placement

Should recommend:
- Angels across the curve and protection/ramp, such as Righteous Valkyrie or Youthful Valkyrie
- card draw that supports expensive Angels

Should avoid:
- generic lifegain as primary
- +1/+1 counter proliferate decks

Reason quality notes:
- The app should understand Giada ramps only for Angels and adds counters to Angels.
- It must not call the deck proliferate just because counters appear.

Edge-case pressure:
- This is typal with counters, not a counters archetype by default.

## Krenko, Mob Boss

Color identity:
- R

Expected primary themes:
- Goblin typal token multiplication
- go-wide combat/combo

Expected secondary themes:
- specific_subtype_required
- creature_token_creation

Should recommend:
- Goblin density, haste, and untap support, such as Skirk Prospector or Thousand-Year Elixir
- card draw and protection for a tap engine

Should avoid:
- generic red tokens without Goblins
- artifact-token Treasure packages

Reason quality notes:
- The app should understand Goblin count scales Krenko's output.
- It must not recommend generic token cards that ignore Goblin type.

Edge-case pressure:
- The tap activation and subtype count both matter.

## Oloro, Ageless Ascetic

Color identity:
- W/U/B

Expected primary themes:
- lifegain control
- life-total payoff

Expected secondary themes:
- life_total_payoff
- large_card_draw

Should recommend:
- lifegain payoffs and control tools, such as Well of Lost Dreams or Sanguine Bond
- pillow-fort and interaction to leverage passive life

Should avoid:
- aggressive lifegain Voltron
- generic Esper control without life payoff

Reason quality notes:
- The app should understand Oloro gains life from the command zone.
- It must not require attack/combat support.

Edge-case pressure:
- Command-zone passive value is an edge case for deterministic detection.

## Heliod, Sun-Crowned

Color identity:
- W

Expected primary themes:
- lifegain counters engine
- life-trigger combo

Expected secondary themes:
- lifegain_trigger
- counter_placement

Should recommend:
- repeatable lifegain sources and counter payoffs, such as Soul Warden or Walking Ballista
- protection for enchantment/creature combo pieces

Should avoid:
- generic +1/+1 counters without lifegain
- white weenie aggro

Reason quality notes:
- The app should connect lifegain events to +1/+1 counter placement.
- It must not call this proliferate unless proliferate cards are present.

Edge-case pressure:
- This is lifegain plus counters, not generic counters.

## Dina, Soul Steeper

Color identity:
- B/G

Expected primary themes:
- lifegain drain payoff
- sacrifice support

Expected secondary themes:
- lifegain_trigger
- sacrifice_outlet

Should recommend:
- repeatable lifegain and life-drain payoffs, such as Essence Warden or Exquisite Blood
- token/fodder support if using Dina's sacrifice ability

Should avoid:
- generic aristocrats without lifegain
- landfall unless lifegain lands are present

Reason quality notes:
- The app should understand opponent life loss is triggered by your lifegain.
- It must not recommend sacrifice pieces as primary unless the deck has fodder.

Edge-case pressure:
- Dina has a sacrifice outlet, but the central payoff is lifegain-drain.

## Vito, Thorn of the Dusk Rose

Color identity:
- B

Expected primary themes:
- lifegain drain finisher
- life-total swing combo

Expected secondary themes:
- lifegain_trigger
- major_payoff_text

Should recommend:
- large or repeatable lifegain sources, such as Exquisite Blood or Gray Merchant of Asphodel
- protection and tutors for a fragile payoff creature

Should avoid:
- generic Vampire typal
- aristocrats without lifegain

Reason quality notes:
- The app should connect lifegain to opponent life loss.
- It must not infer Vampire typal from creature type alone.

Edge-case pressure:
- This is a typal false-positive trap.

## Lathiel, the Bounteous Dawn

Color identity:
- G/W

Expected primary themes:
- lifegain counter placement
- go-wide counter growth

Expected secondary themes:
- lifegain_trigger
- counter_placement

Should recommend:
- large lifegain bursts and creatures that use counters well, such as Archangel of Thune or Well of Lost Dreams
- protection and board presence

Should avoid:
- generic Selesnya counters without lifegain
- Horse typal

Reason quality notes:
- The app should understand counters are placed at end step based on life gained.
- It must not recommend proliferate as primary unless the deck includes it.

Edge-case pressure:
- This is lifegain-to-counters, not counters alone.

## Brago, King Eternal

Color identity:
- W/U

Expected primary themes:
- combat-damage blink engine
- ETB permanent value

Expected secondary themes:
- combat_damage_trigger
- repeatable_value_engine

Should recommend:
- ETB permanents and ways to make Brago connect, such as Strionic Resonator or Mulldrifter
- protection/evasion for a combat-damage engine

Should avoid:
- Voltron commander damage
- generic Azorius control with no ETB density

Reason quality notes:
- The app should understand combat damage unlocks blink value.
- It must not recommend damage payoffs that do not help blinking.

Edge-case pressure:
- Combat damage is a trigger condition, but the payoff is blink.

## Yorion, Sky Nomad

Color identity:
- W/U

Expected primary themes:
- mass blink value
- ETB permanent reset

Expected secondary themes:
- repeatable_value_engine
- blink_etb_value

Should recommend:
- ETB creatures/enchantments/artifacts and value permanents, such as Omen of the Sea or Solemn Simulacrum
- ramp and interaction to support a five-mana reset

Should avoid:
- graveyard recursion
- Voltron

Reason quality notes:
- The app should understand mass exile-and-return of owned nonland permanents.
- It must not confuse blink with bounce or reanimation.

Edge-case pressure:
- Yorion's companion history should not affect commander QA logic.

## Roon of the Hidden Realm

Color identity:
- G/W/U

Expected primary themes:
- targeted blink toolbox
- ETB creature value

Expected secondary themes:
- repeatable_value_engine
- instant_speed_play

Should recommend:
- ETB creatures and untap/protection support, such as Eternal Witness or Seedborn Muse
- ramp for an activated ability commander

Should avoid:
- generic Bant goodstuff
- flicker cards that only save the commander but do not advance ETB value

Reason quality notes:
- The app should understand repeatable targeted flicker.
- It must not call this landfall because of Bant colors or ramp cards.

Edge-case pressure:
- This is a color false-positive trap.

## Aminatou, the Fateshifter

Color identity:
- W/U/B

Expected primary themes:
- blink/control planeswalker value
- top-deck manipulation

Expected secondary themes:
- card_selection
- repeatable_value_engine

Should recommend:
- ETB permanents and top-deck manipulation, such as Oath of Teferi or Ponder
- protection for a planeswalker commander

Should avoid:
- generic Esper control without blink support
- miracle-only packages unless sample supports them

Reason quality notes:
- The app should connect flicker ability with ETB permanents and planeswalker support.
- It must not overclaim miracle/topdeck themes from one ability.

Edge-case pressure:
- Planeswalker commander and blink overlap can confuse simple creature-centric logic.

## Preston, the Vanisher

Color identity:
- W

Expected primary themes:
- blink token copies
- nontoken creature ETB abuse

Expected secondary themes:
- creature_token_creation
- blink_etb_value

Should recommend:
- blink effects and nontoken creatures with ETBs, such as Ephemerate or Wall of Omens
- sacrifice/value outlets for Illusion copies if supported

Should avoid:
- generic token swarm
- artifact-token support

Reason quality notes:
- The app should understand Preston creates token copies from nontoken creatures entering without being cast.
- It must not recommend normal token doublers as the whole plan.

Edge-case pressure:
- The trigger condition is unusual and easy to overgeneralize.

## Prosper, Tome-Bound

Color identity:
- B/R

Expected primary themes:
- cast from exile value
- Treasure engine

Expected secondary themes:
- treasure_creation
- impulse_draw

Should recommend:
- impulse draw and cast-from-exile payoffs, such as Light Up the Stage or Jeska's Will
- Treasure payoff and interaction

Should avoid:
- generic artifact recursion
- discard/reanimator Rakdos packages

Reason quality notes:
- The app should understand Prosper cares about playing cards from exile and makes Treasures.
- It must not treat Treasure as the only strategy.

Edge-case pressure:
- This is exile-casting plus artifact tokens, not artifact recursion.

## Faldorn, Dread Wolf Herald

Color identity:
- R/G

Expected primary themes:
- cast from exile token generation
- impulse-draw creature tokens

Expected secondary themes:
- impulse_draw
- creature_token_creation

Should recommend:
- exile-cast effects and impulse draw, such as Reckless Impulse or Escape to the Wilds
- token payoffs and protection

Should avoid:
- generic Gruul combat with no exile-cast support
- Wolf typal as primary

Reason quality notes:
- The app should understand Wolf tokens come from casting from exile.
- It must not infer Wolf typal just because Wolves are created.

Edge-case pressure:
- This tests typal false positives and exile-cast detection.

## Pia Nalaar, Consul of Revival

Color identity:
- R/W

Expected primary themes:
- cast from exile Thopter tokens
- impulse-draw token aggression

Expected secondary themes:
- impulse_draw
- artifact_token_creation

Should recommend:
- red impulse draw and exile-cast enablers, such as Wrenn's Resolve or Chandra, Dressed to Kill
- artifact-token payoffs if Thopters matter

Should avoid:
- generic artifact recursion
- Vehicle/artifact goodstuff without exile casting

Reason quality notes:
- The app should understand Thopters are artifact creature tokens from exile-casting.
- It must not recommend artifact recursion unless graveyard support exists.

Edge-case pressure:
- This is artifact tokens but not artifact recursion.

## Laelia, the Blade Reforged

Color identity:
- R

Expected primary themes:
- impulse attack value
- exile-count commander growth

Expected secondary themes:
- attack_trigger
- impulse_draw

Should recommend:
- impulse draw and ways to attack safely, such as Chandra's Phoenix support or Rogue's Passage
- extra combat/protection if pursuing commander damage

Should avoid:
- generic red Voltron only
- discard-matters strategies

Reason quality notes:
- The app should connect exile events to +1/+1 counters on Laelia.
- It must not assume all exile effects are cast-from-exile payoffs unless the cards are playable.

Edge-case pressure:
- This mixes attack impulse draw with exile-count growth.

## Narset, Enlightened Exile

Color identity:
- U/R/W

Expected primary themes:
- noncreature spell recursion from graveyard
- Prowess-wide combat

Expected secondary themes:
- instant_sorcery_payoff
- combat_damage_trigger

Should recommend:
- noncreature spell density and cheap interaction, such as Opt or Boros Charm
- creatures that benefit from prowess-wide buffs

Should avoid:
- creature reanimator
- Voltron-only Jeskai equipment

Reason quality notes:
- The app should understand Narset grants prowess and casts noncreature spells from graveyard on attack.
- It must not claim copied/recast spells are free if restrictions apply.

Edge-case pressure:
- This bridges combat, spells, and graveyard without being normal reanimator.

## Kozilek, the Great Distortion

Color identity:
- C

Expected primary themes:
- colorless big-mana finisher
- hand-refill control

Expected secondary themes:
- high_mana_value_commander
- colorless_mana_scaling

Should recommend:
- colorless ramp and utility lands, such as Thran Dynamo or Ancient Tomb
- protection and interaction that work in colorless

Should avoid:
- artifact recursion as primary
- Eldrazi typal swarm only

Reason quality notes:
- The app should understand the deck needs heavy colorless ramp to cast a ten-mana commander.
- It must not recommend colored cards or colored activation costs.

Edge-case pressure:
- Colorless identity is a construction constraint and recommendation filter.

## Zhulodok, Void Gorger

Color identity:
- C

Expected primary themes:
- high-mana colorless cascade
- Eldrazi/big spell payoff

Expected secondary themes:
- colorless_mana_scaling
- high_mana_value_commander

Should recommend:
- colorless ramp and expensive colorless spells, such as Basalt Monolith or Ulamog, the Ceaseless Hunger
- top-end threat density

Should avoid:
- low-curve artifact aggro
- colored Eldrazi support

Reason quality notes:
- The app should understand the mana value seven-plus condition.
- It must not recommend cheap artifacts as synergy unless they ramp into the plan.

Edge-case pressure:
- This tests high-MV threshold logic.

## Kozilek, Butcher of Truth

Color identity:
- C

Expected primary themes:
- colorless high-mana threat
- cast-trigger card draw

Expected secondary themes:
- high_mana_value_commander
- large_card_draw

Should recommend:
- fast colorless ramp and protection, such as Sol Ring or Lightning Greaves
- big-mana support and utility lands

Should avoid:
- graveyard recursion; Kozilek reshuffles graveyards
- artifact-token swarm

Reason quality notes:
- The app should understand the draw is on cast and the commander reshuffles graveyards.
- It must not suggest reanimation as the main plan.

Edge-case pressure:
- Cast trigger and graveyard shuffle both matter.

## Liberator, Urza's Battlethopter

Color identity:
- C

Expected primary themes:
- colorless flash tempo
- artifact/colorless counter growth

Expected secondary themes:
- flash_timing
- counter_placement

Should recommend:
- colorless spells and artifacts that benefit from flash timing, such as Mystic Forge or Foundry Inspector
- protection and instant-speed interaction available to colorless

Should avoid:
- generic artifact recursion
- big Eldrazi ramp as the only plan

Reason quality notes:
- The app should understand colorless spells can be cast as though they had flash.
- It must not classify every colorless commander as Eldrazi ramp.

Edge-case pressure:
- This is a colorless tempo/counters edge case.

## Traxos, Scourge of Kroog

Color identity:
- C

Expected primary themes:
- historic artifact aggression
- colorless Voltron-adjacent pressure

Expected secondary themes:
- equipment_payoff
- artifact_count_matters

Should recommend:
- cheap historic spells and untap support, such as Mox Amber or Voltaic Key
- equipment/protection if commander damage is the plan

Should avoid:
- artifact recursion as primary
- Eldrazi big-mana

Reason quality notes:
- The app should understand historic spells untap Traxos.
- It must not recommend graveyard artifact loops without recursion text.

Edge-case pressure:
- This tests artifact presence versus artifact recursion.

## Zedruu the Greathearted

Color identity:
- U/R/W

Expected primary themes:
- donation politics
- life/card advantage from opponents controlling your permanents

Expected secondary themes:
- donation_payoff
- life_total_payoff

Should recommend:
- safe donation targets and political control pieces, such as Steel Golem or Illusions of Grandeur
- protection and interaction

Should avoid:
- generic group hug without donation payoff
- Voltron

Reason quality notes:
- The app should understand ownership/control distinction.
- It must not recommend cards that help opponents unless they create a controlled donation advantage.

Edge-case pressure:
- Donation is a rules-heavy political strategy.

## Blim, Comedic Genius

Color identity:
- B/R

Expected primary themes:
- bad-permanent donation
- combat-damage discard/life loss

Expected secondary themes:
- donation_payoff
- combat_damage_trigger

Should recommend:
- harmful permanents to donate and evasion/protection, such as Demonic Pact or Bronze Bombshell
- ways to ensure combat damage connects

Should avoid:
- generic Rakdos discard
- aristocrats sacrifice

Reason quality notes:
- The app should connect donated permanents to combat-damage punishment.
- It must not suggest normal discard payoffs unless donation/combat support exists.

Edge-case pressure:
- This mixes donation and combat damage, not generic discard.

## The Beamtown Bullies

Color identity:
- B/R/G

Expected primary themes:
- opponent reanimation politics
- temporary drawback abuse

Expected secondary themes:
- temporary_drawback_abuse
- graveyard_recursion

Should recommend:
- creatures with severe drawbacks or end-step consequences, such as Leveler or Eater of Days
- graveyard setup and political protection

Should avoid:
- normal reanimator fatties for your own board
- generic Jund sacrifice

Reason quality notes:
- The app should understand the commander gives creatures from your graveyard to opponents temporarily.
- It must not recommend normal reanimator targets as if you keep them.

Edge-case pressure:
- This is one of the strongest anti-hack QA cases.

## Inniaz, the Gale Force

Color identity:
- W/U

Expected primary themes:
- flying combat exchange
- political permanent redistribution

Expected secondary themes:
- combat_damage_trigger
- donation_payoff

Should recommend:
- flying creature density and cards that benefit from exchange politics
- protection and evasion support

Should avoid:
- generic Azorius flyers typal only
- blink ETB value

Reason quality notes:
- The app should understand combat damage enables control exchange among players.
- It must not call every flyer deck typal.

Edge-case pressure:
- Permanent exchange is not the same as donation or theft alone.

## Karazikar, the Eye Tyrant

Color identity:
- B/R

Expected primary themes:
- forced combat card draw
- opponent attack incentives

Expected secondary themes:
- forced_combat
- goad_payoff

Should recommend:
- goad/forced combat support and defensive tools, such as Disrupt Decorum or No Mercy
- political protection and card draw support

Should avoid:
- Rakdos sacrifice
- Voltron

Reason quality notes:
- The app should understand the commander incentivizes opponents to attack each other.
- It must not treat this as normal aggro.

Edge-case pressure:
- The payoff depends on opponents' combat choices.

## Kardur, Doomscourge

Color identity:
- B/R

Expected primary themes:
- forced combat drain
- ETB goad-like control

Expected secondary themes:
- forced_combat
- lifegain_trigger

Should recommend:
- blink/recur effects for Kardur's ETB and defensive drain payoffs, such as Conjurer's Closet or Deadly Dispute
- interaction that survives opponent combat

Should avoid:
- generic Demon typal
- aristocrats as primary without death-loop support

Reason quality notes:
- The app should understand Kardur redirects opponents' attacks and drains when attacking creatures die.
- It must not overclaim sacrifice synergy from death events alone.

Edge-case pressure:
- Forced combat plus death drain can mimic aristocrats but plays differently.

## Hinata, Dawn-Crowned

Color identity:
- U/R/W

Expected primary themes:
- target-based cost reduction
- target-heavy spellslinger

Expected secondary themes:
- targeting_payoff
- cost_reduction

Should recommend:
- spells with many targets or modal target scaling, such as Magma Opus or Comet Storm
- protection and interaction

Should avoid:
- generic storm cantrips with no targeting
- Voltron

Reason quality notes:
- The app should understand cost changes scale with number of targets.
- It must not recommend spells just because they are instants/sorceries.

Edge-case pressure:
- Targeting count is the key restriction.

## Obeka, Brute Chronologist

Color identity:
- U/B/R

Expected primary themes:
- end-the-turn abuse
- temporary drawback protection

Expected secondary themes:
- temporary_drawback_abuse
- instant_speed_play

Should recommend:
- cards with delayed sacrifice/exile drawbacks, such as Final Fortune or Sneak Attack
- ways to give haste/protection and choose timing carefully

Should avoid:
- generic Grixis control
- normal sacrifice/aristocrats

Reason quality notes:
- The app should understand ending the turn can skip delayed triggers.
- It must not claim Obeka removes all drawbacks permanently without timing context.

Edge-case pressure:
- Turn-ending rules are subtle and easy to overstate.

## Gyruda, Doom of Depths

Color identity:
- U/B

Expected primary themes:
- even mana value restriction
- mill/reanimate clone chain

Expected secondary themes:
- mana_value_restriction
- graveyard_recursion

Should recommend:
- even-mana creatures and clone effects, such as Spark Double or Sakashima the Impostor
- ramp that respects deckbuilding restriction if companion-style

Should avoid:
- odd mana value staples
- generic reanimator without MV filtering

Reason quality notes:
- The app should understand even mana value restrictions and ETB mill/reanimate.
- It must not recommend off-restriction cards in restricted builds.

Edge-case pressure:
- Mana value parity is a deterministic deckbuilding constraint.

## Keruga, the Macrosage

Color identity:
- G/U

Expected primary themes:
- high-mana-value restriction
- ETB card draw payoff

Expected secondary themes:
- mana_value_restriction
- large_card_draw

Should recommend:
- mana acceleration that fits restrictions and permanents with mana value 3+, such as Cultivate or Kiora's Follower
- blink/bounce only if it reuses Keruga's ETB

Should avoid:
- cheap one- and two-mana staples if using restriction
- generic Simic landfall

Reason quality notes:
- The app should understand Keruga rewards permanents with mana value 3 or greater.
- It must not blindly recommend cheap staples when the restriction is active.

Edge-case pressure:
- Deckbuilding restriction and ETB payoff can conflict with normal curve advice.

## Obosh, the Preypiercer

Color identity:
- B/R

Expected primary themes:
- odd mana value damage amplification
- restricted aggressive damage

Expected secondary themes:
- mana_value_restriction
- major_payoff_text

Should recommend:
- odd-mana damage sources and aggressive permanents, such as Torbran, Thane of Red Fell or Lightning Bolt if legal in commander deck constraints
- ramp/interaction that respects odd MV if companion-style

Should avoid:
- even mana value staples in restricted lists
- generic Rakdos sacrifice

Reason quality notes:
- The app should understand odd mana value sources get damage doubled.
- It must not recommend cards that violate the intended restriction if the deck is built around it.

Edge-case pressure:
- Odd/even MV logic is a direct false-positive test.

## Yuriko, the Tiger's Shadow

Color identity:
- U/B

Expected primary themes:
- combat-damage topdeck drain
- Ninja evasive tempo

Expected secondary themes:
- combat_damage_trigger
- specific_subtype_required

Should recommend:
- cheap evasive enablers, Ninjas, and top-deck manipulation, such as Ornithopter or Brainstorm
- interaction that preserves tempo

Should avoid:
- generic Ninja typal without evasive enablers
- Voltron commander-damage packages

Reason quality notes:
- The app should understand ninjutsu enables Yuriko and topdeck mana value matters.
- It must not recommend high-MV cards without considering castability/topdeck plan.

Edge-case pressure:
- This is typal-adjacent and combat-damage, but not Voltron.

## Grist, the Hunger Tide

Color identity:
- B/G

Expected primary themes:
- planeswalker commander graveyard tokens
- Insect/self-mill sacrifice

Expected secondary themes:
- self_mill
- creature_token_creation

Should recommend:
- Insects, self-mill, and sacrifice support, such as Skullclamp or Old Rutstein
- protection for a planeswalker commander

Should avoid:
- generic planeswalker superfriends
- generic Insect typal swarm

Reason quality notes:
- The app should understand Grist is a planeswalker that can be commander because of its characteristic-defining ability.
- It must not assume every commander is a creature on the battlefield.

Edge-case pressure:
- This is a noncreature commander edge case.

---

# Deck Analysis Cases


## Deck Case: Sythis, Harvest's Hand - Enchantress Value

Commander:
- Sythis, Harvest's Hand

Deck sample:
- Utopia Sprawl
- Wild Growth
- Sterling Grove
- Enchantress's Presence
- Mesa Enchantress
- Argothian Enchantress
- Sanctum Weaver
- Setessan Champion
- Destiny Spinner
- Kenrith's Transformation
- Darksteel Mutation
- Grasp of Fate
- Seal of Primordium
- Solitary Confinement
- Greater Auramancy
- Ethereal Armor
- All That Glitters
- Hall of Heliod's Generosity
- Sigil of the Empty Throne
- Replenish

Expected deck themes:
- enchantment value engine
- enchantment toolbox interaction

Expected missing pieces:
- creature removal if the list lacks enchantment-based answers
- protection for key enchantress engines

Should recommend:
- cheap enchantments that replace themselves or solve problems
- enchantress payoffs and enchantment recursion

Should avoid:
- generic lifegain
- Aura Voltron cards that only increase commander damage

Reason quality notes:
- Deck Analysis must say the sample is enchantment-density driven. It should not claim lifegain is the primary strategy just because Sythis gains life.

## Deck Case: Light-Paws, Emperor's Voice - Aura Voltron

Commander:
- Light-Paws, Emperor's Voice

Deck sample:
- Ethereal Armor
- All That Glitters
- Hyena Umbra
- Spider Umbra
- Sentinel's Eyes
- Cartouche of Solidarity
- Spirit Mantle
- Shielded by Faith
- Timely Ward
- Sage's Reverie
- Daybreak Coronet
- Karametra's Blessing
- Sejiri Shelter
- Loran's Escape
- Open the Armory
- Kor Spiritdancer
- Sram, Senior Edificer
- Retether
- Hall of Heliod's Generosity
- Rogue's Passage

Expected deck themes:
- Aura Voltron
- Aura tutor sequencing

Expected missing pieces:
- spot removal
- backup threat if Light-Paws is repeatedly removed

Should recommend:
- low-cost Auras with protection, evasion, or scaling power
- Aura tutors and protection spells

Should avoid:
- Equipment Voltron as the main package
- high-mana Auras that do not fit tutor sequencing

Reason quality notes:
- Deck Analysis must understand mana value/tutor-chain restrictions. It should not recommend generic enchantress pillow-fort cards over efficient Auras.

## Deck Case: Urza, Lord High Artificer - Artifact Mana Engine

Commander:
- Urza, Lord High Artificer

Deck sample:
- Mishra's Bauble
- Urza's Bauble
- Mox Amber
- Everflowing Chalice
- Sol Ring
- Arcane Signet
- Mind Stone
- Thought Vessel
- Sensei's Divining Top
- Mystic Forge
- The One Ring
- Sai, Master Thopterist
- Thought Monitor
- Thoughtcast
- Whir of Invention
- Fabricate
- Pithing Needle
- Tormod's Crypt
- Aetherflux Reservoir
- Karn, the Great Creator

Expected deck themes:
- artifact count mana engine
- artifact value/control

Expected missing pieces:
- ways to protect Urza
- win condition clarity if the list is only mana rocks

Should recommend:
- cheap artifacts that increase mana output through Urza
- artifact payoffs and card selection

Should avoid:
- artifact recursion as primary without graveyard artifacts
- Equipment Voltron

Reason quality notes:
- Deck Analysis must say artifacts function as mana with Urza. It must not infer recursion simply from artifact density.

## Deck Case: Emry, Lurker of the Loch - Artifact Recursion

Commander:
- Emry, Lurker of the Loch

Deck sample:
- Mishra's Bauble
- Urza's Bauble
- Chromatic Star
- Chromatic Sphere
- Ichor Wellspring
- Aether Spellbomb
- Nihil Spellbomb
- Lotus Petal
- Mox Amber
- Sai, Master Thopterist
- Thought Monitor
- Thoughtcast
- Mirrodin Besieged
- Grinding Station
- Mesmeric Orb
- Codex Shredder
- Mystic Forge
- Buried Ruin
- Academy Ruins
- Counterspell

Expected deck themes:
- artifact recursion
- self-mill artifact value

Expected missing pieces:
- protection for Emry
- graveyard protection against exile

Should recommend:
- cheap sacrifice artifacts that are good to recast
- artifact-graveyard protection and recursion payoffs

Should avoid:
- generic creature reanimator
- artifact-token-only payoffs with no recursion role

Reason quality notes:
- Deck Analysis must distinguish artifacts in graveyard from generic graveyard decks. It should explain why reusable artifacts fit.

## Deck Case: Magda, Brazen Outlaw - Treasure Tutor Engine

Commander:
- Magda, Brazen Outlaw

Deck sample:
- Universal Automaton
- Changeling Outcast
- Dwarven Mine
- Seven Dwarves
- Vault Robber
- Axgard Cavalry
- Springleaf Drum
- Relic of Legends
- Clock of Omens
- Liquimetal Torque
- Professional Face-Breaker
- Goldspan Dragon
- Xorn
- Academy Manufactor
- Maskwood Nexus
- Skullclamp
- Lightning Greaves
- Portal to Phyrexia
- Blightsteel Colossus
- Hellkite Tyrant

Expected deck themes:
- Treasure engine
- artifact/Dragon tutor

Expected missing pieces:
- consistent Dwarf/tap enablers if the sample is top-heavy
- interaction

Should recommend:
- Dwarves or changelings that create Treasures through tapping
- high-impact artifacts or Dragons worth tutoring

Should avoid:
- Dragon typal without Treasure production
- generic red artifact recursion

Reason quality notes:
- Deck Analysis must say Treasure count enables tutoring. It should not treat Magda as only Dragon typal.

## Deck Case: Meren of Clan Nel Toth - Sacrifice Recursion

Commander:
- Meren of Clan Nel Toth

Deck sample:
- Viscera Seer
- Carrion Feeder
- Yawgmoth, Thran Physician
- Sakura-Tribe Elder
- Satyr Wayfinder
- Stitcher's Supplier
- Spore Frog
- Plaguecrafter
- Merciless Executioner
- Eternal Witness
- Reclamation Sage
- Solemn Simulacrum
- Blood Artist
- Zulaport Cutthroat
- Bastion of Remembrance
- Victimize
- Living Death
- Phyrexian Reclamation
- Skullclamp
- Bojuka Bog

Expected deck themes:
- creature recursion
- sacrifice value

Expected missing pieces:
- artifact/enchantment removal if not enough ETB answers
- protection for graveyard against exile

Should recommend:
- creatures with ETB/death utility
- sacrifice outlets and recursive value pieces

Should avoid:
- artifact recursion
- reanimator targets that do nothing when sacrificed or recurred

Reason quality notes:
- Deck Analysis must distinguish recursive creature value from pure aristocrats. It should not call death-drain primary unless enough drain payoffs are present.

## Deck Case: Yawgmoth, Thran Physician - Sacrifice Counters, Not Proliferate

Commander:
- Yawgmoth, Thran Physician

Deck sample:
- Young Wolf
- Strangleroot Geist
- Butcher Ghoul
- Geralf's Messenger
- Blood Artist
- Zulaport Cutthroat
- Doomed Dissenter
- Nested Shambler
- Pawn of Ulamog
- Pitiless Plunderer
- Skullclamp
- Mikaeus, the Unhallowed
- Nest of Scarabs
- Soul Snuffers
- Toxic Deluge
- Reanimate
- Victimize
- Cabal Coffers
- Urborg, Tomb of Yawgmoth
- Malakir Rebirth

Expected deck themes:
- sacrifice control engine
- -1/-1 counter card draw

Expected missing pieces:
- protection for Yawgmoth
- redundant sacrifice outlets if commander is removed

Should recommend:
- undying creatures and expendable fodder
- life management and protection

Should avoid:
- generic proliferate packages
- counter decks that only place +1/+1 counters

Reason quality notes:
- Deck Analysis must identify counters but avoid treating the deck as proliferate. The counter type and sacrifice outlet matter.

## Deck Case: Atraxa, Praetors' Voice - Proliferate Superfriends

Commander:
- Atraxa, Praetors' Voice

Deck sample:
- Sol Ring
- Arcane Signet
- Farseek
- Evolution Sage
- Inexorable Tide
- Flux Channeler
- Deepglow Skate
- Tezzeret's Gambit
- Vraska, Betrayal's Sting
- Tamiyo, Field Researcher
- Narset, Parter of Veils
- Teferi, Hero of Dominaria
- The Chain Veil
- Oath of Nissa
- Oath of Teferi
- Doubling Season
- Vorinclex, Monstrous Raider
- Swords to Plowshares
- Cyclonic Rift
- Heroic Intervention

Expected deck themes:
- proliferate
- planeswalker counters

Expected missing pieces:
- early blockers if planeswalkers are exposed
- mana fixing for four colors

Should recommend:
- counter-bearing permanents and repeatable proliferate
- interaction that protects planeswalkers

Should avoid:
- generic lifegain
- creature +1/+1 counter swarm if no creature-counter density exists

Reason quality notes:
- Deck Analysis must use the sample to identify Superfriends. It should not assume poison or +1/+1 counters from Atraxa alone.

## Deck Case: Chishiro, the Shattered Blade - Modified, Not Proliferate

Commander:
- Chishiro, the Shattered Blade

Deck sample:
- Rancor
- Snake Umbra
- Bear Umbra
- Ring of Valkas
- Swiftfoot Boots
- Blackblade Reforged
- Kami of Celebration
- Invigorating Hot Spring
- Rhythm of the Wild
- Hardened Scales
- Forgotten Ancient
- Walking Ballista
- Lizard Blades
- Champion of Lambholt
- Toski, Bearer of Secrets
- Beast Within
- Chaos Warp
- Cultivate
- Kodama's Reach
- Kessig Wolf Run

Expected deck themes:
- modified creature value
- Aura/Equipment/counter hybrid

Expected missing pieces:
- more cheap creatures to carry modifications if the list is top-heavy
- card draw if Toski is unavailable

Should recommend:
- ways to modify multiple creatures through Auras, Equipment, or counters
- payoffs for going wide with modified creatures

Should avoid:
- proliferate as the default counter recommendation
- single-commander Voltron only

Reason quality notes:
- Deck Analysis must understand modified is a condition, not one mechanic. It should not reduce the deck to Equipment or counters alone.

## Deck Case: Aesi, Tyrant of Gyre Strait - Lands Draw Engine

Commander:
- Aesi, Tyrant of Gyre Strait

Deck sample:
- Exploration
- Burgeoning
- Azusa, Lost but Seeking
- Dryad of the Ilysian Grove
- Oracle of Mul Daya
- Cultivate
- Kodama's Reach
- Nature's Lore
- Farseek
- Rampaging Baloths
- Scute Swarm
- Tireless Provisioner
- Tatyova, Benthic Druid
- Roil Elemental
- Avenger of Zendikar
- Simic Growth Chamber
- Evolving Wilds
- Fabled Passage
- Field of the Dead
- Mystic Sanctuary

Expected deck themes:
- extra land drops
- landfall card draw

Expected missing pieces:
- interaction/removal
- protection for a six-mana commander

Should recommend:
- extra land-drop effects and landfall payoffs
- lands that can enter repeatedly or sacrifice themselves

Should avoid:
- graveyard land recursion as primary unless present
- generic sea monster typal

Reason quality notes:
- Deck Analysis must identify lands entering as the engine. It should not call this generic Simic ramp.

## Deck Case: The Gitrog Monster - Lands in Graveyard

Commander:
- The Gitrog Monster

Deck sample:
- Dakmor Salvage
- Life from the Loam
- Crop Rotation
- Entomb
- Satyr Wayfinder
- Stitcher's Supplier
- Ramunap Excavator
- Crucible of Worlds
- Zuran Orb
- Squandered Resources
- World Shaper
- Splendid Reclamation
- Bojuka Bog
- Strip Mine
- Wasteland
- Evolving Wilds
- Fabled Passage
- Skullclamp
- Putrefy
- Sylvan Library

Expected deck themes:
- land graveyard value
- land recursion

Expected missing pieces:
- graveyard protection
- clear win condition if only value pieces are present

Should recommend:
- lands that sacrifice/discard well and ways to replay them
- self-mill/discard that specifically supports land recursion

Should avoid:
- creature reanimator
- landfall-only cards that never put lands in graveyard

Reason quality notes:
- Deck Analysis must understand lands going to graveyard draw cards. It should not recommend generic reanimation packages.

## Deck Case: Veyran, Voice of Duality - Trigger-Doubling Spellslinger

Commander:
- Veyran, Voice of Duality

Deck sample:
- Opt
- Consider
- Ponder
- Preordain
- Brainstorm
- Faithless Looting
- Expressive Iteration
- Storm-Kiln Artist
- Young Pyromancer
- Third Path Iconoclast
- Archmage Emeritus
- Guttersnipe
- Thousand-Year Storm
- Bonus Round
- Reverberate
- Expansion // Explosion
- Lightning Greaves
- Swan Song
- Counterspell
- Aetherflux Reservoir

Expected deck themes:
- spellslinger
- cast/copy trigger doubling

Expected missing pieces:
- mana base/ramp if many spells chain in one turn
- protection for Veyran

Should recommend:
- cheap cantrips and magecraft-like payoffs
- copy effects that create additional trigger events

Should avoid:
- big spells with no velocity
- creature-token swarm unrelated to casting spells

Reason quality notes:
- Deck Analysis must say Veyran doubles triggered abilities, not that copied spells are cast.

## Deck Case: Zada, Hedron Grinder - Targeting Copy Swarm

Commander:
- Zada, Hedron Grinder

Deck sample:
- Expedite
- Crimson Wisps
- Accelerate
- Renegade Tactics
- Titan's Strength
- Infuriate
- Brute Force
- Fists of Flame
- Ancestral Anger
- Twinflame
- Heat Shimmer
- Krenko's Command
- Dragon Fodder
- Hordeling Outburst
- Young Pyromancer
- Third Path Iconoclast
- Runaway Steam-Kin
- Birgi, God of Storytelling
- Impact Tremors
- Goblin Bombardment

Expected deck themes:
- targeting payoff
- spell-copy swarm

Expected missing pieces:
- protection for Zada
- enough token makers if hand is full of target spells

Should recommend:
- cheap spells that target only Zada and replace themselves
- token makers that increase copy count

Should avoid:
- generic storm cards that do not target creatures
- Voltron pump for one creature only

Reason quality notes:
- Deck Analysis must understand the spell-copy condition. It should not claim Zada casts copies.

## Deck Case: Isshin, Two Heavens as One - Attack Triggers, Not Damage Triggers

Commander:
- Isshin, Two Heavens as One

Deck sample:
- Myrel, Shield of Argive
- Adeline, Resplendent Cathar
- Hero of Bladehold
- Etali, Primal Storm
- Professional Face-Breaker
- Grave Titan
- Breena, the Demagogue
- Skyknight Vanguard
- Krenko, Tin Street Kingpin
- Aurelia, the Warleader
- Reconnaissance
- Dolmen Gate
- Fervent Charge
- Shared Animosity
- Boros Charm
- Teferi's Protection
- Swords to Plowshares
- Terminate
- Sol Ring
- Arcane Signet

Expected deck themes:
- attack-trigger doubling
- combat token/value engine

Expected missing pieces:
- card draw if attack engines are removed
- board protection against wipes

Should recommend:
- attack-trigger permanents and combat protection
- tokens generated on attack

Should avoid:
- combat-damage triggers presented as doubled by Isshin
- extra combat as the only plan

Reason quality notes:
- Deck Analysis must accurately distinguish attack triggers from combat-damage triggers.

## Deck Case: Edric, Spymaster of Trest - Combat Damage Tempo

Commander:
- Edric, Spymaster of Trest

Deck sample:
- Ornithopter
- Faerie Seer
- Spectral Sailor
- Triton Shorestalker
- Slither Blade
- Gudul Lurker
- Mist-Cloaked Herald
- Invisible Stalker
- Siren Stormtamer
- Bident of Thassa
- Coastal Piracy
- Reconnaissance Mission
- Curiosity
- Nature's Claim
- Swan Song
- Counterspell
- Cyclonic Rift
- Temporal Manipulation
- Time Warp
- Beast Within

Expected deck themes:
- combat-damage draw
- evasive go-wide tempo

Expected missing pieces:
- protection against board wipes
- ways to close after drawing many cards

Should recommend:
- cheap evasive creatures and tempo protection
- extra turns or finishers if the list already draws enough

Should avoid:
- Voltron commander-damage packages
- generic Simic landfall

Reason quality notes:
- Deck Analysis must identify many small evasive attackers, not a single suited commander.

## Deck Case: Edgar Markov - Vampire Typal Aggro

Commander:
- Edgar Markov

Deck sample:
- Stromkirk Noble
- Indulgent Aristocrat
- Vicious Conquistador
- Vampire of the Dire Moon
- Gifted Aetherborn
- Bloodghast
- Captivating Vampire
- Stromkirk Captain
- Legion Lieutenant
- Cordial Vampire
- Drana, Liberator of Malakir
- Champion of Dusk
- Sanctum Seeker
- Bloodline Keeper
- Skullclamp
- Shared Animosity
- Swords to Plowshares
- Terminate
- Boros Charm
- Kindred Dominance

Expected deck themes:
- Vampire typal
- go-wide aggro

Expected missing pieces:
- mana fixing for three colors
- protection against sweepers

Should recommend:
- cheap Vampires and Vampire lords
- draw/protection that supports attacking

Should avoid:
- generic aristocrats unless death payoffs dominate
- non-Vampire token strategies

Reason quality notes:
- Deck Analysis must account for eminence and Vampire spell density. It should not over-focus on Edgar being cast.

## Deck Case: Oloro, Ageless Ascetic - Lifegain Control

Commander:
- Oloro, Ageless Ascetic

Deck sample:
- Soul Warden
- Soul's Attendant
- Authority of the Consuls
- Blind Obedience
- Daxos, Blessed by the Sun
- Drogskol Reaver
- Well of Lost Dreams
- Alhammarret's Archive
- Sanguine Bond
- Exquisite Blood
- Aetherflux Reservoir
- Ghostly Prison
- Propaganda
- Sphere of Safety
- Supreme Verdict
- Swords to Plowshares
- Counterspell
- Anguished Unmaking
- Sol Ring
- Arcane Signet

Expected deck themes:
- lifegain control
- life-total payoff

Expected missing pieces:
- win conditions if combo pieces are absent
- mana fixing

Should recommend:
- lifegain payoffs and control tools
- pillow-fort cards that buy time

Should avoid:
- aggressive lifegain Voltron
- generic Esper control with no life payoff

Reason quality notes:
- Deck Analysis must mention passive command-zone lifegain. It should not require Oloro to attack or resolve.

## Deck Case: Brago, King Eternal - Blink ETB

Commander:
- Brago, King Eternal

Deck sample:
- Wall of Omens
- Spirited Companion
- Mulldrifter
- Cloudblazer
- Solemn Simulacrum
- Reflector Mage
- Skyclave Apparition
- Stonehorn Dignitary
- Peregrine Drake
- Strionic Resonator
- Conjurer's Closet
- Omen of the Sea
- Reality Acid
- Prophetic Prism
- Azorius Signet
- Sol Ring
- Swiftfoot Boots
- Whispersilk Cloak
- Swords to Plowshares
- Counterspell

Expected deck themes:
- blink
- ETB value

Expected missing pieces:
- ways to ensure Brago connects
- protection from removal

Should recommend:
- ETB permanents and evasion/protection for Brago
- blink payoffs that scale with repeated resets

Should avoid:
- Voltron damage scaling
- graveyard recursion

Reason quality notes:
- Deck Analysis must say combat damage is the condition for blink, not the payoff itself.

## Deck Case: Prosper, Tome-Bound - Cast from Exile Treasure

Commander:
- Prosper, Tome-Bound

Deck sample:
- Light Up the Stage
- Reckless Impulse
- Wrenn's Resolve
- Jeska's Will
- Outpost Siege
- Theater of Horrors
- Stolen Strategy
- Etali, Primal Storm
- Dire Fleet Daredevil
- Professional Face-Breaker
- Laelia, the Blade Reforged
- Xorn
- Academy Manufactor
- Marionette Master
- Disciple of the Vault
- Mayhem Devil
- Bedevil
- Chaos Warp
- Sol Ring
- Arcane Signet

Expected deck themes:
- cast from exile
- Treasure value

Expected missing pieces:
- card selection if impulse draw exiles too many uncastable cards
- artifact/enchantment removal

Should recommend:
- impulse draw and exile-cast enablers
- Treasure payoffs that convert artifact tokens into advantage

Should avoid:
- artifact recursion
- discard/reanimator packages

Reason quality notes:
- Deck Analysis must connect exile-casting to Treasure creation. It should not classify Treasures alone as artifact recursion.

## Deck Case: Zedruu the Greathearted - Donation Politics

Commander:
- Zedruu the Greathearted

Deck sample:
- Steel Golem
- Grid Monitor
- Aggressive Mining
- Illusions of Grandeur
- Transcendence
- Statecraft
- Harmless Offering
- Role Reversal
- Pendant of Prosperity
- Coveted Jewel
- Propaganda
- Ghostly Prison
- Sphere of Safety
- Dovin's Veto
- Swords to Plowshares
- Chaos Warp
- Sol Ring
- Azorius Signet
- Izzet Signet
- Boros Signet

Expected deck themes:
- donation politics
- control/pillow-fort

Expected missing pieces:
- safe donation density if too many cards help opponents
- win condition clarity

Should recommend:
- controlled donation targets and pillow-fort protection
- interaction that manages donated drawbacks

Should avoid:
- generic group hug
- Voltron or equipment packages

Reason quality notes:
- Deck Analysis must understand ownership versus control. It should not recommend cards that help opponents without payoff.

## Deck Case: Kozilek, the Great Distortion - Colorless Big Mana

Commander:
- Kozilek, the Great Distortion

Deck sample:
- Sol Ring
- Mana Vault
- Grim Monolith
- Basalt Monolith
- Thran Dynamo
- Hedron Archive
- Dreamstone Hedron
- Mind Stone
- Everflowing Chalice
- Forsaken Monument
- Mystic Forge
- The One Ring
- Ugin, the Ineffable
- All Is Dust
- Warping Wail
- Spatial Contortion
- Lightning Greaves
- Swiftfoot Boots
- Ancient Tomb
- Eldrazi Temple

Expected deck themes:
- colorless big mana
- high-mana commander finisher

Expected missing pieces:
- colored-card filtering; none should be recommended
- early interaction if meta is fast

Should recommend:
- colorless ramp and utility interaction
- protection for a ten-mana commander

Should avoid:
- colored staples
- artifact recursion as primary

Reason quality notes:
- Deck Analysis must respect colorless identity as a hard recommendation constraint.

## Deck Case: Gyruda, Doom of Depths - Even Mana Value Restriction

Commander:
- Gyruda, Doom of Depths

Deck sample:
- Sakashima the Impostor
- Spark Double
- Clever Impersonator
- Phyrexian Metamorph
- Clone
- Stunt Double
- Vizier of Many Faces
- Thassa, Deep-Dwelling
- Panharmonicon
- Solemn Simulacrum
- Dauthi Voidwalker
- Baleful Strix
- Dimir Signet
- Talisman of Dominance
- Mind Stone
- Fact or Fiction
- Damnation
- Toxic Deluge
- Reanimate
- Animate Dead

Expected deck themes:
- mana value restriction
- mill/reanimate clone chain

Expected missing pieces:
- verify restriction compliance if using companion-style build
- graveyard hate protection

Should recommend:
- even-mana creatures and clones
- ramp/interaction that respects the restriction when relevant

Should avoid:
- odd-mana staples in a restricted build
- generic reanimator targets with no ETB/cloning value

Reason quality notes:
- Deck Analysis must detect the even mana value pressure. It should not blindly recommend efficient odd-mana staples.
