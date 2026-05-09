# Golden Commander QA Matrix

Purpose: deterministic commander QA coverage across archetypes without commander-specific hacks. Each commander should validate broad theme recognition, recommendation quality, and false-positive avoidance.

Recommended use:
- Treat commander names as fixture anchors, not hardcoded logic.
- Primary themes should be inferred from commander text, deck shape, card-type density, and synergy patterns.
- Recommendations should reflect categories first, with individual card examples only when they represent a category well.
- Avoid recommendations that are generically powerful but off-plan.

---

# Enchantment Toolbox / Enchantress

## Sythis, Harvest's Hand

Expected primary themes:
- enchantment toolbox
- enchantress card draw

Should recommend:
- low-cost enchantments and enchantment cantrips
- enchantment payoff cards such as constellation effects or enchantress draw engines

Should avoid:
- generic Selesnya creature tokens
- equipment Voltron packages

Reason quality notes:
- The explanation should understand that Sythis rewards casting enchantments, not simply controlling them, and should prioritize enchantment density, cheap enchantments, and repeatable value.

## Tuvasa the Sunlit

Expected primary themes:
- enchantress
- aura Voltron

Should recommend:
- aura-based protection and evasion
- enchantress draw engines and enchantment-cost support

Should avoid:
- generic Bant goodstuff
- creature-token swarm recommendations

Reason quality notes:
- The explanation should understand that Tuvasa overlaps enchantress and Voltron, but the recommendations should still be enchantment-centered rather than generic commander-damage support.

## Zur the Enchanter

Expected primary themes:
- enchantment toolbox
- tutor/control

Should recommend:
- enchantments with mana value 3 or less
- silver-bullet enchantments, protection pieces, and control enchantments

Should avoid:
- high-mana enchantments that Zur cannot search for
- generic Esper control cards with no enchantment synergy

Reason quality notes:
- The explanation should understand Zur's mana value restriction and should not recommend enchantments purely because they are powerful.

## Go-Shintai of Life's Origin

Expected primary themes:
- Shrine enchantments
- five-color enchantment recursion

Should recommend:
- Shrine subtype support
- enchantment recursion and mana fixing for five-color decks

Should avoid:
- generic enchantress cards that ignore Shrine scaling
- typal creature recommendations unrelated to Shrines

Reason quality notes:
- The explanation should recognize Shrines as enchantments with subtype-based scaling, not as normal creature typal.

---

# Artifact Recursion

## Emry, Lurker of the Loch

Expected primary themes:
- artifact recursion
- graveyard artifact value

Should recommend:
- cheap artifacts that sacrifice or self-mill
- artifact combo/value pieces that can be recast from the graveyard

Should avoid:
- generic mono-blue spellslinger
- creature reanimator packages

Reason quality notes:
- The explanation should understand that Emry is specifically artifact recursion from the graveyard, not generic graveyard reanimation.

## Teshar, Ancestor's Apostle

Expected primary themes:
- historic artifact recursion
- low-mana combo recursion

Should recommend:
- cheap historic spells
- small creatures with mana value 3 or less that enable loops

Should avoid:
- large artifact threats with no recursion loop
- generic white equipment Voltron

Reason quality notes:
- The explanation should understand the historic trigger and the mana value restriction on returned creatures.

## Osgir, the Reconstructor

Expected primary themes:
- artifact recursion
- artifact token copies

Should recommend:
- artifacts with strong sacrifice or enter-the-battlefield value
- graveyard setup and artifact-copy payoffs

Should avoid:
- generic Boros combat aggro
- creature-token recommendations unrelated to artifacts

Reason quality notes:
- The explanation should understand that Osgir turns graveyard artifacts into token copies and should value artifacts that scale when copied.

## Mishra, Eminent One

Expected primary themes:
- artifact recursion-like reuse
- temporary artifact token copies

Should recommend:
- artifacts with attack triggers, ETB value, or sacrifice value
- artifact payoffs that benefit from extra temporary copies

Should avoid:
- graveyard-only artifact recursion assumptions
- generic Grixis control recommendations

Reason quality notes:
- The explanation should distinguish Mishra's temporary Warform copies from true graveyard recursion.

---

# Artifact Tokens

## Magda, Brazen Outlaw

Expected primary themes:
- Treasure tokens
- artifact-based tutoring

Should recommend:
- Dwarves or tap enablers that create Treasures
- high-impact artifacts and Dragons to tutor with Treasure sacrifices

