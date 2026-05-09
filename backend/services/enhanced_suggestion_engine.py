from typing import Dict, List, Optional, Set
import asyncio
import logging
import re
from collections import Counter, defaultdict
from services.scryfall_service import ScryfallService

logger = logging.getLogger(__name__)

class EnhancedSuggestionEngine:
    """Enhanced deterministic Commander deck suggestion engine with commander synergy"""
    
    def __init__(self, scryfall_service: ScryfallService):
        self.scryfall = scryfall_service
        
        # Role targets
        self.role_targets = {
            'draw': (10, 12),
            'ramp': (10, 12),
            'removal': (7, 10),
            'sweeper': (2, 4),
            'interaction': (5, 8),
            'protection': (3, 5)
        }
        
        # Commander synergy keywords
        self.synergy_keywords = {
            'enchantment': ['enchantment', 'aura', 'enchant'],
            'artifact': ['artifact', 'equipment'],
            'creature': ['creatures you control', 'creature spell', 'nontoken creature', 'creature card'],
            'instant_sorcery': ['instant', 'sorcery', 'spell'],
            'graveyard': ['graveyard', 'dies', 'death', 'reanimate', 'from your graveyard'],
            'lifegain': ['gain life', 'gains life', 'you gain'],
            'counters': ['+1/+1 counter', '-1/-1 counter', 'counter on', 'put a counter', 'put one or more counters', 'proliferate'],
            'tokens': ['create', 'token'],
            'artifact_tokens': ['treasure token', 'clue token', 'food token', 'blood token', 'artifact token'],
            'exile': ['exile'],
            'blink': ['exile it, then return', 'exile another target', 'return it to the battlefield', 'flicker'],
            'landfall': ['landfall', 'land enters', 'additional land'],
            'sacrifice': ['sacrifice', 'dies'],
            'voltron': ['equipment', 'aura', 'attach']
        }

    def _combined_type_line(self, card: Dict) -> str:
        """Return all face type lines as a single lowercase string."""
        parts = [card.get('type_line', '')]
        parts.extend(face.get('type_line', '') for face in card.get('card_faces', []) or [])
        return ' '.join(part for part in parts if part).lower()

    def _combined_oracle_text(self, card: Dict) -> str:
        """Return all face oracle text as a single lowercase string."""
        parts = [card.get('oracle_text', '')]
        parts.extend(face.get('oracle_text', '') for face in card.get('card_faces', []) or [])
        return ' '.join(part for part in parts if part).lower()

    def _is_commander_eligible(self, card: Dict, creature_only: bool = False) -> bool:
        """True when the card can actually be chosen as a commander."""
        if not card or card.get('legalities', {}).get('commander') != 'legal':
            return False

        type_line = self._combined_type_line(card)
        oracle_text = self._combined_oracle_text(card)
        is_legendary_creature = 'legendary' in type_line and 'creature' in type_line
        if creature_only:
            return is_legendary_creature

        return is_legendary_creature or 'can be your commander' in oracle_text

    def _has_creature_spell_text(self, text: str) -> bool:
        """Match creature-spell text without treating noncreature spells as creatures."""
        return re.search(r'(?<!non)creature spell', text) is not None

    def _has_creature_card_text(self, text: str) -> bool:
        """Match creature-card text without treating noncreature cards as creatures."""
        return re.search(r'(?<!non)creature card', text) is not None

    def _counter_plan_for_text(self, text: str) -> Optional[str]:
        """Classify counter text so recommendations do not treat all counters alike."""
        if 'proliferate' in text:
            return 'proliferate'
        if self._named_counter_terms(text):
            return 'named_counters'
        if '-1/-1 counter' in text:
            return 'negative_counters'
        if '+1/+1 counter' not in text and 'counter on' not in text:
            return None
        if any(phrase in text for phrase in [
            'each creature you control',
            'creatures you control',
            'each other creature',
            'one or more creatures you control',
        ]):
            return 'board_counters'
        if re.search(r'put (?:a |one |one or more |that many )?\+1/\+1 counters? on (?:this creature|it|him|her|[a-z\', -]+)', text):
            return 'self_counters'
        return 'targeted_counters'

    def _named_counter_terms(self, text: str) -> List[str]:
        ignored = {'1/+1', '1/-1', 'loyalty'}
        terms = []
        for match in re.finditer(r'\b([a-z][a-z -]+?) counters?\b', text):
            term = match.group(1).strip()
            previous = None
            while previous != term:
                previous = term
                term = re.sub(
                    r'^(?:put|puts|putting|has|have|with|on|target|a|an|one or more|one|two|three|that|those)\s+',
                    '',
                    term
                ).strip()
            if len(term.split()) > 2:
                term = term.split()[-1]
            if term not in ignored and not term.endswith('+1/+1') and '+1/+1' not in term and '-1/-1' not in term:
                if term not in terms:
                    terms.append(term)
        return terms

    def _is_counter_multiplier(self, oracle_text: str) -> bool:
        return any(phrase in oracle_text for phrase in [
            'additional +1/+1 counter',
            'that many plus one',
            'twice that many',
            'double the number of counters',
            'double the number of +1/+1 counters',
        ])

    def _is_counter_payoff(self, oracle_text: str) -> bool:
        return any(phrase in oracle_text for phrase in [
            'creatures you control with counters',
            'creature you control with a counter',
            'if a creature you control has a counter',
            'modified creatures',
            'modified creature',
            'for each counter',
            'remove a +1/+1 counter',
            'whenever one or more counters',
        ])
    
    async def analyze_deck(self, deck: Dict, categories: Optional[List[str]] = None, deep: bool = False) -> Dict:
        """Main analysis entry point with commander synergy and category filtering"""
        cards = deck.get('cards', [])
        commander = deck.get('commander')
        color_identity = deck.get('color_identity', [])
        
        # Get commander card data for synergy analysis
        commander_data = None
        commander_synergies = []
        commander_constraints = {}
        if commander:
            commander_data = await self.scryfall.search_card(commander)
            if commander_data:
                commander_synergies = self._detect_commander_synergies(commander_data)
                commander_constraints = self._get_commander_constraints(commander_data)
        
        # Calculate deck statistics
        stats = self._calculate_stats(cards, commander, commander_synergies)
        
        # Detect deck themes and combos
        detected_themes = self._detect_deck_themes(cards, commander_synergies)
        
        # Identify gaps and issues
        gaps = self._identify_gaps(stats, color_identity, commander_synergies)
        
        # Generate suggestions with commander synergy and category filter
        suggestions_add = await self._generate_additions(
            gaps,
            commander,
            color_identity,
            cards,
            commander_synergies,
            commander_data,
            categories,
            commander_constraints,
            search_budget=10 if deep else 5,
        )
        suggestions_cut = await self._generate_cuts(cards, gaps, stats, commander_synergies, detected_themes)
        
        # Generate playstyle tips
        playstyle_tips = self._generate_playstyle_tips(
            stats,
            commander_synergies,
            detected_themes,
            commander,
            color_identity,
            commander_data,
        )
        if deep:
            playstyle_tips.extend(self._generate_deep_deck_playstyle_tips(
                stats,
                commander_synergies,
                detected_themes,
                commander,
                cards,
                color_identity,
            ))
        
        # Generate combo suggestions
        combo_suggestions = self._generate_combo_suggestions(commander, commander_synergies, cards)
        
        return {
            'suggestions_add': suggestions_add[:15 if deep else 10],
            'suggestions_cut': suggestions_cut[:12 if deep else 10],
            'stats': stats,
            'commander_synergies': commander_synergies,
            'detected_themes': detected_themes,
            'playstyle_tips': playstyle_tips,
            'combo_suggestions': combo_suggestions,
            'analysis_depth': 'deep' if deep else 'fast',
        }
    
    def _detect_commander_synergies(self, commander_card: Dict) -> List[str]:
        """Detect what synergies the commander cares about"""
        oracle_text = self._combined_oracle_text(commander_card)
        type_line = self._combined_type_line(commander_card)
        
        synergies = []

        def add_once(synergy_type: str):
            if synergy_type not in synergies:
                synergies.append(synergy_type)

        if 'enchantment' in oracle_text or 'aura' in oracle_text or 'enchant' in oracle_text:
            add_once('enchantment')
        if 'artifact' in oracle_text or 'equipment' in oracle_text:
            add_once('artifact')
        creature_theme_phrases = [
            'creatures you control',
            'nontoken creature',
            'whenever another creature',
            'whenever a creature enters',
            'whenever one or more creatures',
            'creature enters the battlefield',
            'each creature you control',
            'creatures get',
            'creatures have',
        ]
        if (
            any(phrase in oracle_text for phrase in creature_theme_phrases) or
            self._has_creature_spell_text(oracle_text) or
            self._has_creature_card_text(oracle_text)
        ):
            add_once('creature')
        spell_theme_phrases = [
            'instant or sorcery',
            'instant and sorcery',
            'instant card',
            'sorcery card',
            'instant spell',
            'sorcery spell',
            'whenever you cast a spell',
            'whenever you cast an instant',
            'whenever you cast a sorcery',
            'noncreature spell',
        ]
        if any(phrase in oracle_text for phrase in spell_theme_phrases):
            add_once('instant_sorcery')
        if (
            'graveyard' in oracle_text or
            re.search(r'\b(dies|dying|death)\b', oracle_text) or
            'reanimate' in oracle_text or
            'put into a graveyard' in oracle_text
        ):
            add_once('graveyard')
        if self._has_lifegain_reward_text(oracle_text):
            add_once('lifegain')
        if '+1/+1 counter' in oracle_text or 'proliferate' in oracle_text or 'counter on' in oracle_text:
            add_once('counters')
        if 'token' in oracle_text and any(phrase in oracle_text for phrase in ['create', 'populate', 'copy']):
            if self._has_artifact_token_text(oracle_text) and 'creature token' not in oracle_text:
                add_once('artifact_tokens')
            else:
                add_once('tokens')
        if 'landfall' in oracle_text or 'additional land' in oracle_text or 'land you control enters' in oracle_text:
            add_once('landfall')
        if 'sacrifice' in oracle_text or re.search(r'\b(dies|dying|death)\b', oracle_text):
            add_once('sacrifice')
        blink_phrases = [
            'exile it, then return',
            'exile another target',
            'return it to the battlefield',
            'return those cards to the battlefield',
            'exile any number of target nonland permanents you control',
            'flicker',
        ]
        if any(phrase in oracle_text for phrase in blink_phrases):
            add_once('blink')
        elif 'exile' in oracle_text:
            add_once('exile')
        if any(phrase in oracle_text for phrase in ['equipment', 'aura', 'attach', 'equipped', 'enchanted']):
            add_once('voltron')
        if self._is_board_conversion_commander(oracle_text):
            add_once('board_conversion')
        
        return synergies
    
    def _get_commander_constraints(self, commander_card: Dict) -> Dict:
        """Extract specific constraints from commander abilities"""
        if not commander_card:
            return {}
        
        oracle_text = commander_card.get('oracle_text', '').lower()
        name = commander_card.get('name', '').lower()
        constraints = {}
        
        # Store commander's color identity for validation
        constraints['commander_color_identity'] = commander_card.get('color_identity', [])
        counter_plan = self._counter_plan_for_text(oracle_text)
        if counter_plan:
            constraints['counter_plan'] = counter_plan
        
        # Zur the Enchanter: "mana value 3 or less"
        if 'zur' in name and 'enchant' in name.lower():
            if 'mana value 3 or less' in oracle_text or 'mana cost 3 or less' in oracle_text:
                constraints['max_enchantment_cmc'] = 3
        
        # Brago, King Eternal: only targets permanents you control
        if 'brago' in name:
            constraints['own_permanents_only'] = True
        
        # Yisan: fetches creatures based on verse counters
        if 'yisan' in name:
            constraints['creature_cmc_progressive'] = True
        
        # Sisay: legendary matters
        if 'sisay' in name:
            constraints['legendary_only'] = True
        
        # Atla Palani: only creatures with no abilities
        if 'atla' in name:
            constraints['vanilla_creatures'] = True
        
        # Match "mana value X or less" patterns
        mana_value_match = re.search(r'mana (?:value|cost) (\d+) or less', oracle_text)
        if mana_value_match:
            constraints['max_tutor_cmc'] = int(mana_value_match.group(1))
        
        # Match "power X or less" for creature tutors
        power_match = re.search(r'power (\d+) or less', oracle_text)
        if power_match:
            constraints['max_power'] = int(power_match.group(1))
        
        return constraints
    
    def _calculate_effective_cmc(self, card: Dict) -> int:
        """
        Calculate effective CMC, treating X as minimum 1.
        Scryfall reports X=0 in CMC, but for deck building X should be treated as at least 1.
        """
        cmc = card.get('cmc', 0)
        mana_cost = card.get('mana_cost', '')
        
        # If mana cost contains X, add 1 to CMC (X cannot be 0)
        if 'X' in mana_cost.upper():
            return cmc + 1
        
        return cmc
    
    def _get_correct_face_for_validation(self, card: Dict, target_type: str = 'enchantment') -> Dict:
        """For double-faced cards, get the correct face for validation"""
        # Check if card has multiple faces
        card_faces = card.get('card_faces', [])
        
        if not card_faces or len(card_faces) < 2:
            # Single-faced card, return as is
            return card
        
        # For double-faced cards, check which face matches the target type
        for face in card_faces:
            type_line = face.get('type_line', '').lower()
            if target_type.lower() in type_line:
                # Return a modified card dict with this face's properties
                return {
                    **card,
                    'type_line': face.get('type_line'),
                    'oracle_text': face.get('oracle_text', ''),
                    'mana_cost': face.get('mana_cost', ''),
                    'cmc': face.get('cmc', card.get('cmc', 0)),
                    'colors': face.get('colors', card.get('colors', [])),
                    # Color identity must be checked from the full card
                    'color_identity': card.get('color_identity', [])
                }
        
        # If no matching face found, return the first face
        return {
            **card,
            'type_line': card_faces[0].get('type_line'),
            'oracle_text': card_faces[0].get('oracle_text', ''),
            'mana_cost': card_faces[0].get('mana_cost', ''),
            'cmc': card_faces[0].get('cmc', card.get('cmc', 0)),
            'colors': card_faces[0].get('colors', card.get('colors', [])),
            'color_identity': card.get('color_identity', [])
        }
    
    def _is_legal_for_deck(self, card: Dict, commander_color_identity: List[str]) -> bool:
        """Check if a card is legal for the deck based on color identity"""
        card_color_identity = card.get('color_identity', [])
        
        # A card is legal if all its colors are in the commander's color identity
        for color in card_color_identity:
            if color not in commander_color_identity:
                return False
        
        return True
    
    def _calculate_stats(self, cards: List[Dict], commander: Optional[str], 
                        commander_synergies: List[str]) -> Dict:
        """Calculate enhanced deck statistics"""
        stats = {
            'total_cards': 0,
            'unique_cards': len(cards),
            'lands': 0,
            'nonlands': 0,
            'avg_cmc': 0,
            'cmc_distribution': defaultdict(int),
            'color_distribution': defaultdict(int),
            'role_counts': defaultdict(int),
            'etb_tapped_lands': 0,
            'total_lands': 0,
            'synergy_tags': defaultdict(int),
            'synergy_score': 0,
            'commander_synergy_cards': 0
        }
        
        total_cmc = 0
        cmc_count = 0
        
        for card in cards:
            qty = card.get('qty', 1)
            stats['total_cards'] += qty
            
            card_name = card.get('name', '')
            type_line = card.get('type_line', '')
            oracle_text = card.get('oracle_text', '').lower()
            cmc = card.get('cmc', 0)
            colors = card.get('colors', [])
            tags = card.get('tags', [])
            
            # Count lands
            if 'Land' in type_line:
                stats['lands'] += qty
                stats['total_lands'] += qty
                
                if 'enters the battlefield tapped' in oracle_text or 'enters tapped' in oracle_text:
                    stats['etb_tapped_lands'] += qty
            else:
                stats['nonlands'] += qty
                total_cmc += cmc * qty
                cmc_count += qty
            
            # CMC distribution
            if cmc <= 1:
                stats['cmc_distribution']['0-1'] += qty
            elif cmc == 2:
                stats['cmc_distribution']['2'] += qty
            elif cmc == 3:
                stats['cmc_distribution']['3'] += qty
            elif cmc == 4:
                stats['cmc_distribution']['4'] += qty
            elif cmc == 5:
                stats['cmc_distribution']['5'] += qty
            else:
                stats['cmc_distribution']['6+'] += qty
            
            # Color distribution
            for color in colors:
                stats['color_distribution'][color] += qty
            
            # Role detection
            roles = self._detect_roles(oracle_text, type_line, card_name)
            for role in roles:
                stats['role_counts'][role] += qty
            
            # Synergy tags
            for tag in tags:
                stats['synergy_tags'][tag] += 1
            
            # Commander synergy score
            card_synergies = self._detect_card_synergies(oracle_text, type_line)
            matching_synergies = set(card_synergies) & set(commander_synergies)
            if matching_synergies:
                stats['commander_synergy_cards'] += 1
                stats['synergy_score'] += len(matching_synergies)
        
        # Average CMC
        if cmc_count > 0:
            stats['avg_cmc'] = round(total_cmc / cmc_count, 2)
        
        return stats
    
    def _detect_card_synergies(self, oracle_text: str, type_line: str) -> List[str]:
        """Detect what synergies a card provides"""
        synergies = []
        for synergy_type, keywords in self.synergy_keywords.items():
            if synergy_type == 'creature':
                creature_keywords = [
                    keyword for keyword in keywords
                    if keyword not in ['creature spell', 'creature card']
                ]
                if (
                    any(keyword in oracle_text or keyword in type_line for keyword in creature_keywords) or
                    self._has_creature_spell_text(oracle_text) or
                    self._has_creature_card_text(oracle_text)
                ):
                    synergies.append(synergy_type)
                continue
            if any(keyword in oracle_text or keyword in type_line for keyword in keywords):
                synergies.append(synergy_type)
        return synergies
    
    def _detect_roles(self, oracle_text: str, type_line: str, card_name: str) -> List[str]:
        """Detect card roles from oracle text"""
        roles = []
        
        # Draw
        if self._has_card_draw_text(oracle_text):
            roles.append('draw')
        
        # Ramp
        if any(word in oracle_text for word in ['search your library for', 'add', 'treasure']) and \
           ('land' in oracle_text or 'mana' in oracle_text):
            roles.append('ramp')
        
        # Removal
        if any(word in oracle_text for word in ['destroy target', 'exile target']):
            roles.append('removal')
        
        # Sweeper
        if any(word in oracle_text for word in ['destroy all', 'exile all', '-x/-x']):
            roles.append('sweeper')
        
        # Interaction. Avoid counting +1/+1 or -1/-1 counters as stack interaction.
        if (
            'counter target spell' in oracle_text or
            'counter target activated' in oracle_text or
            'counter target triggered' in oracle_text or
            'counter target ability' in oracle_text or
            'prevent all damage' in oracle_text or
            'prevent the next' in oracle_text
        ):
            roles.append('interaction')
        
        # Protection
        if any(word in oracle_text for word in ['protection', 'hexproof', 'indestructible', 'ward']):
            roles.append('protection')
        
        return roles
    
    def _identify_gaps(self, stats: Dict, color_identity: List[str], 
                      commander_synergies: List[str]) -> Dict:
        """Identify deck weaknesses and gaps"""
        gaps = {
            'roles': {},
            'cmc': {},
            'lands': {},
            'colors': [],
            'synergy': []
        }
        
        # Role gaps
        for role, (min_target, max_target) in self.role_targets.items():
            current = stats['role_counts'].get(role, 0)
            if current < min_target:
                gaps['roles'][role] = min_target - current
        
        # Land count
        if stats['total_lands'] < 36:
            gaps['lands']['count'] = 36 - stats['total_lands']
        
        # ETB tapped ratio
        if stats['total_lands'] > 0:
            tapped_ratio = stats['etb_tapped_lands'] / stats['total_lands']
            if tapped_ratio > 0.3:
                gaps['lands']['too_many_tapped'] = True
        
        # Synergy gaps - prioritize commander synergies
        if commander_synergies:
            gaps['synergy'] = commander_synergies
        
        return gaps
    
    def _detect_deck_themes(self, cards: List[Dict], commander_synergies: List[str]) -> List[str]:
        """Detect prominent mechanical themes in the deck"""
        theme_counts = defaultdict(int)
        
        for card in cards:
            oracle_text = card.get('oracle_text', '').lower()
            type_line = card.get('type_line', '').lower()
            
            # Count theme occurrences
            if 'enchantment' in type_line and any(phrase in oracle_text for phrase in [
                'whenever an enchantment',
                'whenever you cast an enchantment',
                'enchantress',
                'enchantment card',
                'enchantment spell',
            ]):
                theme_counts['enchantress'] += 1
            if 'artifact' in type_line:
                theme_counts['artifacts'] += 1
            if 'equipment' in type_line or 'equip' in oracle_text:
                theme_counts['voltron'] += 1
            if any(w in oracle_text for w in ['graveyard', 'dies', 'reanimate']):
                theme_counts['graveyard'] += 1
            if '+1/+1 counter' in oracle_text or '-1/-1 counter' in oracle_text or 'proliferate' in oracle_text or 'put a counter' in oracle_text:
                theme_counts['counters'] += 1
            if 'token' in oracle_text and ('create' in oracle_text or 'double' in oracle_text or 'twice' in oracle_text):
                theme_counts['tokens'] += 1
            if 'landfall' in oracle_text:
                theme_counts['landfall'] += 1
            if 'sacrifice' in oracle_text:
                theme_counts['aristocrats'] += 1
            if any(w in oracle_text for w in ['instant', 'sorcery']) and 'cast' in oracle_text:
                theme_counts['spellslinger'] += 1
        
        theme_thresholds = {
            'enchantress': 3,
            'artifacts': 8,
            'voltron': 4,
            'graveyard': 5,
            'counters': 4,
            'tokens': 4,
            'landfall': 4,
            'aristocrats': 4,
            'spellslinger': 5,
        }
        return [
            theme for theme, count in theme_counts.items()
            if count >= theme_thresholds.get(theme, 5)
        ]

    def _legal_example_names(
        self,
        candidates: List[tuple],
        color_identity: Optional[List[str]],
        limit: int = 3
    ) -> str:
        """Return example card names that fit the commander's color identity."""
        commander_colors = set(color_identity or [])
        legal_names = [
            name for name, card_colors in candidates
            if set(card_colors).issubset(commander_colors)
        ]
        return ", ".join(legal_names[:limit])

    def _role_examples(
        self,
        role: str,
        color_identity: Optional[List[str]],
        commander_synergies: Optional[List[str]] = None
    ) -> str:
        """Choose color-legal examples so tips do not recommend off-identity cards."""
        commander_synergies = commander_synergies or []

        if role == 'draw' and 'enchantment' in commander_synergies:
            examples = self._legal_example_names([
                ("Mystic Remora", ["U"]),
                ("Rhystic Study", ["U"]),
                ("Necropotence", ["B"]),
                ("Enchantress's Presence", ["G"]),
                ("Mesa Enchantress", ["W"]),
                ("Eidolon of Blossoms", ["G"]),
                ("Sythis, Harvest's Hand", ["G", "W"]),
            ], color_identity)
            if examples:
                return examples

        if role == 'draw' and 'artifact' in commander_synergies:
            examples = self._legal_example_names([
                ("The One Ring", []),
                ("Idol of Oblivion", []),
                ("Esper Sentinel", ["W"]),
                ("Thought Monitor", ["U"]),
                ("Mystic Forge", []),
            ], color_identity)
            if examples:
                return examples

        examples_by_role = {
            'draw': [
                ("Esper Sentinel", ["W"]),
                ("Mystic Remora", ["U"]),
                ("Rhystic Study", ["U"]),
                ("Phyrexian Arena", ["B"]),
                ("Toski, Bearer of Secrets", ["G"]),
                ("Skullclamp", []),
                ("The One Ring", []),
            ],
            'ramp': [
                ("Sol Ring", []),
                ("Arcane Signet", []),
                ("Fellwar Stone", []),
                ("Nature's Lore", ["G"]),
                ("Three Visits", ["G"]),
                ("Talisman cycle", []),
            ],
            'interaction': [
                ("Swords to Plowshares", ["W"]),
                ("Counterspell", ["U"]),
                ("Arcane Denial", ["U"]),
                ("Swan Song", ["U"]),
                ("Heroic Intervention", ["G"]),
                ("Veil of Summer", ["G"]),
                ("Deadly Rollick", ["B"]),
                ("Chaos Warp", ["R"]),
                ("Lightning Greaves", []),
                ("Swiftfoot Boots", []),
            ],
            'enchantment': [
                ("Mystic Remora", ["U"]),
                ("Rhystic Study", ["U"]),
                ("Necropotence", ["B"]),
                ("Sterling Grove", ["G", "W"]),
                ("Enchantress's Presence", ["G"]),
                ("Grasp of Fate", ["W"]),
                ("Diplomatic Immunity", ["U"]),
            ],
            'voltron': [
                ("Lightning Greaves", []),
                ("Swiftfoot Boots", []),
                ("Whispersilk Cloak", []),
                ("All That Glitters", ["W"]),
                ("Rancor", ["G"]),
                ("Blackblade Reforged", []),
            ],
        }
        return self._legal_example_names(examples_by_role.get(role, []), color_identity)
    
    def _generate_playstyle_tips(self, stats: Dict, commander_synergies: List[str], 
                                  detected_themes: List[str], commander: Optional[str],
                                  color_identity: Optional[List[str]] = None,
                                  commander_card: Optional[Dict] = None) -> List[str]:
        """Generate specific playstyle tips based on deck analysis"""
        tips = []
        commander_name = commander or "your commander"
        commander_text = commander_card.get('oracle_text', '').lower() if commander_card else ''
        commander_type = commander_card.get('type_line', '').lower() if commander_card else ''
        
        # Mana base tips
        land_count = stats.get('total_lands', 0)
        if land_count < 36:
            tips.append(f"Your land count ({land_count}) is below the recommended 36-38. Consider adding {36 - land_count} more lands or mana rocks.")
        elif land_count > 38:
            tips.append(f"You're running {land_count} lands. Consider cutting {land_count - 38} for more action spells.")
        
        # Draw engine tips
        draw_count = stats.get('role_counts', {}).get('draw', 0)
        if draw_count < 8:
            draw_examples = self._role_examples('draw', color_identity, commander_synergies)
            if draw_examples:
                tips.append(f"Your deck needs {8 - draw_count} more draw sources. Prioritize engines that match {commander_name}'s plan, such as {draw_examples}.")
            else:
                tips.append(f"Your deck needs {8 - draw_count} more draw sources. Prefer repeatable engines tied to your main theme over one-shot cantrips.")
        
        # Ramp tips
        ramp_count = stats.get('role_counts', {}).get('ramp', 0)
        if ramp_count < 10:
            ramp_examples = self._role_examples('ramp', color_identity, commander_synergies)
            if ramp_examples:
                tips.append(f"Add {10 - ramp_count} more ramp pieces. Start with efficient fixing that fits the color identity, such as {ramp_examples}.")
            else:
                tips.append(f"Add {10 - ramp_count} more ramp pieces. Prioritize two-mana acceleration so the commander and support engines come online earlier.")
        
        # Theme-specific tips
        if 'counters' in detected_themes or 'counters' in commander_synergies:
            if 'proliferate' in commander_text:
                counter_kind = "-1/-1 counters" if "-1/-1 counter" in commander_text else "+1/+1 counters" if "+1/+1 counter" in commander_text else "counters"
                tips.append(f"Counter Strategy: Make sure the deck reliably places {counter_kind} before leaning on proliferate. {commander_name} gets stronger when every proliferate trigger has several meaningful targets.")
            else:
                tips.append(f"Counter Strategy: Prioritize repeatable counter placement and payoffs over single combat tricks so {commander_name}'s board keeps scaling after the first setup turn.")

        if 'tokens' in detected_themes or 'tokens' in commander_synergies:
            if 'elf' in commander_text or 'elf' in commander_type:
                token_focus = "Elf token makers that also tap for mana or scale with creature count"
            elif 'creature token' in commander_text or 'populate' in commander_text:
                token_focus = "creature token makers and token payoffs"
            else:
                token_focus = "token makers that leave useful bodies or resources behind"
            tips.append(f"Token Strategy: Favor {token_focus}. That gives {commander_name} more material to convert into pressure, sacrifice value, or board-wide payoffs.")

        if 'aristocrats' in detected_themes:
            tips.append(
                "Aristocrats Strategy: Death triggers and sacrifice outlets are most useful when they convert expendable creatures into cards, drain, or recursion. Prioritize repeatable outlets over one-shot effects."
            )

        if 'enchantress' in detected_themes:
            enchantment_examples = self._role_examples('enchantment', color_identity, commander_synergies)
            if enchantment_examples:
                tips.append(f"Enchantress Strategy: Keep the enchantment count high enough that each payoff chains into the next. Strong role players for this color identity include {enchantment_examples}.")
            else:
                tips.append("Enchantress Strategy: Keep the enchantment count high enough that each payoff chains into the next, and protect the key engine before committing too many pieces.")
        
        if 'voltron' in detected_themes:
            voltron_examples = self._role_examples('voltron', color_identity, commander_synergies)
            tips.append(f"Voltron Strategy: Protect {commander_name} before stacking damage. {voltron_examples or 'Cheap protection, evasion, and haste effects'} are better early additions than expensive power-only Equipment.")
        
        if 'graveyard' in detected_themes:
            tips.append(f"Graveyard Strategy: Your recursion package can help rebuild after wipes, but it also means graveyard hate is a real pressure point. Keep a few ways to recover key creatures or shuffle important cards back.")
        
        # Interaction tips
        interaction_count = stats.get('role_counts', {}).get('interaction', 0)
        if interaction_count < 5:
            interaction_examples = self._role_examples('interaction', color_identity, commander_synergies)
            if interaction_examples:
                tips.append(f"Add low-cost protection or disruption such as {interaction_examples} so {commander_name}'s engine survives wipes, removal, and combo turns.")
            else:
                tips.append(f"Add a few low-cost protection or disruption pieces that fit your colors so {commander_name}'s main engine can survive removal-heavy tables.")
        
        return tips

    def _generate_deep_deck_playstyle_tips(
        self,
        stats: Dict,
        commander_synergies: List[str],
        detected_themes: List[str],
        commander: Optional[str],
        cards: List[Dict],
        color_identity: Optional[List[str]] = None,
    ) -> List[str]:
        """Add visibly deeper deterministic notes for opt-in deck analysis."""
        tips = []
        commander_name = commander or "your commander"
        role_counts = stats.get('role_counts', {})
        total_cards = max(stats.get('total_cards', 0), 1)
        themes = list(dict.fromkeys([*commander_synergies, *detected_themes]))
        nonland_cards = [
            card for card in cards
            if 'land' not in card.get('type_line', '').lower()
        ]
        high_mv_cards = [
            card for card in nonland_cards
            if card.get('cmc', 0) >= 5
        ]
        early_cards = [
            card for card in nonland_cards
            if card.get('cmc', 0) <= 2
        ]

        if themes:
            tips.append(
                f"Deep Analysis - Theme Density: The deeper pass is checking whether support cards reinforce {', '.join(themes[:4])} instead of only filling generic Commander roles. Off-theme cards should justify their slot with unusually strong draw, ramp, removal, or protection."
            )

        if high_mv_cards:
            high_mv_share = round((len(high_mv_cards) / total_cards) * 100)
            tips.append(
                f"Deep Analysis - Curve Pressure: {len(high_mv_cards)} nonland cards cost five or more mana ({high_mv_share}% of the deck). Keep the expensive cards that directly close games or multiply {commander_name}'s engine, then trim expensive value pieces first."
            )

        if early_cards:
            tips.append(
                f"Deep Analysis - Setup Window: {len(early_cards)} nonland cards cost two or less. Use those slots to establish ramp, protection, or theme material before {commander_name} arrives, not just low-impact filler."
            )

        low_roles = []
        for role, target in self.role_targets.items():
            count = role_counts.get(role, 0)
            if count < target[0]:
                low_roles.append(f"{role} ({count}/{target[0]})")
        if low_roles:
            tips.append(
                f"Deep Analysis - Role Coverage: The weakest role bands are {', '.join(low_roles[:4])}. Prioritize upgrades that patch one of these gaps while still matching the commander's main plan."
            )

        if color_identity:
            tips.append(
                "Deep Analysis - Color Discipline: Recommendations stay inside commander color identity, but color fixing still matters. Favor flexible fixing when the deck has several double-pip spells or wants to cast the commander on curve."
            )

        return tips
    
    def _generate_combo_suggestions(self, commander: Optional[str], 
                                     commander_synergies: List[str], cards: List[Dict]) -> List[Dict]:
        """Suggest specific combos based on commander and deck contents"""
        combos = []
        
        card_names = {card['name'].lower() for card in cards}
        
        # Enchantment combos
        if 'enchantment' in commander_synergies:
            if commander and 'zur' in commander.lower():
                combos.append({
                    'name': 'Zur Lock',
                    'cards': ['Zur the Enchanter', 'Steel of the Godhead', 'Diplomatic Immunity'],
                    'description': 'Make Zur unblockable and give him shroud. Tutor protective enchantments.',
                    'power_level': 'High'
                })
                combos.append({
                    'name': 'Shimmer Zur',
                    'cards': ['Zur the Enchanter', 'Shimmer Myr', 'Any 3-CMC Enchantment'],
                    'description': 'Flash in Zur on opponent\'s end step, attack immediately on your turn.',
                    'power_level': 'Medium'
                })
        
        return combos
    
    async def _generate_additions(self, gaps: Dict, commander: Optional[str], 
                                   color_identity: List[str], current_cards: List[Dict],
                                   commander_synergies: List[str], commander_data: Optional[Dict],
                                   categories: Optional[List[str]] = None,
                                   commander_constraints: Optional[Dict] = None,
                                   search_budget: int = 5) -> List[Dict]:
        """Generate enhanced card addition suggestions with commander synergy and categories"""
        suggestions = []
        current_card_names = {card['name'].lower() for card in current_cards}
        suggested_names = set()
        
        # Build prioritized search queries based on categories or gaps
        queries = []
        
        # If categories specified, filter by those
        if categories:
            color_filter = self._color_identity_filter(color_identity)
            category_map = {
                'ramp': ('ramp', f"(o:search o:land OR o:treasure OR t:mana) {color_filter} f:commander"),
                'draw': ('draw', f"o:draw {color_filter} f:commander"),
                'removal': ('removal', f"(o:destroy o:target OR o:exile o:target) {color_filter} f:commander"),
                'counter': ('counter', f"o:counter o:target o:spell {color_filter} f:commander"),
                'recursion': ('recursion', f"(o:return o:graveyard OR o:reanimate) {color_filter} f:commander"),
                'tutor': ('tutor', f"(o:search o:library OR o:tutor) {color_filter} f:commander"),
                'protection': ('protection', f"(o:protection OR o:hexproof OR o:indestructible) {color_filter} f:commander"),
                'sweeper': ('sweeper', f"(o:destroy o:all OR o:exile o:all) {color_filter} f:commander")
            }
            for cat in categories:
                if cat.lower() in category_map:
                    role, query = category_map[cat.lower()]
                    queries.append((role, query))
        else:
            # Priority 1: Commander synergy cards with constraints
            if commander_data and commander_synergies:
                for synergy in commander_synergies:
                    query = self._build_query_for_synergy(synergy, color_identity, commander_constraints)
                    if query:
                        queries.append((f'synergy:{synergy}', query))
        
            # Priority 2: Role gaps
            if 'draw' in gaps['roles']:
                queries.append((
                    'draw',
                    f"o:draw {self._color_identity_filter(color_identity)} f:commander"
                ))
            
            if 'ramp' in gaps['roles']:
                queries.append((
                    'ramp',
                    f"(o:search o:land OR o:treasure OR t:mana) {self._color_identity_filter(color_identity)} f:commander"
                ))
            
            if 'protection' in gaps['roles']:
                queries.append((
                    'protection',
                    f"(o:protection OR o:hexproof OR o:indestructible) {self._color_identity_filter(color_identity)} f:commander"
                ))

            if 'removal' in gaps['roles']:
                queries.append((
                    'removal',
                    f"(o:destroy o:target OR o:exile o:target) {self._color_identity_filter(color_identity)} f:commander"
                ))

            if 'sweeper' in gaps['roles']:
                queries.append((
                    'sweeper',
                    f"(o:destroy o:all OR o:exile o:all OR o:-x/-x) {self._color_identity_filter(color_identity)} f:commander"
                ))
            
            if 'interaction' in gaps['roles']:
                queries.append((
                    'interaction',
                    f"o:counter {self._color_identity_filter(color_identity)} f:commander"
                ))
            
        # Execute searches
        for role, query in queries[:search_budget]:
            try:
                results = await self.scryfall.search_cards_by_criteria(query, limit=20)
                requested_synergy = role.split(':', 1)[1] if role.startswith('synergy:') else None
                display_role = requested_synergy or role
                cards_added_for_query = 0
                max_cards_for_query = 5 if requested_synergy else 2
                for card in results:
                    if cards_added_for_query >= max_cards_for_query:
                        break
                    card_name = card.get('name', '').lower()
                    if card_name in current_card_names or card_name in suggested_names:
                        continue
                    
                    # CRITICAL COLOR IDENTITY CHECK: Must be legal for deck
                    commander_colors = commander_constraints.get('commander_color_identity', color_identity)
                    if not self._is_legal_for_deck(card, commander_colors):
                        continue  # Skip cards with colors outside commander's identity
                    
                    # For double-faced cards, always get the correct face for validation
                    card_to_validate = card
                    # Check if card has multiple faces
                    if card.get('card_faces') and len(card.get('card_faces', [])) > 1:
                        # For enchantment-focused commanders with CMC constraints
                        if commander_constraints.get('max_enchantment_cmc'):
                            card_to_validate = self._get_correct_face_for_validation(card, 'enchantment')
                        # For any tutor with CMC constraints, check based on role
                        elif commander_constraints.get('max_tutor_cmc'):
                            if 'enchantment' in role:
                                card_to_validate = self._get_correct_face_for_validation(card, 'enchantment')
                            elif 'artifact' in role:
                                card_to_validate = self._get_correct_face_for_validation(card, 'artifact')
                            elif 'creature' in role:
                                card_to_validate = self._get_correct_face_for_validation(card, 'creature')
                    
                    extracted = self.scryfall.extract_card_data(card_to_validate)
                    extracted_name = extracted['name'].lower()
                    if extracted_name in current_card_names or extracted_name in suggested_names:
                        continue
                    if requested_synergy:
                        if not self._card_matches_synergy(extracted, requested_synergy):
                            continue
                        if commander_data and not self._card_matches_commander_context(extracted, requested_synergy, commander_data):
                            continue
                        if self._is_generic_mana_card(extracted):
                            continue
                    elif not self._card_matches_role(extracted, display_role):
                        continue
                    
                    # Calculate effective CMC (handles X costs)
                    effective_cmc = self._calculate_effective_cmc(card_to_validate)
                    
                    # CRITICAL: Apply commander-specific constraints
                    if commander_constraints:
                        # Check CMC constraints (e.g., Zur can only tutor CMC 3 or less)
                        if 'max_enchantment_cmc' in commander_constraints:
                            if 'enchantment' in extracted['type_line'].lower():
                                if effective_cmc > commander_constraints['max_enchantment_cmc']:
                                    continue  # Skip this card, it violates constraints
                        
                        if 'max_tutor_cmc' in commander_constraints:
                            if effective_cmc > commander_constraints['max_tutor_cmc']:
                                continue
                        
                        # Check legendary constraint
                        if commander_constraints.get('legendary_only'):
                            if 'legendary' not in extracted['type_line'].lower():
                                continue
                        
                        # Check power constraint
                        if 'max_power' in commander_constraints:
                            card_power = card_to_validate.get('power')
                            if card_power and card_power.isdigit():
                                if int(card_power) > commander_constraints['max_power']:
                                    continue
                    
                    price = self._extract_price(extracted['prices'])
                    
                    # Get card images (handles double-faced cards)
                    image_data = self._get_card_images(card)
                    
                    # Generate specific, contextual reasoning with constraints
                    if requested_synergy and commander_data:
                        quality = self._recommendation_quality_metadata(
                            extracted,
                            requested_synergy,
                            commander_data,
                        )
                        if quality['score'] < 76 or not quality.get('evidence_tags') or quality.get('confidence') == 'speculative':
                            continue
                        reason = self._generate_validated_recommendation_reason(
                            extracted,
                            commander or "your commander",
                            requested_synergy,
                            quality
                        )
                    else:
                        quality = self._role_recommendation_quality_metadata(extracted, display_role, gaps)
                        if quality['score'] < 76 or quality.get('fit_tier') == 'Speculative':
                            continue
                        reason = self._generate_validated_role_reason(extracted, display_role, quality)
                    
                    suggestion = {
                        'card_name': extracted['name'],
                        'reason': reason,
                        'role_tag': display_role,
                        'cmc': effective_cmc,  # Use effective CMC that accounts for X costs
                        'price': price,
                        'synergy_tags': self._detect_card_synergies(
                            extracted['oracle_text'].lower(), 
                            extracted['type_line'].lower()
                        ),
                        'confidence': 0.9 if requested_synergy else quality['confidence'],
                        'fit_tier': quality['fit_tier'],
                        'score': quality['score'],
                        'evidence': quality['evidence'],
                        'evidence_tags': quality['evidence_tags'],
                        'penalty_tags': quality['penalty_tags'],
                        'image_url': image_data['front'],
                        'image_url_back': image_data['back']
                    }
                    suggestions.append(suggestion)
                    suggested_names.add(extracted_name)
                    cards_added_for_query += 1
                    
                    if len(suggestions) >= 15:
                        break
                
                if len(suggestions) >= 15:
                    break
            except Exception as e:
                logger.error(f"Error generating additions for {role}: {str(e)}")
        
        # Sort by priority: synergy first, then by role importance
        priority_order = {
            'counters': 0,
            'tokens': 1,
            'creature': 2,
            'graveyard': 3,
            'draw': 4,
            'ramp': 5,
            'removal': 6,
            'sweeper': 7,
            'protection': 8,
            'interaction': 9
        }
        suggestions.sort(key=lambda x: (priority_order.get(x['role_tag'], 99), -x['confidence']))
        
        return suggestions[:10]
    
    async def _generate_cuts(self, cards: List[Dict], gaps: Dict, stats: Dict, 
                       commander_synergies: List[str], detected_themes: Optional[List[str]] = None) -> List[Dict]:
        """Generate intelligent cut suggestions with images"""
        suggestions = []
        suggested_names = set()
        protected_themes = set(commander_synergies) | set(detected_themes or [])
        
        # Expand cards for analysis (don't cut basics with qty > 1)
        expanded_cards = []
        for card in cards:
            if 'Basic Land' in card.get('type_line', ''):
                expanded_cards.append(card)  # Keep as single entry
            else:
                expanded_cards.append(card)
        
        # Priority 1: High CMC cards (6+) with weak synergy
        high_cmc_cards = [c for c in expanded_cards 
                         if c.get('cmc', 0) >= 6 
                         and 'Land' not in c.get('type_line', '')
                         and not self._card_supports_themes(c, protected_themes)]
        
        high_cmc_cards.sort(key=lambda x: x.get('cmc', 0), reverse=True)
        
        for card in high_cmc_cards[:3]:
            card_key = card.get('name', '').lower()
            if card_key in suggested_names:
                continue
            # Fetch card image
            scryfall_card = await self.scryfall.search_card(card['name'])
            image_data = self._get_card_images(scryfall_card) if scryfall_card else {'front': None, 'back': None}
            
            suggestions.append({
                'card_name': card['name'],
                'reason': self._generate_cut_reason(card, 'curve_optimization', protected_themes),
                'role_tag': 'curve_optimization',
                'cmc': card.get('cmc', 0),
                'price': 0,
                'synergy_tags': card.get('tags', []),
                'confidence': 0.75,
                'image_url': image_data['front'],
                'image_url_back': image_data['back']
            })
            suggested_names.add(card_key)
        
        # Priority 2: ETB tapped lands
        if gaps.get('lands', {}).get('too_many_tapped'):
            tapped_lands = [c for c in expanded_cards 
                           if 'Land' in c.get('type_line', '') 
                           and 'Basic' not in c.get('type_line', '')
                           and 'enters the battlefield tapped' in c.get('oracle_text', '').lower()]
            
            for card in tapped_lands[:2]:
                card_key = card.get('name', '').lower()
                if card_key in suggested_names:
                    continue
                scryfall_card = await self.scryfall.search_card(card['name'])
                image_data = self._get_card_images(scryfall_card) if scryfall_card else {'front': None, 'back': None}
                
                suggestions.append({
                    'card_name': card['name'],
                    'reason': "Enters tapped, slowing your tempo. Replace with untapped alternatives for faster plays.",
                    'role_tag': 'mana_base_optimization',
                    'cmc': 0,
                    'price': 0,
                    'synergy_tags': [],
                    'confidence': 0.8,
                    'image_url': image_data['front'],
                    'image_url_back': image_data['back']
                })
                suggested_names.add(card_key)
        
        # Priority 3: Cards with no synergy or weak roles
        weak_cards = [
            c for c in expanded_cards
            if not self._card_supports_themes(c, protected_themes)
            and not self._fills_needed_role(c, stats)
            and 'Land' not in c.get('type_line', '')
            and 'Basic' not in c.get('type_line', '')
            and c.get('cmc', 0) > 3
        ]
        
        for card in weak_cards[:(10 - len(suggestions))]:
            card_key = card.get('name', '').lower()
            if card_key in suggested_names:
                continue
            scryfall_card = await self.scryfall.search_card(card['name'])
            image_data = self._get_card_images(scryfall_card) if scryfall_card else {'front': None, 'back': None}
            
            suggestions.append({
                'card_name': card['name'],
                'reason': self._generate_cut_reason(card, 'synergy_optimization', protected_themes),
                'role_tag': 'synergy_optimization',
                'cmc': card.get('cmc', 0),
                'price': 0,
                'synergy_tags': card.get('tags', []),
                'confidence': 0.6,
                'image_url': image_data['front'],
                'image_url_back': image_data['back']
            })
            suggested_names.add(card_key)
        
        return suggestions[:10]

    def _card_supports_themes(self, card: Dict, themes: set) -> bool:
        """Check whether a card supports commander synergies or detected deck themes."""
        oracle_text = card.get('oracle_text', '').lower()
        type_line = card.get('type_line', '').lower()
        tags = set(card.get('tags', []))
        synergies = set(self._detect_card_synergies(oracle_text, type_line))

        if tags & themes or synergies & themes:
            return True
        if 'counters' in themes and (
            '+1/+1 counter' in oracle_text or
            '-1/-1 counter' in oracle_text or
            'proliferate' in oracle_text or
            'put one or more counters' in oracle_text or
            'twice that many of those counters' in oracle_text
        ):
            return True
        if 'tokens' in themes and self._is_creature_token_support(oracle_text, type_line):
            return True
        if 'aristocrats' in themes and any(phrase in oracle_text for phrase in ['sacrifice', 'dies', 'whenever another creature dies']):
            return True
        if 'graveyard' in themes and self._is_graveyard_value_card(oracle_text, type_line):
            return True
        return False

    def _fills_needed_role(self, card: Dict, stats: Dict) -> bool:
        """Avoid cutting scarce utility roles the deck is currently short on."""
        oracle_text = card.get('oracle_text', '').lower()
        type_line = card.get('type_line', '').lower()
        roles = self._detect_roles(oracle_text, type_line, card.get('name', ''))

        for role in roles:
            target = self.role_targets.get(role)
            if target and stats.get('role_counts', {}).get(role, 0) <= target[0]:
                return True
        return False

    def _card_matches_role(self, card_data: Dict, role: str) -> bool:
        """Validate that a search result is a meaningful fit for a role query."""
        name = card_data.get('name', '').lower()
        oracle_text = card_data.get('oracle_text', '').lower()
        type_line = card_data.get('type_line', '').lower()

        if role == 'draw':
            if 'add' in oracle_text and 'mana' in oracle_text and 'artifact' in type_line:
                return False
            if name in {'solemn simulacrum', 'commanders sphere', "commander's sphere", 'mind stone'}:
                return False
            return self._has_card_draw_text(oracle_text)
        if role == 'ramp':
            return (
                'search your library for' in oracle_text and 'land' in oracle_text
            ) or (
                'add' in oracle_text and ('mana' in oracle_text or '{' in oracle_text)
            ) or 'treasure token' in oracle_text
        if role == 'removal':
            if self._is_graveyard_hate(oracle_text):
                return False
            return any(phrase in oracle_text for phrase in [
                'destroy target',
                'exile target creature',
                'exile target artifact',
                'exile target enchantment',
                'exile target permanent',
                'exile target nonland',
            ])
        if role == 'sweeper':
            return any(phrase in oracle_text for phrase in ['destroy all', 'exile all', '-x/-x'])
        if role == 'protection':
            return any(phrase in oracle_text for phrase in ['hexproof', 'indestructible', 'protection from', 'ward'])
        if role == 'interaction':
            return any(phrase in oracle_text for phrase in [
                'counter target spell',
                'counter target activated',
                'counter target triggered',
                'counter target ability',
                'prevent all damage',
            ])
        return True

    def _role_recommendation_quality_metadata(self, card_data: Dict, role: str, gaps: Dict) -> Dict:
        """Score deck-analysis role fixes separately from commander synergy."""
        oracle_text = card_data.get('oracle_text', '').lower()
        type_line = card_data.get('type_line', '').lower()
        cmc = card_data.get('cmc', 0)
        evidence_tags = ['role_gap'] if role in gaps.get('roles', {}) else []
        penalty_tags = []
        score = 70 if evidence_tags else 62
        evidence = f"fills {role} need"
        job = f"{role} role fix"

        if role == 'draw' and self._has_card_draw_text(oracle_text):
            score += 10
            evidence = 'adds card flow'
            if 'whenever' in oracle_text or 'at the beginning' in oracle_text:
                score += 5
                evidence_tags.append('repeatable_engine')
            evidence_tags.append('card_flow')
        elif role == 'ramp' and self._card_matches_role(card_data, 'ramp'):
            score += 9
            evidence = 'improves mana development'
            evidence_tags.append('mana_development')
            if cmc <= 2:
                score += 4
                evidence_tags.append('low_setup_cost')
        elif role == 'removal' and self._card_matches_role(card_data, 'removal'):
            score += 10
            evidence = 'answers specific threats'
            evidence_tags.append('interaction')
        elif role == 'sweeper' and self._card_matches_role(card_data, 'sweeper'):
            score += 9
            evidence = 'resets wide boards'
            evidence_tags.append('interaction')
        elif role == 'protection' and self._card_matches_role(card_data, 'protection'):
            score += 10
            evidence = 'protects key permanents'
            evidence_tags.append('protection')
        elif role == 'interaction' and self._card_matches_role(card_data, 'interaction'):
            score += 10
            evidence = 'interacts on the stack or prevents damage'
            evidence_tags.append('interaction')
        elif role == 'counter' and 'counter target' in oracle_text:
            score += 18
            evidence = 'counters opposing spells or abilities'
            evidence_tags.append('interaction')
            evidence_tags.append('requested_category')
        elif role == 'recursion' and any(term in oracle_text for term in ['return', 'graveyard', 'reanimate']):
            score += 16
            evidence = 'returns cards from the graveyard'
            evidence_tags.append('role_value')
            evidence_tags.append('requested_category')
        elif role == 'tutor' and ('search your library' in oracle_text or 'tutor' in oracle_text):
            score += 16
            evidence = 'adds library search redundancy'
            evidence_tags.append('role_value')
            evidence_tags.append('requested_category')

        if self._is_generic_mana_card(card_data):
            penalty_tags.append('generic_staple')
            if role != 'ramp':
                score -= 14
        if cmc >= 6 and role not in {'sweeper'}:
            penalty_tags.append('high_mana_value')
            score -= 8
        if 'until end of turn' in oracle_text and role not in {'protection', 'removal'}:
            penalty_tags.append('one_shot_effect')
            score -= 5
        if 'land' in type_line and role not in {'ramp'}:
            penalty_tags.append('wrong_card_type')
            score -= 18

        if len(evidence_tags) <= 1 and score < 78:
            penalty_tags.append('low_evidence')

        score = max(0, min(score, 92))
        if score >= 84:
            fit_tier = 'Strong Role Fix'
            confidence = 0.86
        elif score >= 76:
            fit_tier = 'Role Fix'
            confidence = 0.78
        else:
            fit_tier = 'Speculative'
            confidence = 0.6

        return {
            'job': job,
            'fit_tier': fit_tier,
            'score': score,
            'evidence': evidence,
            'evidence_tags': evidence_tags,
            'penalty_tags': penalty_tags,
            'confidence': confidence,
        }

    def _generate_validated_role_reason(self, card_data: Dict, role: str, quality: Dict) -> str:
        """Explain role fixes without overstating commander synergy."""
        card_name = card_data.get('name', 'This card')
        action = f"{card_name} is a {role} role fix."
        if role == 'draw':
            action = f"{card_name} adds card flow."
        elif role == 'ramp':
            action = f"{card_name} improves mana development."
        elif role in {'removal', 'interaction', 'sweeper'}:
            action = f"{card_name} gives the deck more interaction."
        elif role == 'protection':
            action = f"{card_name} protects key permanents."

        reason = f"{action} It is recommended as a role fix because the analysis found a deck-health need: {quality.get('evidence', role)}."
        penalties = set(quality.get('penalty_tags', []))
        if 'generic_staple' in penalties:
            reason += " This is a role recommendation, not a commander-specific synergy claim."
        if 'high_mana_value' in penalties:
            reason += " Its higher mana value means it should compete with other payoff slots."
        if 'one_shot_effect' in penalties:
            reason += " Because the effect is temporary, it is best used to patch a specific gap."
        return reason

    def _generate_cut_reason(self, card: Dict, cut_type: str, protected_themes: set) -> str:
        """Generate a more concrete explanation for a cut suggestion."""
        name = card.get('name', 'This card')
        cmc = card.get('cmc', 0)
        oracle_text = card.get('oracle_text', '').lower()
        type_line = card.get('type_line', '').lower()
        theme_text = ', '.join(sorted(protected_themes)[:3]) if protected_themes else 'the deck plan'

        if cut_type == 'curve_optimization':
            return (
                f"{name} costs {cmc} mana and does not clearly advance {theme_text}. "
                "Cutting this kind of expensive off-plan card lowers clunky opening hands while keeping room for engines that affect the board sooner."
            )
        if 'elf' in oracle_text or 'elf' in type_line:
            return (
                f"{name} is on-tribe, but its impact is slow for its mana compared with pieces that create multiple Elves, add counters, or proliferate immediately."
            )
        return (
            f"{name} is a reasonable card in isolation, but it is not one of the stronger payoffs for {theme_text}. "
            "This is a good flex slot to upgrade before trimming cards that directly feed the commander or the deck's main engines."
        )
    
    def _generate_card_reasoning(self, card_data: Dict, role: str, commander: Optional[str],
                                 commander_synergies: List[str], gaps: Dict, 
                                 commander_constraints: Optional[Dict] = None) -> str:
        """Generate highly detailed, specific reasoning for why a card fits the deck"""
        card_name = card_data['name']
        oracle_text = card_data['oracle_text']
        oracle_lower = oracle_text.lower()
        type_line = card_data['type_line']
        cmc = card_data['cmc']
        
        # Build ultra-specific contextual reasoning with actual card analysis
        reasons = []
        
        # Commander-specific synergy analysis
        if role == 'synergy':
            if 'enchantment' in commander_synergies and 'enchantment' in type_line.lower():
                # Check if commander can actually tutor this (e.g., Zur's CMC 3 limit)
                can_tutor = True
                tutor_note = ""
                if commander_constraints and 'max_enchantment_cmc' in commander_constraints:
                    max_cmc = commander_constraints['max_enchantment_cmc']
                    if cmc <= max_cmc:
                        tutor_note = f"{commander} can DIRECTLY TUTOR this (CMC {cmc} ≤ {max_cmc} limit). "
                    else:
                        can_tutor = False
                        tutor_note = f"Note: At CMC {cmc}, this is above {commander}'s tutor limit ({max_cmc}), but still strong enchantment synergy. "
                
                if 'draw' in oracle_lower and 'enchantment' in oracle_lower:
                    # Find the specific draw trigger
                    if 'whenever you cast' in oracle_lower or 'whenever an enchantment enters' in oracle_lower:
                        reasons.append(f"{tutor_note}This enchantment provides REPEATABLE card draw every time you cast an enchantment, which synergizes perfectly with {commander}'s enchantment-focused strategy. Creates a self-sustaining card advantage engine")
                    else:
                        reasons.append(f"{tutor_note}Enchantment-based card draw that triggers off your deck's primary theme. Ensures you never run out of gas in your enchantment strategy")
                elif 'search' in oracle_lower or 'tutor' in oracle_lower:
                    reasons.append(f"{tutor_note}Tutors enchantments from your library, creating redundancy for finding your key pieces like Necropotence, Rhystic Study, or combo enablers. Consistency is key in Commander")
                elif 'aura' in oracle_lower or 'attach' in oracle_lower:
                    reasons.append(f"{tutor_note}Aura that directly enhances {commander}, making them a more lethal threat. In a voltron-style build, this stacks with other auras to create an overwhelming board presence")
                else:
                    if can_tutor:
                        reasons.append(f"{tutor_note}Core enchantment that fits your strategy perfectly. Acts as both a threat and value engine in your enchantress theme")
                    else:
                        reasons.append(f"{tutor_note}Strong enchantment for your deck's theme, providing significant value even if it must be cast from hand")
            elif 'artifact' in commander_synergies:
                reasons.append(f"Artifact that synergizes with {commander}'s ability to manipulate or benefit from artifacts. Provides utility while feeding into your commander's core strategy, creating multiplicative value")
        
        # Ultra-detailed role analysis
        if role == 'draw':
            # Analyze the specific draw mechanism
            if 'skullclamp' in card_name.lower():
                reasons.append(f"{card_name} is excellent with expendable creatures and tokens: it turns small bodies into two fresh cards, which keeps a creature-heavy engine from running out of material.")
            elif 'phyrexian arena' in card_name.lower():
                reasons.append("A steady black draw engine that adds an extra card each turn with a manageable life cost. It is best when the deck wants reliable long-game fuel over explosive one-shot draw.")
            elif 'rhystic study' in card_name.lower():
                reasons.append("THE most powerful draw engine in Commander. Opponents either pay 1 mana for EVERY spell (slowing them down significantly) or you draw cards. In a 4-player game, this draws 5-10 cards per turn cycle")
            elif 'mystic remora' in card_name.lower():
                reasons.append("Extremely efficient early-game draw engine. For just 1 mana, this draws you 3-5 cards in the first few turns when opponents are ramping and playing rocks. Drop this turn 1-2 for maximum value")
            elif 'whenever' in oracle_lower and 'draw' in oracle_lower:
                if 'dies' in oracle_lower or 'is put into a graveyard' in oracle_lower:
                    reasons.append(f"{card_name} rewards creatures dying, which pairs well with token and aristocrat patterns while turning trades or sacrifice outlets into cards.")
                elif 'power 4 or greater' in oracle_lower:
                    reasons.append(f"{card_name} is a creature-based draw payoff for larger threats, and its extra combat text can help a board of counters close games once creatures grow.")
                elif 'creature' in oracle_lower:
                    reasons.append(f"{card_name} turns creature deployment into card flow, helping a creature-heavy deck keep pressure on the table without emptying its hand.")
                else:
                    reasons.append(f"{card_name} provides repeatable card draw tied to board development, which is stronger here than a one-shot draw spell.")
            elif 'at the beginning' in oracle_lower and 'upkeep' in oracle_lower:
                reasons.append(f"{card_name} is a passive draw engine that keeps cards coming without requiring more mana after it resolves.")
            else:
                reasons.append(f"{card_name} adds card advantage in a deck that is still short about {gaps.get('roles', {}).get('draw', 0)} draw sources.")
        
        elif role == 'ramp':
            if 'sol ring' in card_name.lower():
                reasons.append("THE most powerful mana rock in Commander. Turn 1 Sol Ring is basically an auto-win - you're 2 turns ahead of everyone else. This card is banned in Legacy for a reason. Always include it")
            elif 'arcane signet' in card_name.lower():
                reasons.append(f"Perfect 2-mana rock that produces ANY color in your commander's identity. No color restrictions, no ETB tapped drawback. This is as efficient as mana acceleration gets in Commander")
            elif 'treasure' in oracle_lower:
                reasons.append(f"Creates Treasure tokens for FLEXIBLE mana. Unlike rocks, treasures can be sacrificed when needed for a burst of mana, enabling huge turns. They also dodge artifact removal and work around Null Rod effects")
            elif 'search' in oracle_lower and 'land' in oracle_lower:
                if 'basic' in oracle_lower:
                    reasons.append(f"Land ramp that puts basics directly onto the battlefield, PERMANENTLY accelerating your mana. Unlike artifacts, lands don't die to Vandalblast or Austere Command. This also thins your deck, improving draw quality")
                else:
                    reasons.append(f"Fetches ANY land from your library - including utility lands like Reliquary Tower, Ancient Tomb, or dual lands. Provides both ramp AND color fixing in one package")
            elif 'mana' in oracle_lower and ('add' in oracle_lower or 'produce' in oracle_lower):
                reasons.append(f"Efficient mana rock at {cmc} CMC. Gets you ahead on mana to deploy threats faster. Your deck needs {gaps.get('roles', {}).get('ramp', 0)} more ramp sources to consistently cast your high-impact spells")
        
        elif role == 'removal':
            if 'swords to plowshares' in card_name.lower():
                reasons.append("THE most efficient removal spell in Magic. For just 1 white mana, permanently exile ANY creature at instant speed. The life gain is negligible in Commander. This answers everything from mana dorks to Blightsteel Colossus")
            elif 'path to exile' in card_name.lower():
                reasons.append("Instant-speed exile removal for 1 mana - incredibly efficient. Yes, they get a land, but in late game that's irrelevant. Answers indestructible threats, recursive creatures, and commanders permanently")
            elif 'beast within' in card_name.lower():
                reasons.append("Most FLEXIBLE removal in Commander. Destroys literally ANY permanent - creatures, enchantments, artifacts, even lands. The 3/3 beast token is a small price for answering any threat at instant speed")
            elif 'exile' in oracle_lower:
                reasons.append(f"EXILE-based removal that permanently deals with threats. This is crucial in Commander where graveyard recursion (Reanimate, Living Death, Muldrotha) is common. Destroy effects just delay problems; exile solves them")
            elif 'destroy' in oracle_lower and ('artifact' in oracle_lower or 'enchantment' in oracle_lower):
                reasons.append(f"Flexible removal hitting multiple permanent types. Can answer problem artifacts (Rhystic Study, Necropotence) AND enchantments (Smothering Tithe). Versatility is key in Commander's varied meta")
            else:
                reasons.append(f"Spot removal to answer problematic permanents. Your deck currently lacks sufficient removal ({gaps.get('roles', {}).get('removal', 0)} pieces short), leaving you vulnerable to opposing threats")

        elif role == 'sweeper':
            if '-x/-x' in oracle_lower or 'toxic deluge' in card_name.lower():
                reasons.append(f"{card_name} is a flexible board reset that can clear creature-heavy tables while letting you choose how much life to spend. It helps recover when the board grows faster than your counters or tokens can control.")
            elif 'destroy all' in oracle_lower or 'exile all' in oracle_lower:
                reasons.append(f"{card_name} gives the deck a reset button for boards that go wider or taller than your engine. A few sweepers keep you from relying only on spot removal.")
            else:
                reasons.append(f"{card_name} fills the sweeper slot, giving the deck a way to reset multiple threats at once when incremental interaction is not enough.")
        
        elif role == 'counter':
            if 'counterspell' in card_name.lower():
                reasons.append("The original and still one of the best. 2 mana to counter ANY spell - no restrictions, no conditions. Instant speed protection against game-ending threats. Stop combos, board wipes, or opposing win conditions")
            elif 'arcane denial' in card_name.lower():
                reasons.append("Ultra-efficient 2-mana counter that hits ANY spell. Yes they draw cards, but in a multiplayer game you're trading 1-for-1 while the other 2 players get nothing. The political implications are valuable")
            elif 'swan song' in card_name.lower():
                reasons.append("1-mana counterspell for noncreature spells. Counters most game-winning plays (combos, board wipes, big enchantments) for minimal investment. The 2/2 bird is irrelevant compared to stopping a Cyclonic Rift")
            elif 'negate' in card_name.lower():
                reasons.append("2-mana counter for noncreature spells. In Commander, the scariest threats are often instants/sorceries/enchantments (board wipes, combos, Rhystic Study). This stops all of them efficiently")
            else:
                reasons.append(f"Stack interaction to protect your board state and disrupt opposing strategies. Commander games are often won by the player who can STOP the winning play, not just make their own")
        
        elif role == 'protection':
            if 'lightning greaves' in card_name.lower():
                reasons.append(f"THE best protection equipment. Gives {commander} haste AND hexproof for 0 equip cost. Drop this, immediately equip, and your commander is untouchable. Free to re-equip each turn to protect any creature")
            elif 'swiftfoot boots' in card_name.lower():
                reasons.append(f"Protection equipment giving {commander} hexproof and haste. Unlike Lightning Greaves, this costs 1 to equip but doesn't cause targeting issues with your own auras/equipment. More reliable for voltron strategies")
            elif 'heroic intervention' in card_name.lower():
                reasons.append("Instant-speed protection for your ENTIRE board. For 2 mana, make everything hexproof and indestructible. Blank board wipes, protect against targeted removal, save combo pieces. One of green's best cards")
            elif 'teferi\'s protection' in card_name.lower():
                reasons.append("The ULTIMATE protection spell. Phase out your entire board, make yourself immune to damage/loss effects. Completely blank board wipes, combo kills, or anything targeting you. Arguably white's best instant")
            elif 'hexproof' in oracle_lower or 'shroud' in oracle_lower:
                reasons.append(f"Grants hexproof/shroud to {commander}, making them untargetable by opponents' removal. In a format where commanders get removed 3-4 times per game, this protection is invaluable for maintaining board presence")
            elif 'indestructible' in oracle_lower:
                reasons.append(f"Makes permanents indestructible, surviving board wipes like Wrath of God, Blasphemous Act, and Vandalblast. This ensures your key pieces survive mass removal, maintaining your advantage")
        
        elif role == 'recursion':
            if 'reanimate' in card_name.lower():
                reasons.append("THE most efficient reanimation spell. For just 1 black mana, return ANY creature from ANY graveyard. This can steal opponents' threats OR recur your own. Turn 2 Reanimate on a discarded Eldrazi is game-winning")
            elif 'living death' in card_name.lower():
                reasons.append("Board wipe + mass reanimation in one spell. Wipes opponents' boards while bringing back ALL your creatures. In graveyard-focused decks, this is an instant win - they get nothing, you get everything")
            elif 'return' in oracle_lower and 'hand' in oracle_lower:
                reasons.append(f"Returns cards from graveyard to hand, enabling reuse of key pieces. Unlike reanimation, this lets you re-cast cards (triggering ETB effects again). Provides card advantage and recovery from removal")
            else:
                reasons.append(f"Graveyard recursion to recover threats and value pieces. In Commander where everyone has removal, the ability to bring back your best cards is crucial for grinding out victories")
        
        elif role == 'tutor':
            if 'demonic tutor' in card_name.lower():
                reasons.append("THE gold standard for tutors. 2 mana to search for literally ANY card and put it in hand. Want your combo piece? Your answer? Your win condition? This finds it. Banned in Legacy for good reason")
            elif 'vampiric tutor' in card_name.lower():
                reasons.append("1-mana instant-speed tutor to topdeck. Cast this end-of-turn before your draw step to effectively draw ANY card. The life loss is negligible. This consistency is why it's a $100+ card")
            elif 'enlightened tutor' in card_name.lower():
                reasons.append("Efficiently finds ANY enchantment or artifact for just 1 white mana. In enchantment-heavy strategies, this finds your win conditions, answers, or value engines. Instant speed lets you respond to threats")
            elif 'search' in oracle_lower and 'hand' in oracle_lower:
                reasons.append(f"Searches your library for specific cards, dramatically increasing consistency. Commander is about assembling your strategy reliably - tutors ensure you find your key pieces when needed")
        
        # CMC efficiency note
        if cmc <= 2:
            reasons.append(f"At {cmc} mana, it is easy to deploy while still developing the rest of your turn.")
        elif cmc >= 6:
            reasons.append(f"At {cmc} mana, it needs to be a deliberate top-end inclusion rather than a card you expect to cast early.")
        
        # Combine all detailed reasons
        if reasons:
            return ' '.join(reasons)
        else:
            return f"{card_name} provides {role} support for your strategy. Consider it for filling gaps in your deck's game plan."

    def _has_lifegain_reward_text(self, oracle_text: str) -> bool:
        """Detect commanders/cards that actively reward gaining life."""
        return bool(
            re.search(r'whenever (?:you|one or more players) gain life', oracle_text) or
            re.search(r'whenever .* gains life', oracle_text) or
            re.search(r'(?:if|when|whenever) you gained life', oracle_text) or
            'each time you gain life' in oracle_text or
            'you gain that much life' in oracle_text or
            'life you gained' in oracle_text or
            'life total' in oracle_text
        )

    def _has_card_draw_text(self, oracle_text: str) -> bool:
        """Detect actual card draw without matching phrases like draw step."""
        return bool(
            re.search(r'\bdraw (?:a card|two cards|three cards|four cards|x cards|that many cards|cards equal|cards?)\b', oracle_text) or
            re.search(r'\bdraws? (?:a card|two cards|three cards|cards?)\b', oracle_text) or
            'investigate' in oracle_text
        )

    def _has_artifact_token_text(self, oracle_text: str) -> bool:
        """Detect noncreature token economies such as Treasure, Clue, Food, and Blood."""
        return any(phrase in oracle_text for phrase in [
            'treasure token',
            'clue token',
            'food token',
            'blood token',
            'artifact token',
        ])

    def _is_creature_token_support(self, oracle_text: str, type_line: str) -> bool:
        """Identify cards that support creature-token plans instead of incidental Treasure ramp."""
        if any(phrase in oracle_text for phrase in [
            'creature token',
            'creature tokens',
            'populate',
            'token creatures',
            'tokens you control get',
            'tokens you control have',
            'creatures you control get',
            'creatures you control have',
            'double the number of each kind of token',
            'twice that many of those tokens',
            'one or more tokens under your control',
        ]):
            return True
        if 'enchantment' in type_line and any(phrase in oracle_text for phrase in [
            'one or more tokens',
            'twice that many tokens',
        ]):
            return True
        return False

    def _is_artifact_token_support(self, oracle_text: str) -> bool:
        """Identify cards that make or spend artifact tokens as an engine."""
        return self._has_artifact_token_text(oracle_text) or any(phrase in oracle_text for phrase in [
            'sacrifice an artifact',
            'whenever you sacrifice',
            'artifacts you control',
            'for each artifact you control',
        ])

    def _is_graveyard_hate(self, oracle_text: str) -> bool:
        """Filter out graveyard hate from graveyard-value recommendations."""
        hate_patterns = [
            'exile all cards from',
            "exile target player's graveyard",
            "exile target opponent's graveyard",
            'exile all graveyards',
            'from all graveyards',
            "each opponent's graveyard",
            "target player's graveyard",
            "target opponent's graveyard",
            'cards in graveyards lose',
            "graveyards can't",
            'graveyards cannot',
        ]
        return any(pattern in oracle_text for pattern in hate_patterns)

    def _is_graveyard_value_card(self, oracle_text: str, type_line: str) -> bool:
        """Confirm graveyard cards advance recursion, death, self-mill, or reusable resources."""
        if self._is_graveyard_hate(oracle_text):
            return False
        value_patterns = [
            'from your graveyard',
            'from a graveyard',
            'return target',
            'return up to',
            'return a card',
            'return that card',
            'cast target',
            'cast cards',
            'cast spells from your graveyard',
            'play lands from your graveyard',
            'you may play lands',
            'put into your graveyard',
            'put into a graveyard',
            'mill',
            'dies',
            'whenever another creature dies',
            'whenever a creature dies',
            'when this creature dies',
            'sacrifice',
            'reanimate',
            'escape',
            'flashback',
            'unearth',
            'delirium',
            'descend',
        ]
        if any(pattern in oracle_text for pattern in value_patterns):
            return True
        return 'land' in type_line and 'graveyard' in oracle_text

    def _is_exile_value_card(self, oracle_text: str) -> bool:
        """Confirm exile cards support impulse draw/casting from exile rather than hate/removal."""
        if self._is_graveyard_hate(oracle_text):
            return False
        value_patterns = [
            'exile the top',
            'play that card',
            'play those cards',
            'cast that card',
            'cast those cards',
            'from exile',
            'until end of your next turn',
            'until the end of your next turn',
            'you may play it this turn',
            'you may cast it this turn',
        ]
        return any(pattern in oracle_text for pattern in value_patterns)

    def _is_blink_support(self, oracle_text: str, type_line: str) -> bool:
        """Confirm blink candidates either reuse your permanents or are worth reusing."""
        blink_text = (
            'exile another' in oracle_text or
            'exile target' in oracle_text and 'return' in oracle_text or
            'exile any number' in oracle_text and 'return' in oracle_text or
            'exile it, then return' in oracle_text or
            'return it to the battlefield' in oracle_text
        )
        if blink_text:
            return True

        if 'enters the battlefield' not in oracle_text and 'enters under your control' not in oracle_text:
            return False

        if 'instant' in type_line or 'sorcery' in type_line:
            return False

        value_etb_terms = [
            'draw',
            'search your library',
            'return target',
            'exile target',
            'destroy target',
            'create',
            'gain control',
            'look at',
            'put a land',
            'add ',
        ]
        return any(term in oracle_text for term in value_etb_terms)

    def _is_land_fetch_sacrifice(self, oracle_text: str, type_line: str) -> bool:
        """Filter land-fetch sacrifices out of creature/death sacrifice recommendations."""
        if 'land' not in type_line:
            return False
        return (
            'sacrifice' in oracle_text and
            'search your library' in oracle_text and
            'basic land' in oracle_text and
            not any(term in oracle_text for term in ['creature', 'dies', 'blood', 'treasure', 'clue', 'food'])
        )

    def _is_voltron_support(self, oracle_text: str, type_line: str) -> bool:
        """Confirm Voltron cards improve the commander in combat instead of being generic Auras."""
        if 'curse' in type_line or 'enchant player' in oracle_text or 'enchant opponent' in oracle_text:
            return False

        if 'equipment' in type_line or 'equip' in oracle_text or 'attach' in oracle_text:
            return True

        if 'aura' not in type_line and 'enchant creature' not in oracle_text and 'enchanted creature' not in oracle_text:
            return False

        voltron_terms = [
            'gets +',
            '+1/+1',
            '+2/+',
            'double strike',
            'first strike',
            'trample',
            'flying',
            'vigilance',
            'lifelink',
            'haste',
            'hexproof',
            'shroud',
            'ward',
            "can't be blocked",
            'unblockable',
            'draw a card',
        ]
        return any(term in oracle_text for term in voltron_terms)

    def _is_board_conversion_commander(self, oracle_text: str) -> bool:
        """Detect commanders that turn many small bodies into a combat engine."""
        board_text = any(phrase in oracle_text for phrase in [
            'creatures you control have base power and toughness',
            'other creatures you control have base power and toughness',
            'base power and toughness',
            'creatures you control are',
            'in addition to their other creature types',
        ])
        combat_pressure = any(phrase in oracle_text for phrase in [
            'attack each combat if able',
            "can't be blocked",
            'must attack',
            'attack if able',
        ])
        return board_text and ('creatures you control' in oracle_text or 'other creatures you control' in oracle_text or combat_pressure)

    def _is_board_conversion_support(self, oracle_text: str, type_line: str, cmc: float = 0) -> bool:
        """Identify cards that add bodies or make a wide converted board attack better."""
        if 'land' in type_line:
            return False

        creature_token_body = self._is_creature_token_support(oracle_text, type_line) or any(phrase in oracle_text for phrase in [
            'create a 1/1',
            'create two',
            'create three',
            'create x',
            'create that many',
            'thopter artifact creature token',
            'servo artifact creature token',
            'myr artifact creature token',
            'construct artifact creature token',
            'eldrazi scion',
            'eldrazi spawn',
        ])
        cheap_body = 'creature' in type_line and cmc <= 3
        multi_body = any(phrase in oracle_text for phrase in [
            'for each creature',
            'for each artifact',
            'whenever a nontoken creature enters',
            'whenever another nontoken creature enters',
            'at the beginning of combat',
        ])
        attack_support = any(phrase in oracle_text for phrase in [
            'creatures you control gain',
            'creatures you control have',
            'attacking creatures',
            "can't be blocked",
            'menace',
            'trample',
            'haste',
            'indestructible',
        ])

        return creature_token_body or cheap_body or multi_body or attack_support

    def _is_land_card(self, card_data: Dict) -> bool:
        """Keep lands out of commander mechanic recommendations."""
        return re.search(r'\bland\b', card_data.get('type_line', '').lower()) is not None

    def _is_generic_mana_card(self, card_data: Dict) -> bool:
        """Identify mana-only staples that should not dominate commander theme recommendations."""
        name = card_data.get('name', '').lower()
        type_line = card_data.get('type_line', '').lower()
        oracle_text = card_data.get('oracle_text', '').lower()

        known_mana_staples = {
            'arcane signet',
            'chromatic lantern',
            'command sphere',
            'everflowing chalice',
            'fellwar stone',
            'gilded lotus',
            'mind stone',
            'mana crypt',
            'mana vault',
            'sol ring',
            'thran dynamo',
            'thought vessel',
        }
        if name in known_mana_staples:
            return True

        if 'artifact' not in type_line:
            return False

        mana_text = 'add' in oracle_text and ('mana' in oracle_text or '{' in oracle_text)
        if mana_text and any(term in name for term in ['signet', 'talisman', 'locket', 'cluestone', 'keyrune']):
            return True
        if mana_text and re.search(r'\{t\}:\s*add|add \{[wubrgc]', oracle_text):
            return True

        has_theme_text = any(phrase in oracle_text for phrase in [
            'draw',
            'create',
            'sacrifice',
            'graveyard',
            'dies',
            'token',
            '+1/+1 counter',
            'proliferate',
            'copy',
            'whenever',
            'cast',
            'return',
            'equipment',
            'equipped',
            'attach',
        ])
        return mana_text and not has_theme_text

    def _card_matches_synergy(self, card_data: Dict, synergy: str) -> bool:
        """Confirm a candidate card genuinely supports the requested synergy."""
        oracle_text = card_data.get('oracle_text', '').lower()
        type_line = card_data.get('type_line', '').lower()
        detected = set(self._detect_card_synergies(oracle_text, type_line))

        if synergy == 'graveyard':
            return self._is_graveyard_value_card(oracle_text, type_line)
        if synergy == 'tokens':
            return self._is_creature_token_support(oracle_text, type_line)
        if synergy == 'artifact_tokens':
            return self._is_artifact_token_support(oracle_text)
        if synergy == 'exile':
            return self._is_exile_value_card(oracle_text)
        if synergy == 'blink':
            return self._is_blink_support(oracle_text, type_line)
        if synergy == 'lifegain':
            return self._has_lifegain_reward_text(oracle_text) or re.search(r'\bgain(?:s|ed)? life\b', oracle_text) is not None
        if synergy == 'artifact':
            artifact_support = [
                'artifact card',
                'artifact spell',
                'artifacts you control',
                'whenever an artifact',
                'sacrifice an artifact',
                'artifact token',
                'equipment',
                'equip',
                'equipped',
            ]
            return any(phrase in oracle_text for phrase in artifact_support) or 'equipment' in type_line
        if synergy == 'enchantment':
            enchantment_support = [
                'enchantment card',
                'enchantment spell',
                'enchantments you control',
                'whenever an enchantment',
                'aura',
                'enchant ',
                'enchanted',
            ]
            return any(phrase in oracle_text for phrase in enchantment_support) or 'aura' in type_line
        if synergy == 'creature':
            creature_support = [
                'creatures you control',
                'whenever another creature',
                'whenever a creature',
                'creature enters',
                'enters the battlefield',
                'nontoken creature',
                'creature token',
            ]
            return (
                any(phrase in oracle_text for phrase in creature_support) or
                self._has_creature_spell_text(oracle_text) or
                self._has_creature_card_text(oracle_text)
            )
        if synergy == 'voltron':
            return self._is_voltron_support(oracle_text, type_line)
        if synergy == 'board_conversion':
            return self._is_board_conversion_support(oracle_text, type_line, card_data.get('cmc', 0))
        if synergy in detected:
            return True
        if synergy == 'landfall' and (
            'landfall' in oracle_text or
            'additional land' in oracle_text or
            'land you control enters' in oracle_text
        ):
            return True

        return False

    def _card_matches_commander_context(self, card_data: Dict, synergy: str, commander_card: Dict) -> bool:
        """Confirm the candidate matches the commander's specific version of a broad theme."""
        commander_text = self._combined_oracle_text(commander_card)
        oracle_text = card_data.get('oracle_text', '').lower()
        type_line = card_data.get('type_line', '').lower()

        if synergy == 'graveyard':
            if self._is_graveyard_hate(oracle_text) or not self._is_graveyard_value_card(oracle_text, type_line):
                return False
            if 'artifact card in your graveyard' in commander_text:
                return 'artifact' in type_line
            if self._has_creature_card_text(commander_text) and 'graveyard' in commander_text:
                return 'creature' in type_line or 'creature card' in oracle_text
            if 'enchantment card' in commander_text and 'graveyard' in commander_text:
                return 'enchantment' in type_line or 'enchantment card' in oracle_text

        if synergy == 'artifact':
            if not any(term in commander_text for term in ['artifact', 'equipment', 'equip', 'treasure', 'clue', 'food', 'blood']):
                return False
            if 'artifact card in your graveyard' in commander_text:
                return 'artifact' in type_line
            if 'equipment' in commander_text or 'equipped' in commander_text or 'equip' in commander_text:
                return 'equipment' in type_line or any(term in oracle_text for term in ['equipment', 'equip', 'equipped', 'attach'])

        if synergy == 'enchantment':
            if not any(term in commander_text for term in ['enchantment', 'aura', 'enchant', 'enchanted']):
                return False
            if 'aura' in commander_text or 'enchanted' in commander_text:
                return 'aura' in type_line or any(term in oracle_text for term in ['aura', 'enchant ', 'enchanted'])

        if synergy == 'creature':
            if self._has_creature_spell_text(commander_text):
                return 'creature' in type_line or self._has_creature_spell_text(oracle_text)
            if any(term in commander_text for term in ['enters the battlefield', 'creature enters']):
                return any(term in oracle_text for term in [
                    'enters the battlefield',
                    'creature token',
                    'return it to the battlefield',
                    'exile another',
                    'whenever another creature',
                    'whenever a creature',
                ])
            if any(term in commander_text for term in ['creatures you control', 'each creature you control', 'creatures get', 'creatures have']):
                return any(term in oracle_text for term in [
                    'creatures you control',
                    'each creature you control',
                    'creature token',
                    'whenever a creature',
                    'whenever another creature',
                    '+1/+1 counter',
                    'draw a card',
                ])

        if synergy == 'tokens':
            if any(phrase in oracle_text for phrase in ['its controller creates', 'that player creates', 'target opponent creates']):
                return False
            if 'creature token' in commander_text or 'populate' in commander_text:
                return self._is_creature_token_support(oracle_text, type_line)
            if self._has_artifact_token_text(oracle_text) and not self._is_creature_token_support(oracle_text, type_line):
                return False

        if synergy == 'artifact_tokens':
            if any(phrase in oracle_text for phrase in ['its controller creates', 'that player creates', 'target opponent creates']):
                return False
            return self._is_artifact_token_support(oracle_text)

        if synergy == 'exile':
            if 'from exile' in commander_text or 'play a card from exile' in commander_text:
                return self._is_exile_value_card(oracle_text)
            if self._is_graveyard_hate(oracle_text):
                return False

        if synergy == 'blink':
            if self._is_exile_value_card(oracle_text) and not self._is_blink_support(oracle_text, type_line):
                return False
            return self._is_blink_support(oracle_text, type_line)

        if synergy == 'landfall':
            if 'landfall' in commander_text or 'land you control enters' in commander_text:
                return (
                    'landfall' in oracle_text or
                    'additional land' in oracle_text or
                    'land you control enters' in oracle_text or
                    'you may play lands' in oracle_text
                )

        if synergy == 'counters':
            counter_plan = self._counter_plan_for_text(commander_text)
            if not counter_plan:
                return False
            if 'proliferate' in oracle_text and counter_plan not in ['proliferate', 'named_counters']:
                return False
            if counter_plan == 'proliferate':
                return (
                    'proliferate' in oracle_text or
                    self._is_counter_multiplier(oracle_text) or
                    self._is_counter_payoff(oracle_text) or
                    '+1/+1 counter' in oracle_text or
                    '-1/-1 counter' in oracle_text
                )
            if counter_plan == 'named_counters':
                named_terms = self._named_counter_terms(commander_text)
                return (
                    'proliferate' in oracle_text or
                    any(f'{term} counter' in oracle_text for term in named_terms)
                )
            if counter_plan == 'self_counters':
                external_counter_payoff = (
                    self._is_counter_payoff(oracle_text) and
                    'remove a +1/+1 counter' not in oracle_text and
                    'enters the battlefield with' not in oracle_text
                )
                return (
                    self._is_counter_multiplier(oracle_text) or
                    external_counter_payoff or
                    ('commander' in oracle_text and '+1/+1 counter' in oracle_text) or
                    'move counters' in oracle_text or
                    'move all counters' in oracle_text
                )
            if counter_plan == 'board_counters':
                return (
                    self._is_counter_multiplier(oracle_text) or
                    self._is_counter_payoff(oracle_text) or
                    'creatures you control' in oracle_text and '+1/+1 counter' in oracle_text or
                    'each creature you control' in oracle_text and '+1/+1 counter' in oracle_text
                )
            if counter_plan == 'negative_counters':
                return '-1/-1 counter' in oracle_text or self._is_counter_payoff(oracle_text)
            return (
                self._is_counter_multiplier(oracle_text) or
                self._is_counter_payoff(oracle_text) or
                '+1/+1 counter on target creature' in oracle_text or
                '+1/+1 counter on a creature' in oracle_text
            )

        if synergy == 'sacrifice':
            if self._is_land_fetch_sacrifice(oracle_text, type_line):
                return False
            return any(term in oracle_text for term in [
                'sacrifice a creature',
                'sacrifice another creature',
                'sacrifice another permanent',
                'whenever you sacrifice',
                'whenever a creature dies',
                'whenever another creature dies',
                'creature dies',
                'dies',
                'death trigger',
                'create a creature token',
                'creature token',
            ])

        if synergy == 'voltron':
            return self._is_voltron_support(oracle_text, type_line)

        if synergy == 'board_conversion':
            if self._is_board_conversion_support(oracle_text, type_line, card_data.get('cmc', 0)):
                if 'enters the battlefield' in oracle_text and not any(term in oracle_text for term in [
                    'create',
                    'creatures you control',
                    'tokens you control',
                    'attacking creatures',
                    'haste',
                    'trample',
                    "can't be blocked",
                ]):
                    return False
                return True
            return False

        return True

    def _generate_commander_recommendation_reason(
        self,
        card_data: Dict,
        commander_name: str,
        synergy: str,
        commander_card: Dict
    ) -> str:
        """Generate concise, commander-specific recommendation copy."""
        card_name = card_data.get('name', 'This card')
        oracle_text = card_data.get('oracle_text', '')
        oracle_lower = oracle_text.lower()
        type_line = card_data.get('type_line', '').lower()
        commander_text = commander_card.get('oracle_text', '').lower()
        commander_constraints = self._get_commander_constraints(commander_card)
        cmc = card_data.get('cmc', 0)

        reasons = []

        if synergy == 'artifact':
            if 'equipment' in type_line and any(word in oracle_lower for word in ['haste', 'hexproof', 'shroud', 'ward']):
                reasons.append(f"{card_name} protects {commander_name} and can help the commander start generating value sooner. Because it is also an artifact, it still contributes to the deck's artifact density rather than being a disconnected protection piece.")
            elif 'artifact card' in oracle_lower and 'graveyard' in oracle_lower:
                reasons.append(f"{card_name} directly extends {commander_name}'s artifact-recursion plan by getting important artifacts back after they are milled, sacrificed, or removed.")
            elif 'when' in oracle_lower and ('dies' in oracle_lower or 'put into a graveyard' in oracle_lower):
                reasons.append(f"{card_name} is useful because it is an artifact you do not mind losing. It creates value when it dies, which pairs well with {commander_name}'s ability to reuse artifacts.")
            elif 'draw' in oracle_lower and 'artifact' in type_line:
                reasons.append(f"{card_name} gives the artifact package card flow instead of only board presence, helping {commander_name} keep finding artifacts worth casting or recurring.")
            elif 'sacrifice' in oracle_lower and 'artifact' in type_line:
                reasons.append(f"{card_name} gives you an artifact-based sacrifice outlet or payoff, which turns expendable artifacts into decisions rather than dead permanents.")
            elif 'graveyard' in commander_text and ('artifact' in type_line or 'artifact' in oracle_lower):
                reasons.append(f"{card_name} raises your artifact count while giving {commander_name} more material to reuse or care about from the graveyard.")
            elif 'sacrifice' in commander_text and 'artifact' in type_line:
                reasons.append(f"{card_name} is an artifact that can feed {commander_name}'s sacrifice or artifact-counting plan instead of sitting outside the engine.")
            else:
                reasons.append(f"{card_name} supports {commander_name}'s artifact theme as a real engine piece, not just generic acceleration.")
        elif synergy == 'graveyard':
            if 'artifact card' in oracle_lower and 'graveyard' in oracle_lower and 'artifact' in commander_text:
                reasons.append(f"{card_name} is a strong fit because it recovers artifacts that {commander_name} mills, sacrifices, or trades off, giving the deck more staying power.")
            elif 'return' in oracle_lower and 'graveyard' in oracle_lower:
                reasons.append(f"{card_name} gives {commander_name} another way to reclaim important cards from the graveyard, which makes self-mill and normal removal less costly.")
            elif 'play' in oracle_lower and 'land' in oracle_lower and 'graveyard' in oracle_lower:
                reasons.append(f"{card_name} turns self-mill into mana consistency by letting you reuse lands that end up in the graveyard while setting up {commander_name}.")
            elif 'when' in oracle_lower and ('dies' in oracle_lower or 'put into a graveyard' in oracle_lower):
                death_subject = 'creatures' if 'creature' in type_line or 'creature' in oracle_lower else 'permanents'
                reasons.append(f"{card_name} rewards the deck when {death_subject} die, which makes sacrifice lines, board wipes, and combat trades feed {commander_name}'s long game instead of only costing resources.")
            elif 'draw' in oracle_lower:
                reasons.append(f"{card_name} keeps cards moving while interacting with the graveyard, which is exactly what a recursive {commander_name} deck wants.")
            else:
                reasons.append(f"{card_name} gives {commander_name} a useful graveyard-facing role, helping the deck turn milled, sacrificed, or removed cards into future advantage.")
        elif synergy == 'tokens':
            if 'populate' in oracle_lower:
                reasons.append(f"{card_name} is strong with {commander_name} because populate copies an existing creature token, turning the commander's token output into repeatable board growth.")
            elif 'creature token' in oracle_lower or 'creature tokens' in oracle_lower:
                reasons.append(f"{card_name} adds real bodies to {commander_name}'s creature-token plan, giving the deck more material to copy, pump, sacrifice, or turn sideways.")
            elif 'tokens you control' in oracle_lower:
                reasons.append(f"{card_name} rewards the tokens {commander_name} is already making, so the deck gets paid for going wide instead of only adding more small bodies.")
            elif 'one or more tokens' in oracle_lower or 'twice that many' in oracle_lower:
                reasons.append(f"{card_name} multiplies {commander_name}'s token output, making each activation scale into a much wider board than the commander could produce alone.")
            else:
                reasons.append(f"{card_name} strengthens {commander_name}'s token plan by making repeated token creation more valuable.")
        elif synergy == 'artifact_tokens':
            if 'treasure token' in oracle_lower:
                reasons.append(f"{card_name} supports {commander_name}'s artifact-token economy by making Treasures that can become mana, sacrifice fodder, or artifact-count payoffs.")
            elif self._has_artifact_token_text(oracle_lower):
                reasons.append(f"{card_name} gives {commander_name} more artifact tokens to convert into cards, mana, or sacrifice value instead of just adding generic board presence.")
            else:
                reasons.append(f"{card_name} rewards the artifact tokens {commander_name} creates, turning temporary resources into a more durable engine.")
        elif synergy == 'counters':
            counter_plan = self._counter_plan_for_text(commander_text)
            if 'proliferate' in oracle_lower:
                if 'proliferate' in commander_text:
                    reasons.append(f"{card_name} gives {commander_name} another proliferate effect, making every counter already on the table scale harder.")
                elif counter_plan == 'named_counters':
                    named_terms = self._named_counter_terms(commander_text)
                    counter_label = f"{named_terms[0]} counters" if named_terms else "the commander's named counters"
                    reasons.append(f"{card_name} can add more {counter_label} after {commander_name} marks a permanent, supporting that specific counter plan without mixing in unrelated +1/+1 counter cards.")
                else:
                    reasons.append(f"{card_name} can multiply counters after {commander_name} starts placing them, but it belongs here only as a counter-scaling support piece, not because the commander is a proliferate deck.")
            elif self._is_counter_multiplier(oracle_lower):
                if counter_plan == 'self_counters':
                    reasons.append(f"{card_name} increases the +1/+1 counters {commander_name} puts on itself, making each commander trigger scale into a faster clock.")
                elif counter_plan == 'board_counters':
                    reasons.append(f"{card_name} increases the counters your board receives, so {commander_name}'s counter plan turns small creatures into real pressure faster.")
                else:
                    reasons.append(f"{card_name} improves the counter plan by increasing the number of counters your engine creates instead of adding an unrelated counter subtheme.")
            elif 'commander' in oracle_lower and '+1/+1 counter' in oracle_lower:
                reasons.append(f"{card_name} puts counters directly on {commander_name}, which supports the commander's own scaling plan without asking the deck to pivot into a generic counter shell.")
            elif self._is_counter_payoff(oracle_lower):
                reasons.append(f"{card_name} pays you for already having counters, giving {commander_name}'s scaling plan a concrete reward beyond simply making creatures larger.")
            elif '-1/-1 counter' in oracle_lower:
                reasons.append(f"{card_name} adds -1/-1 counter pressure, giving {commander_name} a way to shrink or pick off creatures while staying inside a counter-focused plan.")
            elif '+1/+1 counter' in oracle_lower:
                reasons.append(f"{card_name} adds +1/+1 counter scaling, which pairs with {commander_name}'s counter plan without depending on a separate combat-only payoff.")
            else:
                reasons.append(f"{card_name} supports the counter plan by adding either more counter placement or a payoff for creatures that already have counters.")
        elif synergy == 'creature':
            if self._has_creature_spell_text(commander_text) and 'creature' in type_line:
                if 'enters the battlefield' in oracle_lower:
                    reasons.append(f"{card_name} is a creature spell for {commander_name}'s cast trigger and it still creates value when it enters, so it advances the engine from both sides.")
                elif self._has_card_draw_text(oracle_lower):
                    reasons.append(f"{card_name} keeps the creature count high while adding card flow, making {commander_name}'s creature-cast turns less likely to run out of gas.")
                elif 'search your library' in oracle_lower or 'add ' in oracle_lower:
                    reasons.append(f"{card_name} gives {commander_name} a creature-based ramp or fixing piece, which is stronger here than a noncreature support card because it also triggers the commander.")
                else:
                    reasons.append(f"{card_name} keeps {commander_name}'s creature-spell density high while giving the deck another body that can carry the main game plan.")
            elif 'enters the battlefield' in commander_text and 'enters the battlefield' in oracle_lower:
                reasons.append(f"{card_name} gives {commander_name} another ETB target worth reusing, turning blink, bounce, or creature-entry loops into concrete cards, mana, or interaction.")
            elif 'creature token' in oracle_lower:
                reasons.append(f"{card_name} supplies bodies for {commander_name}'s creature plan, giving the deck material for attacks, sacrifice lines, or board-scaling payoffs.")
            else:
                reasons.append(f"{card_name} supports {commander_name}'s creature plan with a job tied to the commander's trigger pattern rather than only filling the curve.")
        elif synergy == 'board_conversion':
            if self._is_creature_token_support(oracle_lower, type_line):
                reasons.append(f"{card_name} gives {commander_name} creature material to convert into real combat damage, which is stronger here than relying only on oversized standalone threats.")
            elif 'creature' in type_line and cmc <= 3:
                reasons.append(f"{card_name} is a cheap body that can come down before {commander_name} and later become part of the converted attack force.")
            elif any(term in oracle_lower for term in ['creatures you control gain', 'creatures you control have', 'attacking creatures', "can't be blocked"]):
                reasons.append(f"{card_name} helps the wide board actually connect in combat after {commander_name} turns small creatures into meaningful attackers.")
            else:
                reasons.append(f"{card_name} supports {commander_name}'s board-conversion plan by adding material or combat texture for the commander to amplify.")
        elif synergy == 'blink':
            if 'enters the battlefield' in oracle_lower and not ('exile' in oracle_lower and 'return' in oracle_lower):
                reasons.append(f"{card_name} is a high-quality blink target for {commander_name}; reusing its ETB text turns each blink trigger into cards, mana, removal, or board presence.")
            elif 'exile' in oracle_lower and 'return' in oracle_lower:
                reasons.append(f"{card_name} gives {commander_name} another way to reuse or protect your own permanents, keeping the blink plan active even when the commander is removed.")
            else:
                reasons.append(f"{card_name} belongs in {commander_name}'s blink package because it creates repeatable value when permanents leave and return.")
        elif synergy == 'sacrifice':
            if 'sacrifice a creature' in oracle_lower or 'sacrifice another creature' in oracle_lower:
                reasons.append(f"{card_name} is an actual sacrifice outlet for {commander_name}, letting the deck control when death triggers and resource-conversion lines happen.")
            elif 'whenever you sacrifice' in oracle_lower or 'whenever a creature dies' in oracle_lower or 'whenever another creature dies' in oracle_lower:
                reasons.append(f"{card_name} is a sacrifice payoff for {commander_name}, turning creature deaths into cards, damage, mana, or board growth instead of simple attrition.")
            elif 'creature token' in oracle_lower:
                reasons.append(f"{card_name} supplies fodder for {commander_name}'s sacrifice plan, giving the deck expendable material that can be cashed in for stronger effects.")
            else:
                reasons.append(f"{card_name} gives the deck more sacrifice texture, so {commander_name}'s death and resource-conversion lines happen more reliably.")
        elif synergy == 'enchantment':
            tutor_note = ""
            if commander_constraints.get('max_enchantment_cmc') and 'enchantment' in type_line:
                max_cmc = commander_constraints['max_enchantment_cmc']
                if cmc <= max_cmc:
                    tutor_note = f"{commander_name} can find it directly because its mana value is {cmc}, inside the {max_cmc}-mana tutor limit. "
                else:
                    tutor_note = f"It sits above {commander_name}'s tutor limit, so it is more of a hand-cast payoff than a direct attack trigger target. "

            if 'draw' in oracle_lower:
                if 'opponent' in oracle_lower or 'unless' in oracle_lower or 'pay' in oracle_lower:
                    reasons.append(f"{tutor_note}{card_name} pressures opponents while feeding you cards, which is ideal for {commander_name}: you advance the enchantment count and keep the hand stocked for follow-up protection or interaction.")
                else:
                    reasons.append(f"{tutor_note}{card_name} turns the enchantment package into card flow, helping {commander_name} keep chaining value pieces instead of relying on one attack trigger.")
            elif any(phrase in oracle_lower for phrase in ["can't attack", 'cannot attack', 'prevent all combat damage', 'attacks you', 'attacks a planeswalker you control']):
                reasons.append(f"{tutor_note}{card_name} protects your life total and makes combat awkward for opponents, buying {commander_name} more turns to attack and tutor.")
            elif 'aura' in type_line or 'enchanted creature' in oracle_lower or 'enchant creature' in oracle_lower:
                if any(phrase in oracle_lower for phrase in ['unblockable', "can't be blocked", 'lifelink', 'hexproof', 'shroud']):
                    reasons.append(f"{tutor_note}{card_name} is an Aura that helps {commander_name} survive or connect in combat, which matters because the commander has to attack to generate value.")
                else:
                    reasons.append(f"{tutor_note}{card_name} gives the deck a tutorable Aura role player that can turn a creature into a better threat or utility piece.")
            elif 'search your library' in oracle_lower or 'tutor' in oracle_lower:
                reasons.append(f"{tutor_note}{card_name} adds redundancy to the enchantment toolbox, making it easier for {commander_name} to assemble the right protection, value, or lock piece.")
            elif 'opponent' in oracle_lower and any(phrase in oracle_lower for phrase in ['pay', 'tax', "can't", 'cannot']):
                reasons.append(f"{tutor_note}{card_name} taxes opposing plays while staying inside the enchantment theme, slowing the table enough for {commander_name} to keep attacking safely.")
            else:
                reasons.append(f"{tutor_note}{card_name} gives {commander_name} another enchantment-based tool, raising the density of permanents the deck can tutor, protect, and build around.")
        elif synergy == 'instant_sorcery':
            reasons.append(f"{card_name} supports {commander_name}'s spell-based game plan by rewarding or enabling repeated instant and sorcery casts.")
        elif synergy == 'lifegain':
            reasons.append(f"{card_name} turns life gain into a resource, helping {commander_name} convert incidental life swings into pressure or cards.")
        elif synergy == 'exile':
            if 'exile the top' in oracle_lower or 'play that card' in oracle_lower or 'cast that card' in oracle_lower:
                reasons.append(f"{card_name} gives {commander_name} more cards to play from exile, which keeps the trigger chain moving instead of waiting for the commander to do all the work.")
            elif 'from exile' in oracle_lower:
                reasons.append(f"{card_name} connects directly to {commander_name}'s exile zone plan by rewarding or enabling cards cast from exile.")
            else:
                reasons.append(f"{card_name} supports {commander_name}'s exile plan with card access that can turn into extra triggers and Treasures.")
        elif synergy == 'landfall':
            if 'additional land' in oracle_lower or 'you may play lands' in oracle_lower:
                reasons.append(f"{card_name} helps {commander_name} make more land drops, which means more landfall draw triggers and a faster path to high-mana turns.")
            elif 'landfall' in oracle_lower or 'land you control enters' in oracle_lower:
                reasons.append(f"{card_name} adds another payoff for the land drops {commander_name} already wants to make, so each fetch land or extra land play produces more value.")
            else:
                reasons.append(f"{card_name} supports {commander_name}'s landfall plan by making land drops more frequent or more rewarding.")
        elif synergy == 'voltron':
            if 'equipment' in type_line or 'equip' in oracle_lower:
                reasons.append(f"{card_name} is Equipment that can stay on board through removal and help {commander_name} attack safely, hit harder, or generate combat value.")
            elif 'hexproof' in oracle_lower or 'shroud' in oracle_lower or 'ward' in oracle_lower:
                reasons.append(f"{card_name} protects {commander_name}, which is usually more important for Voltron than adding another pure damage boost.")
            elif "can't be blocked" in oracle_lower or 'flying' in oracle_lower or 'trample' in oracle_lower:
                reasons.append(f"{card_name} improves {commander_name}'s evasion, making combat triggers and commander-damage pressure more reliable.")
            else:
                reasons.append(f"{card_name} helps {commander_name} win through commander damage by adding protection, evasion, or repeatable combat pressure.")
        else:
            reasons.append(f"{card_name} connects to {commander_name}'s {synergy.replace('_', ' ')} theme in a way that advances the deck's core plan.")

        effect_notes = []
        if self._has_card_draw_text(oracle_lower):
            effect_notes.append("It also adds card flow, which helps the deck keep finding action instead of running out of pressure.")
        if synergy == 'board_conversion' and self._is_creature_token_support(oracle_lower, type_line):
            effect_notes.append("Its creature-token production gives the commander more material to amplify in combat.")
        elif synergy != 'board_conversion' and 'create' in oracle_lower and 'token' in oracle_lower:
            effect_notes.append("Its token production gives you extra permanents to build around, sacrifice, or convert into value.")
        if 'sacrifice' in oracle_lower:
            effect_notes.append("The sacrifice text matters because it gives you agency over when your permanents become resources.")
        if 'graveyard' in oracle_lower or 'dies' in oracle_lower:
            effect_notes.append("The graveyard text makes it useful after removal and improves your ability to grind.")
        if synergy == 'counters' and ('+1/+1 counter' in oracle_lower or 'proliferate' in oracle_lower):
            effect_notes.append("Its counter text gives the commander or board a clearer path from small advantages into a real clock.")
        if 'copy' in oracle_lower:
            effect_notes.append("Copy effects are especially strong here because they multiply the best permanent or trigger you already assembled.")

        if effect_notes:
            reasons.append(effect_notes[0])

        return " ".join(reasons)

    def _recommendation_quality_metadata(
        self,
        card_data: Dict,
        synergy: str,
        commander_card: Dict,
        fallback_role: Optional[str] = None
    ) -> Dict:
        """Attach deterministic proof, penalty, and tier metadata for recommendations."""
        oracle_text = card_data.get('oracle_text', '').lower()
        type_line = card_data.get('type_line', '').lower()
        commander_text = self._combined_oracle_text(commander_card)
        score = 50
        job = fallback_role or synergy
        evidence = synergy.replace('_', ' ')
        evidence_tags = []
        penalty_tags = []

        def add_evidence(tag: str):
            if tag not in evidence_tags:
                evidence_tags.append(tag)

        def add_penalty(tag: str):
            if tag not in penalty_tags:
                penalty_tags.append(tag)

        if synergy == 'blink':
            if 'enters the battlefield' in oracle_text and not ('exile' in oracle_text and 'return' in oracle_text):
                job = 'ETB value target'
                evidence = 'repeatable ETB value'
                score = 88
                add_evidence('direct_synergy')
                add_evidence('repeatable_engine')
            elif 'exile' in oracle_text and 'return' in oracle_text:
                job = 'blink enabler'
                evidence = 'reuses or protects your permanents'
                score = 84
                add_evidence('enabler')
                add_evidence('protection')
        elif synergy == 'creature':
            if self._has_creature_spell_text(commander_text) and 'creature' in type_line:
                job = 'creature spell trigger'
                evidence = 'raises creature density for commander triggers'
                score = 84
                add_evidence('direct_synergy')
                add_evidence('creature_density')
                if 'enters the battlefield' in oracle_text or self._has_card_draw_text(oracle_text):
                    score += 6
                    add_evidence('role_value')
            elif 'creature token' in oracle_text:
                job = 'creature material'
                evidence = 'adds bodies for the creature plan'
                score = 76
                add_evidence('enabler')
                add_evidence('creature_token_support')
            elif 'enters the battlefield' in oracle_text:
                job = 'ETB creature value'
                evidence = 'supports creature-entry loops'
                score = 80
                add_evidence('role_value')
        elif synergy == 'board_conversion':
            if self._is_creature_token_support(oracle_text, type_line):
                job = 'wide-board material'
                evidence = 'adds creature material for the commander to convert'
                score = 88
                add_evidence('direct_synergy')
                add_evidence('creature_token_support')
            elif 'creature' in type_line and card_data.get('cmc', 0) <= 2:
                job = 'cheap body'
                evidence = 'sets up the board before the payoff arrives'
                score = 84
                add_evidence('enabler')
                add_evidence('low_setup_cost')
            elif 'creature' in type_line and card_data.get('cmc', 0) <= 3:
                job = 'early attacker'
                evidence = 'becomes a better threat after conversion'
                score = 82
                add_evidence('enabler')
            elif any(term in oracle_text for term in ['creatures you control gain', 'creatures you control have', 'attacking creatures', "can't be blocked"]):
                job = 'combat converter'
                evidence = 'helps the converted board connect'
                score = 84
                add_evidence('direct_synergy')
                add_evidence('payoff')
        elif synergy == 'sacrifice':
            if 'sacrifice a creature' in oracle_text or 'sacrifice another creature' in oracle_text:
                job = 'sacrifice outlet'
                evidence = 'lets you control death triggers'
                score = 88
                add_evidence('direct_synergy')
                add_evidence('sacrifice_outlet')
            elif 'whenever you sacrifice' in oracle_text or 'whenever a creature dies' in oracle_text or 'whenever another creature dies' in oracle_text:
                job = 'death payoff'
                evidence = 'pays off sacrifices and deaths'
                score = 84
                add_evidence('direct_synergy')
                add_evidence('payoff')
            elif 'creature token' in oracle_text:
                job = 'sacrifice fodder'
                evidence = 'creates expendable material'
                score = 74
                add_evidence('enabler')
                add_evidence('creature_token_support')
        elif synergy == 'counters':
            counter_plan = self._counter_plan_for_text(commander_text)
            if 'proliferate' in oracle_text and counter_plan in ['proliferate', 'named_counters']:
                job = 'named-counter scaling'
                evidence = 'adds counters after the commander establishes them'
                score = 86
                add_evidence('direct_synergy')
                add_evidence('counter_scaling')
            elif self._is_counter_multiplier(oracle_text):
                job = 'counter multiplier'
                evidence = 'increases counters produced by the engine'
                score = 82
                add_evidence('direct_synergy')
                add_evidence('counter_placement')
            elif self._is_counter_payoff(oracle_text):
                job = 'counter payoff'
                evidence = 'rewards counters already being present'
                score = 76
                add_evidence('payoff')
            elif '+1/+1 counter' in oracle_text or 'counter on' in oracle_text:
                add_penalty('wrong_counter_context')
                score = 60
        elif synergy == 'voltron':
            if 'equipment' in type_line or 'equip' in oracle_text:
                job = 'equipment pressure'
                evidence = 'reusable combat upgrade'
                score = 82
                add_evidence('direct_synergy')
                add_evidence('repeatable_engine')
            elif any(term in oracle_text for term in ['hexproof', 'shroud', 'ward']):
                job = 'commander protection'
                evidence = 'keeps the threat on board'
                score = 86
                add_evidence('protection')
            elif any(term in oracle_text for term in ["can't be blocked", 'flying', 'trample']):
                job = 'combat evasion'
                evidence = 'helps damage and triggers connect'
                score = 80
                add_evidence('enabler')
        elif synergy == 'tokens':
            if 'twice that many' in oracle_text or 'double the number' in oracle_text:
                job = 'token multiplier'
                evidence = 'scales repeatable token output'
                score = 88
                add_evidence('direct_synergy')
                add_evidence('payoff')
            elif 'tokens you control' in oracle_text:
                job = 'token payoff'
                evidence = 'rewards the board the commander makes'
                score = 80
                add_evidence('payoff')
            elif 'creature token' in oracle_text:
                job = 'token maker'
                evidence = 'adds bodies to the core plan'
                score = 74
                add_evidence('enabler')
                add_evidence('creature_token_support')
            elif 'treasure token' in oracle_text or 'clue token' in oracle_text or 'food token' in oracle_text:
                add_penalty('wrong_token_type')
                score = 58
        elif synergy == 'artifact_tokens':
            if 'whenever you sacrifice' in oracle_text or 'sacrifice an artifact' in oracle_text:
                job = 'artifact-token payoff'
                evidence = 'converts temporary tokens into value'
                score = 84
                add_evidence('direct_synergy')
                add_evidence('payoff')
            elif self._has_artifact_token_text(oracle_text):
                job = 'artifact-token maker'
                evidence = 'adds spendable artifacts'
                score = 76
                add_evidence('enabler')
        elif synergy == 'exile':
            if 'from exile' in oracle_text:
                job = 'exile payoff'
                evidence = 'rewards cards cast from exile'
                score = 84
                add_evidence('direct_synergy')
                add_evidence('payoff')
            else:
                job = 'impulse draw'
                evidence = 'keeps exile-play triggers flowing'
                score = 78
                add_evidence('enabler')
                add_evidence('card_access')
        elif synergy == 'artifact':
            if any(term in oracle_text for term in ['whenever an artifact', 'artifacts you control', 'sacrifice an artifact', 'artifact card']):
                job = 'artifact engine'
                evidence = 'cares about artifacts directly'
                score = 84
                add_evidence('direct_synergy')
            elif 'equipment' in type_line or 'equip' in oracle_text:
                job = 'equipment support'
                evidence = 'artifact card with combat utility'
                score = 78
                add_evidence('enabler')
        elif synergy == 'enchantment':
            if any(term in oracle_text for term in ['whenever an enchantment', 'enchantments you control', 'enchantment card']):
                job = 'enchantment engine'
                evidence = 'cares about enchantments directly'
                score = 84
                add_evidence('direct_synergy')
            elif 'aura' in type_line or 'enchant ' in oracle_text or 'enchanted creature' in oracle_text:
                job = 'aura support'
                evidence = 'supports the enchantment package'
                score = 78
                add_evidence('enabler')
        elif synergy == 'landfall':
            if 'additional land' in oracle_text or 'you may play lands' in oracle_text:
                job = 'extra land drop'
                evidence = 'increases landfall trigger frequency'
                score = 88
                add_evidence('direct_synergy')
                add_evidence('enabler')
            elif 'landfall' in oracle_text or 'land you control enters' in oracle_text:
                job = 'landfall payoff'
                evidence = 'rewards the same land-drop plan'
                score = 82
                add_evidence('payoff')
        elif synergy == 'lifegain':
            if self._has_lifegain_reward_text(oracle_text):
                job = 'lifegain payoff'
                evidence = 'rewards life gain directly'
                score = 84
                add_evidence('direct_synergy')
            elif re.search(r'\bgain(?:s|ed)? life\b', oracle_text):
                job = 'lifegain enabler'
                evidence = 'supplies life gain triggers'
                score = 76
                add_evidence('enabler')
        elif synergy == 'instant_sorcery':
            if any(term in oracle_text for term in ['whenever you cast an instant', 'whenever you cast a sorcery', 'instant or sorcery']):
                job = 'spell payoff'
                evidence = 'rewards instant and sorcery casting'
                score = 84
                add_evidence('direct_synergy')
            elif 'copy target instant' in oracle_text or 'copy target sorcery' in oracle_text:
                job = 'spell copier'
                evidence = 'multiplies key spells'
                score = 80
                add_evidence('payoff')

        if self._has_card_draw_text(oracle_text):
            score += 4
            add_evidence('card_flow')
        if 'mana value' in oracle_text or 'costs' in oracle_text:
            score += 2
        if card_data.get('cmc', 0) >= 6 and not any(tag in evidence_tags for tag in ['payoff', 'direct_synergy']):
            add_penalty('high_mana_value')
            score -= 8
        if 'until end of turn' in oracle_text and not any(tag in evidence_tags for tag in ['protection', 'payoff']):
            add_penalty('one_shot_effect')
            score -= 5
        if self._is_generic_mana_card(card_data):
            add_penalty('generic_staple')
            score -= 12
        if not evidence_tags:
            add_penalty('low_theme_overlap')
            score = min(score, 64)

        score = max(0, min(score, 95))
        if score >= 86 and 'direct_synergy' in evidence_tags:
            confidence = 'core'
            fit_tier = 'Core Fit'
        elif score >= 78 and evidence_tags:
            confidence = 'support'
            fit_tier = 'Strong Support'
        elif score >= 72 and evidence_tags:
            confidence = 'alternate'
            fit_tier = 'Role Fit'
        else:
            confidence = 'speculative'
            fit_tier = 'Speculative'
        return {
            'job': job,
            'confidence': confidence,
            'fit_tier': fit_tier,
            'score': score,
            'evidence': evidence,
            'evidence_tags': evidence_tags,
            'penalty_tags': penalty_tags,
        }

    def _generate_validated_recommendation_reason(
        self,
        card_data: Dict,
        commander_name: str,
        synergy: str,
        quality: Dict
    ) -> str:
        """Build why-it-fits copy only from validated evidence and penalties."""
        card_name = card_data.get('name', 'This card')
        oracle_text = card_data.get('oracle_text', '').lower()
        type_line = card_data.get('type_line', '').lower()
        evidence_tags = set(quality.get('evidence_tags', []))
        penalty_tags = set(quality.get('penalty_tags', []))
        job = quality.get('job', synergy.replace('_', ' '))

        action = f"{card_name} fills the {job} role."
        if 'creature_token_support' in evidence_tags:
            action = f"{card_name} creates or supports creature material."
        elif 'sacrifice_outlet' in evidence_tags:
            action = f"{card_name} gives the deck a real sacrifice outlet."
        elif 'counter_scaling' in evidence_tags:
            action = f"{card_name} adds proliferate or counter-scaling text."
        elif 'counter_placement' in evidence_tags:
            action = f"{card_name} increases the counters your engine creates."
        elif 'protection' in evidence_tags:
            action = f"{card_name} protects the commander or key permanents."
        elif 'card_flow' in evidence_tags:
            action = f"{card_name} adds card flow while filling the {job} role."
        elif 'payoff' in evidence_tags:
            action = f"{card_name} rewards the board state this deck is trying to build."
        elif 'enabler' in evidence_tags:
            action = f"{card_name} is an enabler for the deck's {synergy.replace('_', ' ')} plan."

        fit = f"That matters for {commander_name} because the validated match is {quality.get('evidence', synergy.replace('_', ' '))}."
        if synergy == 'board_conversion':
            fit = f"That matters for {commander_name} because board-conversion commanders need material or team-wide combat support before the payoff turn."
        elif synergy == 'tokens' and 'creature_token_support' in evidence_tags:
            fit = f"That matters for {commander_name} because the commander wants bodies or token payoffs, not unrelated token vocabulary."
        elif synergy == 'artifact_tokens':
            fit = f"That matters for {commander_name} because the card creates or converts artifact tokens the deck can actually use."
        elif synergy == 'counters':
            fit = f"That matters for {commander_name} because the card interacts with the same counter plan instead of merely mentioning counters."
        elif synergy == 'sacrifice':
            fit = f"That matters for {commander_name} because sacrifice decks need outlets, fodder, or payoffs that turn deaths into resources."
        elif synergy == 'blink':
            fit = f"That matters for {commander_name} because blink decks need reusable ETB targets or ways to reset and protect permanents."

        caution = ""
        if 'high_mana_value' in penalty_tags:
            caution = " Its mana value means it should be treated as a payoff slot, not early setup."
        elif 'one_shot_effect' in penalty_tags:
            caution = " Because the effect is temporary, it is best as support rather than a core engine."
        elif 'generic_staple' in penalty_tags:
            caution = " This is recommended only as a role piece, not as commander-specific synergy."

        return f"{action} {fit}{caution}"

    def _build_strategy_sections(self, tips: List[str]) -> List[Dict]:
        """Group tips into small deterministic pages without changing legacy output."""
        sections = [
            {'id': 'game_plan', 'label': 'Game Plan', 'tips': []},
            {'id': 'build_priorities', 'label': 'Build Priorities', 'tips': []},
            {'id': 'foundation', 'label': 'Foundation', 'tips': []},
            {'id': 'deep', 'label': 'Deep Search', 'tips': []},
        ]

        for tip in tips:
            if tip.startswith('Deep Strategy'):
                sections[3]['tips'].append(tip)
            elif tip.startswith('Use 36-38') or tip.startswith('Reserve 7-10'):
                sections[2]['tips'].append(tip)
            elif len(sections[0]['tips']) < 3:
                sections[0]['tips'].append(tip)
            else:
                sections[1]['tips'].append(tip)

        return [section for section in sections if section['tips']]

    def _build_recommended_sections(self, suggested_cards: List[Dict]) -> List[Dict]:
        """Group recommendations into pages by deterministic quality tier."""
        section_map = {
            'core': {'id': 'core', 'label': 'Core Fit', 'cards': []},
            'support': {'id': 'support', 'label': 'Strong Support', 'cards': []},
            'alternate': {'id': 'alternate', 'label': 'Role Fit', 'cards': []},
        }

        for index, card in enumerate(suggested_cards):
            confidence = card.get('confidence')
            if confidence not in section_map:
                confidence = 'core' if index < 4 else 'support' if index < 8 else 'alternate'
            section_map[confidence]['cards'].append(card)

        sections = [section for section in section_map.values() if section['cards']]
        if len(sections) == 1 and len(sections[0]['cards']) > 6:
            first_cards = sections[0]['cards']
            sections[0]['cards'] = first_cards[:6]
            sections.append({'id': 'alternate', 'label': 'More Options', 'cards': first_cards[6:]})
        return sections
    
    def _get_card_images(self, scryfall_card: Dict) -> Dict[str, Optional[str]]:
        """Extract card image URLs from Scryfall data, handling double-faced cards"""
        if not scryfall_card:
            return {'front': None, 'back': None}
        
        # Check if it's a double-faced card (has card_faces)
        if 'card_faces' in scryfall_card:
            faces = scryfall_card['card_faces']
            front_image = faces[0].get('image_uris', {}).get('normal') or faces[0].get('image_uris', {}).get('large')
            back_image = faces[1].get('image_uris', {}).get('normal') or faces[1].get('image_uris', {}).get('large') if len(faces) > 1 else None
            return {'front': front_image, 'back': back_image}
        else:
            # Single-faced card
            image_uris = scryfall_card.get('image_uris', {})
            front_image = image_uris.get('normal') or image_uris.get('large') or image_uris.get('small')
            return {'front': front_image, 'back': None}
    
    def _get_card_image(self, scryfall_card: Dict) -> Optional[str]:
        """Legacy method - returns only front image"""
        images = self._get_card_images(scryfall_card)
        return images['front']
    
    def _colors_to_query(self, color_identity: List[str]) -> str:
        """Convert color identity to Scryfall query format"""
        if not color_identity:
            return "c:c"
        return "".join(color_identity).lower()

    def _color_identity_filter(self, color_identity: List[str]) -> str:
        """Build a Scryfall Commander legality filter for card color identity."""
        if not color_identity:
            return "id:c"
        return f"id<={''.join(color_identity).lower()}"

    def _build_query_for_synergy(
        self,
        synergy: str,
        color_identity: List[str],
        commander_constraints: Optional[Dict] = None
    ) -> Optional[str]:
        """Build a Scryfall query for a commander synergy theme."""
        color_filter = self._color_identity_filter(color_identity)
        commander_constraints = commander_constraints or {}

        if synergy == 'enchantment':
            cmc_filter = ""
            if 'max_enchantment_cmc' in commander_constraints:
                cmc_filter = f" cmc<={commander_constraints['max_enchantment_cmc']}"
            return f"t:enchantment{cmc_filter} {color_filter} f:commander"

        if synergy == 'counters':
            counter_plan = commander_constraints.get('counter_plan')
            if counter_plan == 'proliferate':
                return f'(o:proliferate OR o:"+1/+1 counter" OR o:"-1/-1 counter" OR o:"additional +1/+1 counter" OR o:"twice that many") {color_filter} f:commander'
            if counter_plan == 'named_counters':
                return f'o:proliferate {color_filter} f:commander'
            if counter_plan == 'self_counters':
                return f'(o:"additional +1/+1 counter" OR o:"that many plus one" OR o:"twice that many" OR o:"double the number of counters" OR o:"move counters" OR o:"commander" OR o:modified) {color_filter} f:commander'
            if counter_plan == 'board_counters':
                return f'(o:"additional +1/+1 counter" OR o:"creatures you control" o:"+1/+1 counter" OR o:"creatures you control with counters" OR o:modified OR o:"for each counter") {color_filter} f:commander'
            if counter_plan == 'negative_counters':
                return f'(o:"-1/-1 counter" OR o:"for each counter" OR o:"remove a counter") {color_filter} f:commander'
            return f'(o:"additional +1/+1 counter" OR o:"that many plus one" OR o:"creatures you control with counters" OR o:modified OR o:"for each counter") {color_filter} f:commander'

        synergy_queries = {
            'artifact': '(o:"artifact card" OR o:"artifact spell" OR o:"artifacts you control" OR o:"whenever an artifact" OR o:"sacrifice an artifact" OR t:equipment OR o:equip)',
            'board_conversion': '(t:creature OR o:"creature token" OR o:"creature tokens" OR o:"create a 1/1" OR o:"create two" OR o:"create three" OR o:"create X" OR o:thopter OR o:servo OR o:myr OR o:construct OR o:"creatures you control have" OR o:"creatures you control gain" OR o:"attacking creatures")',
            'blink': '(o:exile o:return OR o:"enters the battlefield")',
            'creature': '(o:"creature spell" OR o:"creature enters" OR o:"creatures you control" OR o:"whenever another creature" OR o:"whenever a creature" OR o:"creature token")',
            'exile': '(o:"exile the top" OR o:"play that card" OR o:"cast that card" OR o:"from exile" OR o:"until end of your next turn")',
            'graveyard': '(o:"from your graveyard" OR o:"put into your graveyard" OR o:dies OR o:reanimate OR o:flashback OR o:escape OR o:unearth)',
            'instant_sorcery': '(t:instant OR t:sorcery OR o:"instant or sorcery")',
            'landfall': '(o:landfall OR o:"additional land" OR o:"land you control enters")',
            'lifegain': '(o:"whenever you gain life" OR o:"if you gained life" OR o:"life total" OR o:"life you gained")',
            'sacrifice': '(o:"sacrifice a creature" OR o:"sacrifice another creature" OR o:"whenever you sacrifice" OR o:"whenever a creature dies" OR o:"whenever another creature dies" OR o:"creature token")',
            'tokens': '(o:"creature token" OR o:"creature tokens" OR o:populate OR o:"tokens you control" OR o:"one or more tokens" OR o:"twice that many")',
            'artifact_tokens': '(o:"Treasure token" OR o:"Clue token" OR o:"Food token" OR o:"Blood token" OR o:"artifact token")',
            'voltron': "(t:equipment OR t:aura OR o:equip OR o:attach)",
        }

        base_query = synergy_queries.get(synergy)
        if not base_query:
            return None

        return f"{base_query} {color_filter} f:commander"
    
    def _extract_price(self, prices: Dict) -> Optional[float]:
        """Extract USD price from Scryfall prices"""
        try:
            if prices.get('usd'):
                return float(prices['usd'])
            elif prices.get('usd_foil'):
                return float(prices['usd_foil'])
        except (ValueError, TypeError):
            pass
        return None

    def _generate_commander_strategy_tips(
        self,
        commander_card: Dict,
        synergies: List[str],
        commander_constraints: Optional[Dict] = None
    ) -> List[str]:
        """Generate commander lookup tips from the actual oracle text and color identity."""
        commander_constraints = commander_constraints or {}
        commander_name = commander_card.get('name', 'This commander')
        oracle_text = commander_card.get('oracle_text', '').lower()
        type_line = commander_card.get('type_line', '').lower()
        color_identity = commander_card.get('color_identity', [])
        tips = []

        if 'enchantment' in synergies:
            if commander_constraints.get('max_enchantment_cmc'):
                max_cmc = commander_constraints['max_enchantment_cmc']
                examples = self._role_examples('enchantment', color_identity, synergies)
                tips.append(f"{commander_name} wants a tight enchantment toolbox. Prioritize enchantments with mana value {max_cmc} or less so attack triggers can find protection, card draw, removal, or a win condition on demand.")
                if examples:
                    tips.append(f"Good enchantment targets in this color identity include {examples}; choose the mix based on whether the deck needs protection, cards, or table control.")
            else:
                examples = self._role_examples('enchantment', color_identity, synergies)
                tips.append(f"Raise the enchantment density only when those enchantments advance the commander's trigger pattern. {examples or 'Repeatable draw, protection, and removal enchantments'} are higher quality than a pile of unrelated Auras.")

        if 'artifact' in synergies:
            if 'graveyard' in oracle_text:
                tips.append(f"{commander_name} rewards artifacts that can be sacrificed, milled, or traded off and then reused. Favor artifacts with enters/dies value over mana-only rocks once the baseline ramp count is healthy.")
            elif 'equipment' in oracle_text or 'attach' in oracle_text or 'equipped' in oracle_text:
                tips.append(f"{commander_name} cares about Equipment as part of the main engine. Prioritize cheap equip costs, haste, protection, and combat triggers before expensive power-only Equipment.")
            else:
                tips.append(f"Keep the artifact package purposeful: ramp early, then convert artifact count into cards, sacrifice value, or a clear finisher instead of filling slots with generic rocks.")

        if 'board_conversion' in synergies:
            tips.append(f"{commander_name} turns quantity into combat pressure. Build the board first with cheap bodies, token makers, and creatures that leave multiple attackers behind, then let the commander convert that material into damage.")
            tips.append("Avoid leaning on expensive single threats that do not multiply the board. This profile improves most when one card creates several attackers or makes the whole team safer in combat.")

        if 'creature' in synergies:
            if 'board_conversion' in synergies:
                pass
            elif self._has_creature_spell_text(oracle_text):
                tips.append(f"{commander_name} rewards casting creatures, so use a curve with enough low and mid-cost creatures to double-spell. ETB creatures are especially useful because they still matter if the commander is removed.")
            elif 'enters the battlefield' in oracle_text or 'enters' in oracle_text:
                tips.append(f"{commander_name} wants creatures that create value when they enter or when other creatures enter. Prioritize ETB creatures, token makers, and ways to reuse those triggers over vanilla bodies.")
            elif 'creatures you control' in oracle_text or 'creatures get' in oracle_text:
                tips.append(f"{commander_name} rewards having a real board. Mix cheap creatures, token production, and protection so the deck can rebuild after wipes instead of relying on one oversized threat.")
            else:
                tips.append(f"Keep the creature package synergistic: bodies should draw cards, ramp, recur, remove threats, or multiply the commander's main trigger rather than only filling the curve.")

        if 'graveyard' in synergies:
            if self._has_creature_card_text(oracle_text) and 'graveyard' in oracle_text:
                tips.append(f"{commander_name} wants creatures that are useful both on board and in the graveyard. Self-mill, discard outlets, and recursion are strongest when the creatures have ETB, death, or cast value.")
            elif 'artifact card' in oracle_text and 'graveyard' in oracle_text:
                tips.append(f"Stock the graveyard with artifacts deliberately. Self-mill and sacrifice outlets become card advantage when the artifact package includes reusable value pieces.")
            else:
                tips.append(f"Treat the graveyard as a second hand, but include a few ways to recover from graveyard hate so the deck is not forced to win through one zone.")

        if 'tokens' in synergies:
            if 'creature token' in oracle_text or 'populate' in oracle_text:
                tips.append(f"{commander_name} benefits most from token makers that create bodies with relevant types, evasion, or scaling payoffs. Token doublers are best after the deck already has enough repeatable token production.")
            else:
                tips.append(f"Use token makers that leave behind resources the deck can spend, sacrifice, copy, or pump. Avoid token cards that make bodies without supporting the commander's payoff.")

        if 'artifact_tokens' in synergies:
            tips.append(f"Treasure, Clue, Food, and Blood tokens should do more than sit around. Add payoffs for sacrificing artifacts or counting artifacts so temporary tokens become lasting advantage.")

        if 'counters' in synergies:
            counter_plan = commander_constraints.get('counter_plan') or self._counter_plan_for_text(oracle_text)
            if counter_plan == 'named_counters':
                named_terms = self._named_counter_terms(oracle_text)
                counter_label = f"{named_terms[0]} counters" if named_terms else "named counters"
                tips.append(f"Treat {counter_label} as its own mechanic. Proliferate can support it after the commander places the first counter, but generic +1/+1 counter cards do not advance this plan.")
            elif 'proliferate' in oracle_text:
                counter_kind = "-1/-1 counters" if "-1/-1 counter" in oracle_text else "+1/+1 counters" if "+1/+1 counter" in oracle_text else "counters"
                tips.append(f"Put {counter_kind} on multiple permanents before proliferating. {commander_name} scales much better when each proliferate trigger advances several threats or weakens several opposing creatures.")
            else:
                tips.append(f"Use repeatable counter placement and cards that reward counters already being present. One-shot pump spells look flashy, but engines are what make {commander_name} reliable.")

        if 'instant_sorcery' in synergies:
            tips.append(f"Keep the spell curve low. Cheap cantrips, interaction, and flashback-style effects let {commander_name} trigger multiple times while still holding up answers.")

        if 'lifegain' in synergies:
            tips.append(f"Separate lifegain enablers from lifegain payoffs. {commander_name} needs repeatable life gain to turn cards like draw engines, counters, or drain effects into dependable pressure.")

        if 'sacrifice' in synergies:
            tips.append(f"Balance three pieces: fodder, free or cheap sacrifice outlets, and payoffs. The deck improves most when sacrificed permanents replace themselves or trigger recursion.")

        if 'landfall' in synergies:
            tips.append(f"Extra land drops and fetch lands are the fuel. Landfall payoffs should either draw cards, make mana, or create a closing board state so each land matters beyond the first trigger.")

        if 'blink' in synergies:
            if 'another target' in oracle_text or 'another creature' in oracle_text:
                tips.append(f"{commander_name} needs profitable blink targets. Load the deck with ETB creatures and permanents, then use the commander to reuse removal, ramp, and card draw while protecting key pieces from targeted removal.")
            else:
                tips.append(f"Blink effects are strongest when they reuse ETB value or reset threatened permanents. Avoid blink cards without enough targets that immediately replace mana or cards.")

        if 'exile' in synergies:
            if 'play a card from exile' in oracle_text or 'from exile' in oracle_text:
                tips.append(f"{commander_name} wants a steady flow of cards to play from exile. Impulse draw and cast-from-exile effects are better than one-shot exile removal because they keep the commander trigger chain active.")
            else:
                tips.append(f"Exile should be treated as card access or a payoff zone here, not just removal. Prioritize cards that let you play or cast the exiled cards.")

        if 'voltron' in synergies and not any('Equipment' in tip or 'Auras' in tip for tip in tips):
            tips.append(f"Protect {commander_name} before increasing damage. Haste, evasion, and hexproof effects make commander-damage plans more reliable than simply adding larger buffs.")

        if not tips:
            tips.append(f"Start by identifying the repeated action in {commander_name}'s text, then add cards that perform or reward that action at low mana values.")

        ramp_examples = self._role_examples('ramp', color_identity, synergies)
        interaction_examples = self._role_examples('interaction', color_identity, synergies)
        tips.append(f"Use 36-38 lands and 10-12 ramp sources. {ramp_examples or 'Efficient two-mana ramp'} keeps the commander online without crowding out synergy slots.")
        tips.append(f"Reserve 7-10 slots for answers and protection. {interaction_examples or 'Low-cost interaction in your colors'} lets the deck keep its engine after removal and board wipes.")

        return tips

    def _generate_deep_commander_strategy_tips(
        self,
        commander_card: Dict,
        synergies: List[str],
        commander_constraints: Optional[Dict] = None
    ) -> List[str]:
        """Generate extra notes that make opt-in deep strategy visibly deeper."""
        commander_constraints = commander_constraints or {}
        commander_name = commander_card.get('name', 'This commander')
        oracle_text = commander_card.get('oracle_text', '').lower()
        color_identity = commander_card.get('color_identity', [])
        notes = []

        if commander_constraints.get('max_enchantment_cmc'):
            max_cmc = commander_constraints['max_enchantment_cmc']
            notes.append(f"Deep Strategy - Tutor Map: Separate the {max_cmc}-mana-or-less targets into protection, card advantage, removal, and finishers. That keeps each attack trigger from becoming a generic value search.")
        elif synergies:
            theme_names = ", ".join(theme.replace('_', ' ') for theme in synergies[:3])
            notes.append(f"Deep Strategy - Priority Lane: Treat {theme_names} as the main lane, then cut cards that only share colors with {commander_name} but do not advance those triggers.")
        else:
            notes.append(f"Deep Strategy - Priority Lane: Build around the repeated action in {commander_name}'s text first, then add staples only after that engine has enough density.")

        if 'artifact' in synergies:
            if 'graveyard' in oracle_text:
                notes.append("Deep Strategy - Artifact Loop: Split artifacts into self-sacrificing value pieces, recursion targets, and payoffs. Mana rocks are useful early, but the best cards still matter after they are milled or destroyed.")
            elif 'equipment' in oracle_text or 'equipped' in oracle_text:
                notes.append("Deep Strategy - Equipment Curve: Keep equip costs low enough to move protection and evasion after removal. One expensive Equipment is weaker than several pieces that let the commander attack safely.")
            else:
                notes.append("Deep Strategy - Artifact Density: Count only artifacts that feed the commander's trigger or convert into cards, damage, or recursion. Raw artifact count should serve a payoff.")
        if 'creature' in synergies:
            if 'board_conversion' in synergies:
                notes.append("Deep Strategy - Board Conversion: Count setup cards by how much material they create before the commander arrives. Cheap bodies, repeatable token makers, and team evasion matter more than standalone value creatures.")
            elif self._has_creature_spell_text(oracle_text):
                notes.append("Deep Strategy - Creature Casting: Bias toward creatures that replace themselves, ramp, or interact when cast. That keeps the commander trigger productive even when the table removes the first board.")
            elif 'enters the battlefield' in oracle_text or 'creature enters' in oracle_text:
                notes.append("Deep Strategy - ETB Texture: Mix token makers with individually strong ETB creatures, then add blink or bounce only when there are enough targets that immediately create cards, mana, or removal.")
            else:
                notes.append("Deep Strategy - Board Quality: Creature count matters less than creature jobs. Prioritize bodies that protect, draw, ramp, recur, or multiply the commander's payoff.")
        if 'enchantment' in synergies:
            notes.append("Deep Strategy - Enchantment Slots: Separate enchantments into engines, protection, removal, and finishers. Auras need a specific payoff or protection role before they earn space.")
        if any(theme in synergies for theme in ['tokens', 'artifact_tokens', 'sacrifice']):
            notes.append("Deep Strategy - Resource Loop: Check that the deck has makers, outlets, and payoffs in balance. Too many payoffs without repeatable material will make strong cards look stranded.")
        if any(theme in synergies for theme in ['graveyard', 'exile', 'blink', 'landfall']):
            notes.append("Deep Strategy - Sequencing: Favor cards that generate value over multiple turns or zones. This kind of commander improves when setup pieces replace themselves instead of asking you to spend a full card for setup only.")
        if any(theme in synergies for theme in ['voltron', 'counters', 'lifegain']):
            notes.append(f"Deep Strategy - Protection Check: {commander_name} likely needs protection before payoff density. Haste, ward/hexproof, and instant-speed saves make the engine much less fragile.")

        interaction_examples = self._role_examples('interaction', color_identity, synergies)
        if interaction_examples:
            notes.append(f"Deep Strategy - Table Safety: Reserve slots for answers like {interaction_examples}; deep recommendations should improve the engine without leaving it unable to stop faster decks.")

        return notes

    def _candidate_card_for_synergy(self, card: Dict, synergy: str) -> Dict:
        """Select the most relevant face for validating a double-faced candidate."""
        if card.get('card_faces') and len(card.get('card_faces', [])) > 1:
            if synergy == 'enchantment':
                return self._get_correct_face_for_validation(card, 'enchantment')
            if synergy == 'artifact':
                return self._get_correct_face_for_validation(card, 'artifact')
            if synergy == 'creature':
                return self._get_correct_face_for_validation(card, 'creature')
        return card

    def _passes_commander_recommendation_constraints(
        self,
        card_extracted: Dict,
        effective_cmc: float,
        commander_constraints: Dict
    ) -> bool:
        """Apply commander-specific hard constraints after relevance validation."""
        if self._is_land_card(card_extracted):
            return False

        if self._is_generic_mana_card(card_extracted):
            return False

        if 'max_enchantment_cmc' in commander_constraints:
            if 'enchantment' in card_extracted['type_line'].lower():
                if effective_cmc > commander_constraints['max_enchantment_cmc']:
                    return False

        if 'max_tutor_cmc' in commander_constraints:
            if effective_cmc > commander_constraints['max_tutor_cmc']:
                return False

        return True

    def _build_commander_recommendation(
        self,
        card: Dict,
        card_extracted: Dict,
        effective_cmc: float,
        synergy: str,
        commander_card: Dict,
        commander_name: str,
        minimum_score: int
    ) -> Optional[Dict]:
        """Return compact recommendation data when a candidate clears the quality floor."""
        quality = self._recommendation_quality_metadata(
            card_extracted,
            synergy,
            commander_card
        )
        if quality['score'] < minimum_score:
            return None
        if not quality.get('evidence_tags') or quality.get('confidence') == 'speculative':
            return None

        image_data = self._get_card_images(card)
        reason = self._generate_validated_recommendation_reason(
            card_extracted,
            commander_name,
            synergy,
            quality
        )

        return {
            'name': card_extracted['name'],
            'cmc': effective_cmc,
            'role': synergy,
            'job': quality['job'],
            'confidence': quality['confidence'],
            'fit_tier': quality['fit_tier'],
            'score': quality['score'],
            'evidence': quality['evidence'],
            'evidence_tags': quality['evidence_tags'],
            'penalty_tags': quality['penalty_tags'],
            'reason': reason,
            'image_url': image_data['front'],
            'image_url_back': image_data['back']
        }

    async def _search_commander_recommendations(
        self,
        commander_card: Dict,
        synergies: List[str],
        color_identity: List[str],
        commander_constraints: Dict,
        max_cards: int,
        search_budget: int,
        per_synergy_limit: int,
        query_limit: int,
        minimum_score: int,
        exclude_names: Optional[Set[str]] = None,
        concurrency: int = 3,
    ) -> List[Dict]:
        """Search Scryfall in bounded parallel and keep only commander-specific cards."""
        extracted = self.scryfall.extract_card_data(commander_card)
        commander_name = extracted['name']
        seen_names = {commander_name.lower()}
        seen_names.update(name.lower() for name in (exclude_names or set()))

        search_specs = []
        for synergy in synergies[:search_budget]:
            query = self._build_query_for_synergy(synergy, color_identity, commander_constraints)
            if query:
                search_specs.append((synergy, query))

        if not search_specs:
            return []

        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def run_search(synergy: str, query: str):
            async with semaphore:
                results = await self.scryfall.search_cards_by_criteria(query, limit=query_limit)
                return synergy, results

        search_results = await asyncio.gather(
            *(run_search(synergy, query) for synergy, query in search_specs)
        )

        candidates = []
        order = 0
        for synergy, results in search_results:
            cards_added_for_synergy = 0
            for card in results:
                if cards_added_for_synergy >= per_synergy_limit:
                    break

                card_name = card.get('name', '').lower()
                if not card_name or card_name in seen_names:
                    continue
                if not self._is_legal_for_deck(card, color_identity):
                    continue

                card_to_validate = self._candidate_card_for_synergy(card, synergy)
                card_extracted = self.scryfall.extract_card_data(card_to_validate)
                extracted_name = card_extracted['name'].lower()
                if extracted_name in seen_names:
                    continue

                effective_cmc = self._calculate_effective_cmc(card_to_validate)
                if not self._card_matches_synergy(card_extracted, synergy):
                    continue
                if not self._card_matches_commander_context(card_extracted, synergy, commander_card):
                    continue
                if not self._passes_commander_recommendation_constraints(
                    card_extracted,
                    effective_cmc,
                    commander_constraints
                ):
                    continue

                recommendation = self._build_commander_recommendation(
                    card,
                    card_extracted,
                    effective_cmc,
                    synergy,
                    commander_card,
                    commander_name,
                    minimum_score
                )
                if not recommendation:
                    continue

                recommendation['_order'] = order
                candidates.append(recommendation)
                seen_names.add(extracted_name)
                cards_added_for_synergy += 1
                order += 1

        candidates.sort(key=lambda card: (-card.get('score', 0), card.get('_order', 0)))
        for card in candidates:
            card.pop('_order', None)
        return candidates[:max_cards]

    async def analyze_commander(self, commander_card: Dict, deep: bool = False) -> Dict:
        """Analyze a commander and provide strategy tips"""
        extracted = self.scryfall.extract_card_data(commander_card)

        # Detect synergies
        synergies = self._detect_commander_synergies(commander_card)
        color_identity = extracted['color_identity']
        commander_constraints = self._get_commander_constraints(commander_card)
        tips = self._generate_commander_strategy_tips(commander_card, synergies, commander_constraints)
        if deep:
            tips.extend(self._generate_deep_commander_strategy_tips(commander_card, synergies, commander_constraints))

        suggested_cards = await self._search_commander_recommendations(
            commander_card=commander_card,
            synergies=synergies,
            color_identity=color_identity,
            commander_constraints=commander_constraints,
            max_cards=5,
            search_budget=5 if deep else 3,
            per_synergy_limit=4 if deep else 3,
            query_limit=24 if deep else 16,
            minimum_score=84,
            concurrency=3,
        )
        
        # Generate combos
        combos = self._generate_combo_suggestions(extracted['name'], synergies, [])
        
        return {
            'name': extracted['name'],
            'type_line': extracted['type_line'],
            'oracle_text': extracted['oracle_text'],
            'cmc': extracted['cmc'],
            'color_identity': extracted['color_identity'],
            'power': commander_card.get('power'),
            'toughness': commander_card.get('toughness'),
            'image_url': self._get_card_image(commander_card),
            'synergies': synergies,
            'strategy_tips': tips,
            'strategy_sections': self._build_strategy_sections(tips),
            'suggested_cards': suggested_cards,
            'recommended_sections': self._build_recommended_sections(suggested_cards),
            'combos': combos,
            'analysis_depth': 'deep' if deep else 'fast'
        }

    async def find_more_commander_recommendations(
        self,
        commander_card: Dict,
        exclude_names: Optional[List[str]] = None,
        page: int = 1,
    ) -> Dict:
        """Run an explicit broader recommendation pass after the user asks for more."""
        extracted = self.scryfall.extract_card_data(commander_card)
        synergies = self._detect_commander_synergies(commander_card)
        color_identity = extracted['color_identity']
        commander_constraints = self._get_commander_constraints(commander_card)
        excluded = {name.lower() for name in (exclude_names or [])}

        more_cards = await self._search_commander_recommendations(
            commander_card=commander_card,
            synergies=synergies,
            color_identity=color_identity,
            commander_constraints=commander_constraints,
            max_cards=8,
            search_budget=8,
            per_synergy_limit=5,
            query_limit=36,
            minimum_score=72,
            exclude_names=excluded,
            concurrency=3,
        )

        for card in more_cards:
            if card.get('confidence') == 'core':
                card['confidence'] = 'support'

        return {
            'commander_name': extracted['name'],
            'suggested_cards': more_cards,
            'recommended_sections': self._build_recommended_sections(more_cards),
            'page': page,
            'has_more': len(more_cards) >= 8,
        }
    
    def _quote_scryfall_phrase(self, value: str) -> str:
        """Quote a user phrase for Scryfall syntax after stripping unsafe syntax."""
        cleaned = re.sub(r'[^A-Za-z0-9 +/#\'-]', ' ', value).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return f'"{cleaned}"' if ' ' in cleaned else cleaned

    def _parse_search_terms(self, search_text: Optional[str], keywords: Optional[List[str]] = None) -> List[str]:
        """Parse freeform search text and legacy keyword filters into normalized terms."""
        raw_terms = []
        if search_text:
            quoted_terms = re.findall(r'"([^"]+)"', search_text)
            unquoted_text = re.sub(r'"[^"]+"', ' ', search_text)
            raw_terms.extend(quoted_terms)
            raw_terms.extend(re.split(r'[,;/]+|\s+', unquoted_text))
        raw_terms.extend(keywords or [])

        terms = []
        for term in raw_terms:
            normalized = re.sub(r'[^A-Za-z0-9 +/#\'-]', ' ', term).strip().lower()
            normalized = re.sub(r'\s+', ' ', normalized)
            if normalized and normalized not in terms:
                terms.append(normalized)

        merged_terms = []
        index = 0
        mergeable_pairs = {
            ('double', 'strike'): 'double strike',
            ('first', 'strike'): 'first strike',
            ('life', 'gain'): 'life gain',
            ('card', 'draw'): 'card draw',
        }
        while index < len(terms):
            pair = tuple(terms[index:index + 2])
            if pair in mergeable_pairs:
                merged_terms.append(mergeable_pairs[pair])
                index += 2
                continue
            merged_terms.append(terms[index])
            index += 1

        return merged_terms[:6]

    def _build_random_commander_query(
        self,
        colors: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        max_cmc: Optional[int] = None,
        search_text: Optional[str] = None,
    ) -> str:
        """Build a budget-friendly Scryfall query for random commander discovery."""
        query_parts = ["is:commander", "t:creature", "f:commander"]

        if colors:
            normalized_colors = [color.upper() for color in colors]
            if 'C' in normalized_colors:
                query_parts.append("id:c")
            else:
                color_str = "".join(normalized_colors).lower()
                query_parts.append(f"id:{color_str}")

        if max_cmc:
            query_parts.append(f"cmc<={max_cmc}")

        keyword_abilities = {
            'flying', 'trample', 'haste', 'vigilance', 'lifelink',
            'deathtouch', 'hexproof', 'indestructible', 'first strike',
            'double strike', 'menace', 'reach', 'ward', 'proliferate',
            'cascade', 'connive', 'convoke', 'delve', 'escape', 'flashback',
            'landfall', 'magecraft', 'mutate', 'partner', 'prowess',
        }
        term_queries = {
            'artifact': '(t:artifact OR o:artifact OR otag:artifact)',
            'artifacts': '(t:artifact OR o:artifact OR otag:artifact)',
            'equipment': '(t:equipment OR o:equip OR o:equipped OR o:attach)',
            'voltron': '(t:equipment OR t:aura OR o:equip OR o:attach)',
            'aura': '(t:aura OR o:"enchanted creature")',
            'auras': '(t:aura OR o:"enchanted creature")',
            'enchantment': '(t:enchantment OR o:enchantment OR otag:enchantment)',
            'enchantments': '(t:enchantment OR o:enchantment OR otag:enchantment)',
            'graveyard': '(o:graveyard OR o:dies OR o:escape OR o:flashback OR otag:graveyard)',
            'recursion': '(o:"from your graveyard" OR o:"return target" OR otag:recursion)',
            'reanimator': '(o:reanimate OR o:"return target creature card" OR otag:reanimate)',
            'sacrifice': '(o:sacrifice OR o:dies OR otag:sacrifice)',
            'aristocrats': '(o:sacrifice OR o:dies OR o:"whenever another creature dies" OR otag:aristocrats)',
            'tokens': '(o:"creature token" OR o:"tokens you control" OR o:populate OR otag:tokens)',
            'token': '(o:"creature token" OR o:"tokens you control" OR o:populate OR otag:tokens)',
            'treasure': '(o:"Treasure token" OR otag:treasure)',
            'lifegain': '(o:"gain life" OR o:"whenever you gain life" OR otag:lifegain)',
            'life gain': '(o:"gain life" OR o:"whenever you gain life" OR otag:lifegain)',
            'counters': '(o:"+1/+1 counter" OR o:"-1/-1 counter" OR o:proliferate OR otag:counters)',
            'counter': '(o:"+1/+1 counter" OR o:"-1/-1 counter" OR o:proliferate OR otag:counters)',
            'spellslinger': '(o:"instant or sorcery" OR o:"whenever you cast" OR otag:spellslinger)',
            'instant': '(o:instant OR t:instant)',
            'sorcery': '(o:sorcery OR t:sorcery)',
            'blink': '(o:"exile another" OR o:"return it to the battlefield" OR otag:blink)',
            'flicker': '(o:"exile another" OR o:"return it to the battlefield" OR otag:blink)',
            'exile': '(o:"from exile" OR o:"play a card from exile" OR o:"exile the top" OR otag:exile)',
            'landfall': '(o:landfall OR o:"land enters" OR o:"land you control enters" OR kw:landfall)',
            'lands': '(o:landfall OR o:"additional land" OR o:"land you control enters")',
            'draw': '(o:"draw a card" OR o:"draw cards" OR otag:card-advantage)',
            'card draw': '(o:"draw a card" OR o:"draw cards" OR otag:card-advantage)',
            'mill': '(o:mill OR otag:mill)',
            'zombies': '(t:zombie OR o:zombie)',
            'zombie': '(t:zombie OR o:zombie)',
            'elves': '(t:elf OR o:elf)',
            'elf': '(t:elf OR o:elf)',
            'goblins': '(t:goblin OR o:goblin)',
            'goblin': '(t:goblin OR o:goblin)',
            'dragons': '(t:dragon OR o:dragon)',
            'dragon': '(t:dragon OR o:dragon)',
            'slivers': '(t:sliver OR o:sliver)',
            'sliver': '(t:sliver OR o:sliver)',
            'vampires': '(t:vampire OR o:vampire)',
            'vampire': '(t:vampire OR o:vampire)',
            'humans': '(t:human OR o:human)',
            'human': '(t:human OR o:human)',
        }

        translated_terms = []
        for term in self._parse_search_terms(search_text, keywords):
            if term in term_queries:
                translated_terms.append(term_queries[term])
            elif term in keyword_abilities:
                translated_terms.append(f"kw:{self._quote_scryfall_phrase(term)}")
            else:
                safe_term = self._quote_scryfall_phrase(term)
                translated_terms.append(f"(t:{safe_term} OR o:{safe_term})")

        if translated_terms:
            query_parts.append(" ".join(translated_terms))

        return " ".join(query_parts)

    async def get_random_commander(self, colors: Optional[List[str]] = None,
                                   keywords: Optional[List[str]] = None,
                                   max_cmc: Optional[int] = None,
                                   search_text: Optional[str] = None) -> Dict:
        """Get a random commander with filters"""
        query = self._build_random_commander_query(
            colors=colors,
            keywords=keywords,
            max_cmc=max_cmc,
            search_text=search_text,
        )
        
        try:
            results = await self.scryfall.search_cards_by_criteria(query, limit=100)
            results = [card for card in results if self._is_commander_eligible(card, creature_only=True)]
            if not results:
                # Fallback to any commander
                results = await self.scryfall.search_cards_by_criteria("is:commander t:creature f:commander", limit=100)
                results = [card for card in results if self._is_commander_eligible(card, creature_only=True)]
            
            # Pick random
            import random
            commander_card = random.choice(results) if results else None
            
            if commander_card:
                result = await self.analyze_commander(commander_card)
                result['search_query'] = query
                return result
            else:
                raise ValueError("No commanders found matching criteria")
        except Exception as e:
            logger.error(f"Random commander error: {str(e)}")
            raise
    
    async def get_replacement_suggestion(
        self, 
        deck: Dict, 
        dismissed_cards: List[str],
        role_tag: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Generate a single replacement suggestion, excluding dismissed cards.
        This is used when a user wants to see different suggestions.
        """
        cards = deck.get('cards', [])
        commander = deck.get('commander')
        color_identity = deck.get('color_identity', [])
        
        # Get commander constraints
        commander_data = None
        commander_synergies = []
        commander_constraints = {}
        if commander:
            commander_data = await self.scryfall.search_card(commander)
            if commander_data:
                commander_synergies = self._detect_commander_synergies(commander_data)
                commander_constraints = self._get_commander_constraints(commander_data)
        
        # Calculate stats and gaps
        stats = self._calculate_stats(cards, commander, commander_synergies)
        gaps = self._identify_gaps(stats, color_identity, commander_synergies)
        
        # Get current card names (including dismissed cards)
        current_card_names = {card['name'].lower() for card in cards}
        dismissed_card_names = {card.lower() for card in dismissed_cards}
        all_excluded_names = current_card_names | dismissed_card_names
        
        # Determine which role to search for
        search_roles = []
        if role_tag:
            search_roles = [role_tag]
        else:
            # Try roles in priority order
            if 'draw' in gaps['roles']:
                search_roles.append('draw')
            if 'ramp' in gaps['roles']:
                search_roles.append('ramp')
            if 'removal' in gaps['roles']:
                search_roles.append('removal')
            if commander_synergies:
                search_roles.append('synergy')
        
        # Search for a replacement
        for role in search_roles:
            query = self._build_query_for_role(role, color_identity, commander_synergies, commander_constraints)
            if not query:
                continue
            
            try:
                results = await self.scryfall.search_cards_by_criteria(query, limit=50)
                for card in results:
                    card_name = card.get('name', '').lower()
                    if card_name in all_excluded_names:
                        continue
                    
                    # Validate color identity
                    commander_colors = commander_constraints.get('commander_color_identity', color_identity)
                    if not self._is_legal_for_deck(card, commander_colors):
                        continue
                    
                    # Handle double-faced cards
                    card_to_validate = card
                    if card.get('card_faces') and len(card.get('card_faces', [])) > 1:
                        if commander_constraints.get('max_enchantment_cmc'):
                            card_to_validate = self._get_correct_face_for_validation(card, 'enchantment')
                        elif commander_constraints.get('max_tutor_cmc'):
                            if 'enchantment' in role:
                                card_to_validate = self._get_correct_face_for_validation(card, 'enchantment')
                            elif 'artifact' in role:
                                card_to_validate = self._get_correct_face_for_validation(card, 'artifact')
                            elif 'creature' in role:
                                card_to_validate = self._get_correct_face_for_validation(card, 'creature')
                    
                    extracted = self.scryfall.extract_card_data(card_to_validate)
                    effective_cmc = self._calculate_effective_cmc(card_to_validate)
                    
                    # Apply commander constraints
                    if commander_constraints:
                        if 'max_enchantment_cmc' in commander_constraints:
                            if 'enchantment' in extracted['type_line'].lower():
                                if effective_cmc > commander_constraints['max_enchantment_cmc']:
                                    continue
                        
                        if 'max_tutor_cmc' in commander_constraints:
                            if effective_cmc > commander_constraints['max_tutor_cmc']:
                                continue
                        
                        if commander_constraints.get('legendary_only'):
                            if 'legendary' not in extracted['type_line'].lower():
                                continue
                        
                        if 'max_power' in commander_constraints:
                            card_power = card_to_validate.get('power')
                            if card_power and card_power.isdigit():
                                if int(card_power) > commander_constraints['max_power']:
                                    continue
                    
                    # Found a valid replacement!
                    price = self._extract_price(extracted['prices'])
                    image_data = self._get_card_images(card)
                    reason = self._generate_card_reasoning(
                        extracted, role, commander, commander_synergies, gaps, commander_constraints
                    )
                    
                    return {
                        'card_name': extracted['name'],
                        'reason': reason,
                        'role_tag': role,
                        'cmc': effective_cmc,
                        'price': price,
                        'synergy_tags': self._detect_card_synergies(
                            extracted['oracle_text'].lower(),
                            extracted['type_line'].lower()
                        ),
                        'confidence': 0.9 if role == 'synergy' else 0.8,
                        'image_url': image_data['front'],
                        'image_url_back': image_data['back']
                    }
            except Exception as e:
                logger.error(f"Error finding replacement for {role}: {str(e)}")
                continue
        
        # No replacement found
        return None
    
    def _build_query_for_role(
        self, 
        role: str, 
        color_identity: List[str],
        commander_synergies: List[str],
        commander_constraints: Dict
    ) -> Optional[str]:
        """Build Scryfall query for a specific role"""
        color_query = self._color_identity_filter(color_identity)
        
        if role == 'draw':
            return f"o:draw {color_query} f:commander"
        elif role == 'ramp':
            return f"(o:search o:land OR o:treasure OR t:mana) {color_query} f:commander"
        elif role == 'removal':
            return f"(o:destroy o:target OR o:exile o:target) {color_query} f:commander"
        elif role == 'sweeper':
            return f"(o:destroy o:all OR o:exile o:all OR o:-x/-x) {color_query} f:commander"
        elif role == 'interaction':
            return f"o:counter {color_query} f:commander"
        elif role == 'protection':
            return f"(o:protection OR o:hexproof OR o:indestructible) {color_query} f:commander"
        elif role == 'synergy':
            for synergy in commander_synergies:
                query = self._build_query_for_synergy(synergy, color_identity, commander_constraints)
                if query:
                    return query
        
        return None
    
    def export_to_markdown(self, deck: Dict, analysis: Dict) -> str:
        """Export analysis to Markdown format"""
        lines = []
        
        lines.append(f"# Commander Deck Analysis: {deck.get('name', 'Unnamed Deck')}")
        lines.append("")
        lines.append(f"**Commander:** {deck.get('commander', 'N/A')}")
        lines.append(f"**Format:** Commander (EDH)")
        lines.append(f"**Color Identity:** {', '.join(deck.get('color_identity', []))}")
        lines.append("")
        
        stats = analysis.get('stats', {})
        lines.append("## Deck Statistics")
        lines.append("")
        lines.append(f"- Total Cards: {stats.get('total_cards', 0)}")
        lines.append(f"- Lands: {stats.get('total_lands', 0)}")
        lines.append(f"- Average CMC: {stats.get('avg_cmc', 0)}")
        lines.append(f"- Commander Synergy Score: {stats.get('synergy_score', 0)}")
        lines.append("")
        
        lines.append("### CMC Distribution")
        lines.append("")
        cmc_dist = stats.get('cmc_distribution', {})
        for bracket in ['0-1', '2', '3', '4', '5', '6+']:
            count = cmc_dist.get(bracket, 0)
            lines.append(f"- CMC {bracket}: {count} cards")
        lines.append("")
        
        lines.append("### Role Distribution")
        lines.append("")
        role_counts = stats.get('role_counts', {})
        for role, count in role_counts.items():
            lines.append(f"- {role.capitalize()}: {count} cards")
        lines.append("")
        
        # Suggestions
        lines.append("## Suggested Additions (10 Cards)")
        lines.append("")
        lines.append("| Card Name | Role | CMC | Price | Reason |")
        lines.append("|-----------|------|-----|-------|--------|")
        
        for sugg in analysis.get('suggestions_add', [])[:10]:
            price_str = f"${sugg.get('price', 0):.2f}" if sugg.get('price') else "N/A"
            lines.append(f"| {sugg['card_name']} | {sugg['role_tag']} | {sugg['cmc']} | {price_str} | {sugg['reason']} |")
        
        lines.append("")
        lines.append("## Suggested Cuts (10 Cards)")
        lines.append("")
        lines.append("| Card Name | Role | CMC | Reason |")
        lines.append("|-----------|------|-----|--------|")
        
        for sugg in analysis.get('suggestions_cut', [])[:10]:
            lines.append(f"| {sugg['card_name']} | {sugg['role_tag']} | {sugg['cmc']} | {sugg['reason']} |")
        
        lines.append("")
        lines.append("---")
        lines.append("*Generated by LandFall AI - Enhanced Suggestion Engine*")
        
        return "\n".join(lines)