Should avoid:
- generic red aggro cards with no Treasure support
- broad artifact recursion packages

Reason quality notes:
- The explanation should understand that Magda's Treasure production and tutor ability are the core engine.

## Lonis, Cryptozoologist

Expected primary themes:
- Clue tokens
- investigate value

Should recommend:
- creatures that repeatedly enter the battlefield
- artifact-token payoff cards and investigate support

Should avoid:
- Treasure-only artifact token packages
- generic Simic ramp with no Clue synergy

Reason quality notes:
- The explanation should recognize Clues as artifact tokens and should understand that creature ETBs fuel the commander.

## Chatterfang, Squirrel General

Expected primary themes:
- token multiplication
- sacrifice/token aristocrats

Should recommend:
- token generators that create many bodies or artifact tokens
- sacrifice outlets and death payoffs

Should avoid:
- pure Squirrel typal with no token engine
- generic Golgari graveyard cards without sacrifice payoff

Reason quality notes:
- The explanation should understand Chatterfang as a token replacement/multiplication commander, not only a Squirrel commander.

## Urza, Lord High Artificer

Expected primary themes:
- artifact tokens
- artifact mana/value engine

Should recommend:
- cheap artifacts and artifact-token generators
- cards that reward high artifact count

Should avoid:
- generic mono-blue control without artifacts
- equipment Voltron packages

Reason quality notes:
- The explanation should understand that Urza converts artifacts into mana and creates a Construct that scales with artifact count.

---

# Counters / Proliferate

## Atraxa, Praetors' Voice

Expected primary themes:
- proliferate
- counters-matter

Should recommend:
- planeswalkers, +1/+1 counters, poison counters, or other counter-based payoffs
- cards that add counters before proliferating

Should avoid:
- generic four-color goodstuff
- poison-only recommendations unless the deck direction supports it

Reason quality notes:
- The explanation should understand that Atraxa proliferates all counter types and can support multiple counter strategies.

## Ezuri, Claw of Progress

Expected primary themes:
- experience counters
- +1/+1 counters

Should recommend:
- small creatures that trigger experience counters
- evasive or scalable creatures that benefit from +1/+1 counters

Should avoid:
- generic Simic ramp
- proliferate-only packages that ignore creature entry triggers

Reason quality notes:
- The explanation should understand that Ezuri uses small creature entries to build player-held experience counters.

## Tekuthal, Inquiry Dominus

Expected primary themes:
- proliferate
- counter amplification

Should recommend:
- permanents and players that accumulate counters
- repeatable proliferate engines

Should avoid:
- generic mono-blue spellslinger
- +1/+1 counter cards with no proliferate value

Reason quality notes:
- The explanation should understand that Tekuthal doubles proliferate events and should prioritize repeatable proliferate payoffs.

## Lae'zel, Vlaakith's Champion

Expected primary themes:
- counters-matter
- counter amplification

Should recommend:
- planeswalkers, +1/+1 counter support, and player-counter synergies
- cards that place counters repeatedly

Should avoid:
- generic mono-white aggro
- equipment Voltron unless counter synergy is present

Reason quality notes:
- The explanation should understand that Lae'zel adds extra counters to permanents and players, which includes more than creature counters.

---

# Sacrifice / Aristocrats

## Korvold, Fae-Cursed King

Expected primary themes:
- sacrifice value
- aristocrats/Treasure overlap

Should recommend:
- repeatable sacrifice fodder such as Treasures, Food, creatures, or lands
- sacrifice payoffs and death-trigger engines

Should avoid:
- generic Jund midrange
- Dragon typal recommendations based only on commander type

Reason quality notes:
- The explanation should understand that Korvold rewards sacrificing any permanent, not only creatures.

## Teysa Karlov

Expected primary themes:
- aristocrats
- death-trigger doubling

Should recommend:
- creature death payoffs
- sacrifice outlets and token fodder

Should avoid:
- generic Orzhov lifegain
- reanimator packages with no death-trigger payoff

Reason quality notes:
- The explanation should understand that Teysa doubles death triggers and supports token combat incidentally, but aristocrats is the core plan.

## Yawgmoth, Thran Physician

Expected primary themes:
- sacrifice combo
- -1/-1 counters

Should recommend:
- undying creatures and recursive fodder
- cards that benefit from sacrifice, card draw, or -1/-1 counters

Should avoid:
- generic mono-black reanimator
- poison/counter recommendations that ignore sacrifice loops

Reason quality notes:
- The explanation should understand that Yawgmoth is both a sacrifice outlet and a counter engine.

## Elas il-Kor, Sadistic Pilgrim

Expected primary themes:
- aristocrats
- creature ETB/death lifedrain

Should recommend:
- cheap creatures and token makers
- sacrifice outlets and drain effects

Should avoid:
- generic Orzhov lifegain lifegain-only packages
- equipment Voltron

Reason quality notes:
- The explanation should understand the dual ETB/death drain pattern and recommend cards that repeatedly move creatures through the battlefield.

---

# Blink / Flicker

## Brago, King Eternal

Expected primary themes:
- blink
- combat-damage value engine

Should recommend:
- permanents with strong enter-the-battlefield effects
- ways to protect or give evasion to Brago

Should avoid:
- generic Azorius control with no ETB value
- Voltron equipment packages that ignore blink value

Reason quality notes:
- The explanation should understand that Brago blinks nonland permanents after combat damage connects.

## Yorion, Sky Nomad

Expected primary themes:
- blink
- ETB value

Should recommend:
- permanents with ETB triggers
- blink payoffs and value engines that scale with mass flicker

Should avoid:
- generic flying typal
- control cards with no permanent-based ETB value

Reason quality notes:
- The explanation should understand Yorion as mass blink support, not a normal evasive creature commander.

## Roon of the Hidden Realm

Expected primary themes:
- repeatable blink
- ETB toolbox

Should recommend:
- creatures with ETB removal, ramp, draw, or recursion
- untap or protection support for Roon

Should avoid:
- generic Bant ramp
- aura Voltron packages

Reason quality notes:
- The explanation should understand targeted repeatable flicker and the delayed return timing.

## Abdel Adrian, Gorion's Ward + Candlekeep Sage

Expected primary themes:
- blink combo
- Background value engine

Should recommend:
- permanents that benefit from being exiled and returned
- Background-compatible value support and token payoffs

Should avoid:
- generic Azorius goodstuff
- partner recommendations that ignore Background rules

Reason quality notes:
- The explanation should understand Background pairing and Abdel's exile-until-leaves pattern.

---

# Spellslinger

## Veyran, Voice of Duality

Expected primary themes:
- spellslinger
- magecraft/trigger doubling

Should recommend:
- cheap instants and sorceries
- magecraft, prowess, and spell-copy payoffs

Should avoid:
- generic Izzet artifacts
- high-cost spells with no cast-density support

Reason quality notes:
- The explanation should understand that Veyran doubles triggered abilities caused by casting or copying instants and sorceries.

## Mizzix of the Izmagnus

Expected primary themes:
- spellslinger
- experience counter cost reduction

Should recommend:
- instants and sorceries with varied mana values
- big spells that benefit from cost reduction after setup

Should avoid:
- generic Izzet cantrip-only plans that do not scale
- creature-heavy recommendations

Reason quality notes:
- The explanation should understand how experience counters reduce spell costs and why the curve matters.

## Zada, Hedron Grinder

Expected primary themes:
- spell-copy combo
- combat pump/cantrip storm

Should recommend:
- single-target cantrips and pump spells
- token makers or bodies that multiply copied spells

Should avoid:
- multi-target spells that do not trigger Zada properly
- generic mono-red burn

Reason quality notes:
- The explanation should understand Zada's exact targeting requirement and why single-target spells are preferred.

## Kess, Dissident Mage

Expected primary themes:
- spellslinger
- graveyard spell recursion

Should recommend:
- instants and sorceries that are strong when cast twice
- discard, self-mill, or graveyard setup for spells

Should avoid:
- creature reanimator packages
- artifact recursion recommendations

Reason quality notes:
- The explanation should understand that Kess reuses spells from the graveyard once each turn.

---

# Landfall / Lands Matter

## Omnath, Locus of Creation

Expected primary themes:
- landfall
- four-color ramp/value

Should recommend:
- extra land drops and fetch lands or land-search effects
- landfall payoffs and mana sinks

Should avoid:
- generic Elemental typal unless landfall supports it
- four-color goodstuff with no land engine

Reason quality notes:
- The explanation should understand Omnath's first, second, and third landfall triggers and why multiple land drops matter.

## Aesi, Tyrant of Gyre Strait

Expected primary themes:
- lands matter
- landfall card draw

Should recommend:
- extra land drop effects
- land ramp, land recursion, and cards that put lands onto the battlefield

Should avoid:
- generic Simic sea-monster ramp
- spellslinger draw packages

Reason quality notes:
- The explanation should understand that Aesi rewards lands entering the battlefield and enables extra land drops.

## The Gitrog Monster

Expected primary themes:
- lands matter
- graveyard land recursion

Should recommend:
- land sacrifice outlets and discard outlets
- lands that can enter the graveyard repeatedly and graveyard recursion tools

Should avoid:
- generic Golgari reanimator
- creature-sacrifice aristocrats with no land focus

Reason quality notes:
- The explanation should understand lands going to the graveyard as the card-draw engine.

## Tatyova, Benthic Druid

Expected primary themes:
- landfall
- ramp/card draw

Should recommend:
- extra land drops and land ramp
- bounce lands or land recursion that repeatedly trigger landfall

Should avoid:
- generic Simic counters
- creature-heavy ramp with no land ETB support

Reason quality notes:
- The explanation should understand that Tatyova converts land entries into life and cards.

---

# Voltron

## Sram, Senior Edificer

Expected primary themes:
- Voltron
- aura/equipment card draw

Should recommend:
- cheap Auras, Equipment, and Vehicles if relevant
- protection and evasion for the commander

Should avoid:
- generic mono-white tokens
- enchantress recommendations that exclude Equipment

Reason quality notes:
- The explanation should understand Sram's draw trigger from Auras, Equipment, and Vehicles.

## Light-Paws, Emperor's Voice

Expected primary themes:
- Aura Voltron
- aura tutor chain

Should recommend:
- low-mana Auras with protection, evasion, and scaling power
- aura packages with different names and useful mana values

Should avoid:
- Equipment packages
- generic enchantress cards that do not support Aura tutoring

Reason quality notes:
- The explanation should understand Light-Paws searches for Auras with mana value less than or equal to the cast Aura and with a different name.

## Wyleth, Soul of Steel

Expected primary themes:
- Voltron
- equipment/aura combat draw

Should recommend:
- cheap Equipment and Auras
- protection, evasion, and double strike support

Should avoid:
- generic Boros aggro
- creature-token go-wide cards

Reason quality notes:
- The explanation should understand that Wyleth wants to attack while modified by Auras and Equipment to draw cards.

## Rafiq of the Many

Expected primary themes:
- Voltron
- exalted/single-attacker combat

Should recommend:
- exalted support, evasion, and commander protection
- pump effects that scale with double strike

Should avoid:
- go-wide combat recommendations
- generic Bant ramp

Reason quality notes:
- The explanation should understand that Rafiq rewards attacking with one creature, not building a wide board.

---

# Graveyard / Reanimator

## Muldrotha, the Gravetide

Expected primary themes:
- graveyard value
- permanent recursion

Should recommend:
- self-mill and sacrifice permanents
- permanents across multiple card types that can be replayed from the graveyard

Should avoid:
- instant/sorcery flashback packages as the main plan
- generic Sultai goodstuff

Reason quality notes:
- The explanation should understand that Muldrotha recasts permanents by type from the graveyard.

## Karador, Ghost Chieftain

Expected primary themes:
- creature graveyard recursion
- reanimator/value creatures

Should recommend:
- self-mill and creature sacrifice outlets
- creatures with ETB/death value that can be recast from the graveyard

Should avoid:
- noncreature graveyard spell packages
- generic Abzan counters

Reason quality notes:
- The explanation should understand Karador's creature-specific recursion and cost reduction from creatures in the graveyard.

## Chainer, Nightmare Adept

Expected primary themes:
- reanimator
- discard/graveyard setup

Should recommend:
- discard outlets and reanimation targets
- creatures that benefit from haste when cast from the graveyard

Should avoid:
- generic Rakdos sacrifice without reanimation
- madness-only packages unless supported

Reason quality notes:
- The explanation should understand that Chainer enables one creature spell from graveyard each turn and grants haste to nontoken creatures entering from graveyard/cast contexts.

## Meren of Clan Nel Toth

Expected primary themes:
- graveyard recursion
- sacrifice/aristocrats

Should recommend:
- sacrifice outlets and recursive creatures
- experience counter support and ETB/death-value creatures

Should avoid:
- generic Golgari lands matter
- artifact recursion packages

Reason quality notes:
- The explanation should understand that Meren uses death events to gain experience counters and recur creatures at end step.

---

# Typal

## Edgar Markov

Expected primary themes:
- Vampire typal
- aggro tokens

Should recommend:
- Vampire creatures and Vampire lords
- low-cost Vampires that benefit from Eminence token production

Should avoid:
- generic Mardu aristocrats without Vampire density
- non-Vampire token swarm cards as the main plan

Reason quality notes:
- The explanation should understand Eminence and the need for high Vampire density.

## The Ur-Dragon

Expected primary themes:
- Dragon typal
- five-color big creatures

Should recommend:
- Dragon cost reduction and ramp
- high-impact Dragons and attack-trigger support

Should avoid:
- generic five-color goodstuff
- non-Dragon tribal packages

Reason quality notes:
- The explanation should understand Dragon density, Eminence cost reduction, and attack-trigger payoff.

## Miirym, Sentinel Wyrm

Expected primary themes:
- Dragon typal
- Dragon token copying

Should recommend:
- Dragons with strong ETB or attack triggers
- token-copy and Dragon support pieces

Should avoid:
- generic Temur ramp with few Dragons
- noncreature copy-spell packages as the main plan

Reason quality notes:
- The explanation should understand that Miirym copies nontoken Dragons entering the battlefield.

## Wilhelt, the Rotcleaver

Expected primary themes:
- Zombie typal
- aristocrats/token sacrifice

Should recommend:
- Zombies that create bodies or benefit from dying
- sacrifice outlets and Zombie death payoffs

Should avoid:
- generic Dimir control
- non-Zombie aristocrats as the main package

Reason quality notes:
- The explanation should understand decayed Zombie token generation and end-step sacrifice/card-draw support.

---

# Combat Damage / Attack Triggers

## Edric, Spymaster of Trest

Expected primary themes:
- combat damage card draw
- evasive creature tempo

Should recommend:
- cheap evasive creatures
- extra turn or tempo cards that benefit from repeated combat damage

Should avoid:
- Voltron-only packages
- generic Simic ramp

Reason quality notes:
- The explanation should understand that Edric rewards multiple creatures dealing combat damage to players.

## Isshin, Two Heavens as One

Expected primary themes:
- attack triggers
- combat trigger doubling

Should recommend:
- creatures and permanents with attack triggers
- token attack payoffs and extra combat support

Should avoid:
- combat-damage-only recommendations as the main plan
- generic Mardu aristocrats

Reason quality notes:
- The explanation should distinguish attack triggers from combat damage triggers.

## Aurelia, the Warleader

Expected primary themes:
- extra combat
- combat aggression

Should recommend:
- attack-trigger creatures and combat-damage payoffs
- equipment, protection, or untap-support that scales across extra combats

Should avoid:
- generic Boros tokens with no combat-scaling payoff
- defensive control packages

Reason quality notes:
- The explanation should understand Aurelia's extra combat trigger and why vigilance/untap/combat triggers scale well.

## Marisi, Breaker of the Coil

Expected primary themes:
- combat damage
- goad/forced combat

Should recommend:
- evasive creatures that reliably deal combat damage
- goad payoffs and combat-control pieces

Should avoid:
- generic Naya stompy
- Voltron-only plans that ignore multiplayer goad pressure

Reason quality notes:
- The explanation should understand that Marisi needs combat damage to players to shut off spells during combat and goad opposing creatures.

---

# Colorless

## Kozilek, the Great Distortion

Expected primary themes:
- colorless big mana
- Eldrazi/control through discard

Should recommend:
- colorless ramp and utility lands
- high-mana colorless threats and cards that support discard-based protection

Should avoid:
- colored ramp spells
- generic artifact tokens as the main plan unless they support big mana

Reason quality notes:
- The explanation should understand colorless deck-building constraints and Kozilek's cast-trigger refill/counter ability.

## Zhulodok, Void Gorger

Expected primary themes:
- colorless big mana
- high-mana-value colorless cascade

Should recommend:
- colorless spells with mana value 7 or greater
- ramp that accelerates into expensive colorless spells

Should avoid:
- low-curve artifact swarm packages
- colored Eldrazi recommendations that violate color identity

Reason quality notes:
- The explanation should understand Zhulodok's mana value threshold and the importance of expensive colorless spells.

## Karn, Legacy Reforged

Expected primary themes:
- colorless artifacts
- artifact-count mana scaling

Should recommend:
- artifacts with varied mana values
- artifact ramp and payoff cards that benefit from large amounts of colorless mana

Should avoid:
- generic Eldrazi-only builds
- colored artifact staples outside color identity

Reason quality notes:
- The explanation should understand Karn's mana generation based on mana values among artifacts controlled.

## Liberator, Urza's Battlethopter

Expected primary themes:
- colorless flash/artifact tempo
- +1/+1 counter scaling

Should recommend:
- colorless spells that benefit from flash timing
- artifacts or colorless spells that scale Liberator through counters

Should avoid:
- generic artifact recursion
- equipment Voltron as the default plan

Reason quality notes:
- The explanation should understand that Liberator gives flash to colorless and artifact spells while growing from higher-mana-value casts.

---

# Weird Mechanics / Edge Cases

## The Beamtown Bullies

Expected primary themes:
- forced reanimation
- graveyard politics

Should recommend:
- creatures with severe drawbacks when controlled by opponents
- graveyard setup and sacrifice/discard tools

Should avoid:
- normal reanimator fatties that help opponents
- generic Jund sacrifice as the primary plan

Reason quality notes:
- The explanation should understand that the commander gives creatures from your graveyard to opponents temporarily.

## Obeka, Brute Chronologist

Expected primary themes:
- end-the-turn mechanics
- temporary-effect abuse

Should recommend:
- cards with delayed sacrifice, exile, or end-step drawbacks
- effects that benefit from ending the turn before delayed triggers resolve

Should avoid:
- generic Grixis control
- recommendations that assume Obeka counters any drawback automatically

Reason quality notes:
- The explanation should understand timing, delayed triggers, and the limitation that the player whose turn it is chooses whether to end the turn.

## Zedruu the Greathearted

Expected primary themes:
- donate/control exchange
- political value

Should recommend:
- permanents that can be safely donated or punish opponents
- cards that give control of permanents to opponents

Should avoid:
- generic Jeskai spellslinger
- group hug cards that do not involve donated permanents

Reason quality notes:
- The explanation should understand ownership versus control and Zedruu's upkeep reward for permanents opponents control that you own.

## Slicer, Hired Muscle

Expected primary themes:
- shared commander aggression
- Voltron/political combat edge case

Should recommend:
- Equipment and protection that remain beneficial while Slicer changes control
- damage amplification that pressures multiple opponents

Should avoid:
- normal go-wide aggro
- recommendations that fail because opponents control the commander on their turns

Reason quality notes:
- The explanation should understand the control-changing pattern and how it changes normal Voltron assumptions.

## Grist, the Hunger Tide

Expected primary themes:
- planeswalker commander edge case
- graveyard/Insect sacrifice

Should recommend:
- Insects, self-mill, and sacrifice support
- cards that care about creatures in graveyard or creature death

Should avoid:
- generic planeswalker superfriends
- recommendations that assume Grist is always only a planeswalker in all zones

Reason quality notes:
- The explanation should understand Grist's special commander eligibility and creature-card behavior outside the battlefield.

## Inniaz, the Gale Force

Expected primary themes:
- flying matters
- permanent exchange/control rotation

Should recommend:
- evasive flying creatures
- permanents that are asymmetrically good to exchange or politically useful

Should avoid:
- generic Azorius flyers with no exchange plan
- blink recommendations that ignore control exchange

Reason quality notes:
- The explanation should understand that Inniaz rotates control of nonland permanents after attacking with enough flying creatures.

## Hinata, Dawn-Crowned

Expected primary themes:
- target-based cost modification
- spellslinger/control

Should recommend:
- spells with many targets or scalable target counts
- protection and interaction that benefit from cost reduction

Should avoid:
- generic Jeskai spellslinger with no targeted spells
- X-spells that do not target or do not scale with Hinata

Reason quality notes:
- The explanation should understand both cost reduction for your targeted spells and tax effects on opponents' targeted spells.

## Blim, Comedic Genius

Expected primary themes:
- donate/punisher
- combat-damage triggered exchange

Should recommend:
- bad permanents to give away
- evasion and protection to ensure combat damage connects

Should avoid:
- generic Rakdos discard
- symmetrical group-slug cards that are not good donation targets

Reason quality notes:
- The explanation should understand that Blim gives permanents to the damaged player and then punishes them for permanents they control but do not own.

