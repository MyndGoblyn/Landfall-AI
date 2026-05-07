from typing import Dict, List, Optional
import logging
from collections import Counter, defaultdict
from services.scryfall_service import ScryfallService

logger = logging.getLogger(__name__)

class SuggestionEngine:
    """Deterministic Commander deck suggestion engine - NO LLM"""
    
    def __init__(self, scryfall_service: ScryfallService):
        self.scryfall = scryfall_service
        
        # Role targets
        self.role_targets = {
            'draw': (8, 12),
            'ramp': (8, 12),
            'removal': (5, 8),
            'sweeper': (2, 4),
            'interaction': (3, 6),
            'wincon': (3, 6)
        }
        
        # CMC distribution targets
        self.cmc_targets = {
            '0-1': 8,
            '2': 12,
            '3': 10,
            '4': 8,
            '5': 6,
            '6+': 6
        }
    
    async def analyze_deck(self, deck: Dict) -> Dict:
        """Main analysis entry point"""
        cards = deck.get('cards', [])
        commander = deck.get('commander')
        color_identity = deck.get('color_identity', [])
        
        # Calculate deck statistics
        stats = self._calculate_stats(cards, commander)
        
        # Identify gaps and issues
        gaps = self._identify_gaps(stats, color_identity)
        
        # Generate suggestions
        suggestions_add = await self._generate_additions(gaps, commander, color_identity, cards)
        suggestions_cut = self._generate_cuts(cards, gaps, stats)
        
        return {
            'suggestions_add': suggestions_add[:10],
            'suggestions_cut': suggestions_cut[:10],
            'stats': stats
        }
    
    def _calculate_stats(self, cards: List[Dict], commander: Optional[str]) -> Dict:
        """Calculate deck statistics - accounting for card quantities"""
        stats = {
            'total_cards': 0,
            'lands': 0,
            'nonlands': 0,
            'avg_cmc': 0,
            'cmc_distribution': defaultdict(int),
            'color_distribution': defaultdict(int),
            'role_counts': defaultdict(int),
            'etb_tapped_lands': 0,
            'total_lands': 0,
            'synergy_tags': defaultdict(int)
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
            
            # Count lands (multiply by quantity)
            if 'Land' in type_line:
                stats['lands'] += qty
                stats['total_lands'] += qty
                
                # Check ETB tapped
                if 'enters the battlefield tapped' in oracle_text or 'enters tapped' in oracle_text:
                    stats['etb_tapped_lands'] += qty
            else:
                stats['nonlands'] += qty
                total_cmc += cmc * qty
                cmc_count += qty
            
            # CMC distribution (multiply by quantity)
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
            
            # Color distribution (multiply by quantity)
            for color in colors:
                stats['color_distribution'][color] += qty
            
            # Role detection
            roles = self._detect_roles(oracle_text, type_line, card_name)
            for role in roles:
                stats['role_counts'][role] += 1
            
            # Synergy tags
            for tag in tags:
                stats['synergy_tags'][tag] += 1
        
        # Average CMC
        if cmc_count > 0:
            stats['avg_cmc'] = round(total_cmc / cmc_count, 2)
        
        return stats
    
    def _detect_roles(self, oracle_text: str, type_line: str, card_name: str) -> List[str]:
        """Detect card roles from oracle text"""
        roles = []
        
        # Draw
        if any(word in oracle_text for word in ['draw', 'draws', 'look at the top']):
            roles.append('draw')
        
        # Ramp
        if any(word in oracle_text for word in ['search your library for', 'add', 'mana', 'treasure', 'ramp']):
            if 'land' in oracle_text or 'mana' in oracle_text:
                roles.append('ramp')
        
        # Removal
        if any(word in oracle_text for word in ['destroy target', 'exile target', 'remove']):
            roles.append('removal')
        
        # Sweeper
        if any(word in oracle_text for word in ['destroy all', 'exile all', 'each creature']):
            roles.append('sweeper')
        
        # Interaction
        if any(word in oracle_text for word in ['counter', 'prevent', 'protection']):
            roles.append('interaction')
        
        # Wincon (simplified detection)
        if any(word in oracle_text for word in ['win the game', 'lose the game', 'damage to each opponent']):
            roles.append('wincon')
        
        return roles
    
    def _identify_gaps(self, stats: Dict, color_identity: List[str]) -> Dict:
        """Identify deck weaknesses and gaps"""
        gaps = {
            'roles': {},
            'cmc': {},
            'lands': {},
            'colors': []
        }
        
        # Role gaps
        for role, (min_target, max_target) in self.role_targets.items():
            current = stats['role_counts'].get(role, 0)
            if current < min_target:
                gaps['roles'][role] = min_target - current
        
        # CMC gaps
        for bracket, target in self.cmc_targets.items():
            current = stats['cmc_distribution'].get(bracket, 0)
            if current < target:
                gaps['cmc'][bracket] = target - current
        
        # Land count
        if stats['total_lands'] < 36:
            gaps['lands']['count'] = 36 - stats['total_lands']
        
        # ETB tapped ratio
        if stats['total_lands'] > 0:
            tapped_ratio = stats['etb_tapped_lands'] / stats['total_lands']
            if tapped_ratio > 0.3:
                gaps['lands']['too_many_tapped'] = True
        
        return gaps
    
    async def _generate_additions(self, gaps: Dict, commander: Optional[str], 
                                   color_identity: List[str], current_cards: List[Dict]) -> List[Dict]:
        """Generate card addition suggestions"""
        suggestions = []
        current_card_names = {card['name'].lower() for card in current_cards}
        
        # Build search queries based on gaps
        queries = []
        
        # Role-based additions
        if 'draw' in gaps['roles']:
            queries.append(('draw', f"o:draw c:{self._colors_to_query(color_identity)} f:commander", 
                           f"Increases card draw to reach {self.role_targets['draw'][0]}-{self.role_targets['draw'][1]} sources"))
        
        if 'ramp' in gaps['roles']:
            queries.append(('ramp', f"o:search o:land c:{self._colors_to_query(color_identity)} f:commander",
                           f"Increases ramp to reach {self.role_targets['ramp'][0]}-{self.role_targets['ramp'][1]} sources"))
        
        if 'removal' in gaps['roles']:
            queries.append(('removal', f"o:destroy o:target c:{self._colors_to_query(color_identity)} f:commander",
                           f"Adds removal to reach {self.role_targets['removal'][0]}-{self.role_targets['removal'][1]} pieces"))
        
        if 'interaction' in gaps['roles']:
            queries.append(('interaction', f"o:counter c:{self._colors_to_query(color_identity)} f:commander",
                           f"Adds interaction/protection to reach {self.role_targets['interaction'][0]}-{self.role_targets['interaction'][1]} pieces"))
        
        # Execute searches
        for role, query, reason_template in queries:
            try:
                results = await self.scryfall.search_cards_by_criteria(query, limit=15)
                for card in results:
                    card_name = card.get('name', '').lower()
                    if card_name in current_card_names:
                        continue
                    
                    extracted = self.scryfall.extract_card_data(card)
                    price = self._extract_price(extracted['prices'])
                    
                    suggestion = {
                        'card_name': extracted['name'],
                        'reason': reason_template,
                        'role_tag': role,
                        'cmc': extracted['cmc'],
                        'price': price,
                        'synergy_tags': [],
                        'confidence': 0.8
                    }
                    suggestions.append(suggestion)
                    
                    if len(suggestions) >= 10:
                        break
                
                if len(suggestions) >= 10:
                    break
            except Exception as e:
                logger.error(f"Error generating additions for {role}: {str(e)}")
        
        return suggestions
    
    def _generate_cuts(self, cards: List[Dict], gaps: Dict, stats: Dict) -> List[Dict]:
        """Generate card cut suggestions"""
        suggestions = []
        
        # Prioritize cuts:
        # 1. High CMC cards (6+) if we have too many
        # 2. Cards with weak synergy
        # 3. ETB tapped lands if ratio is too high
        
        high_cmc_cards = [c for c in cards if c.get('cmc', 0) >= 6 and 'Land' not in c.get('type_line', '')]
        
        # Sort by CMC descending
        high_cmc_cards.sort(key=lambda x: x.get('cmc', 0), reverse=True)
        
        for card in high_cmc_cards[:5]:
            suggestions.append({
                'card_name': card['name'],
                'reason': f"High CMC ({card.get('cmc', 0)}) creates curve imbalance. Consider lower-cost alternatives.",
                'role_tag': 'curve_balance',
                'cmc': card.get('cmc', 0),
                'price': 0,
                'synergy_tags': card.get('tags', []),
                'confidence': 0.7
            })
        
        # Cut ETB tapped lands if too many
        if gaps.get('lands', {}).get('too_many_tapped'):
            tapped_lands = [c for c in cards if 'Land' in c.get('type_line', '') 
                           and 'enters the battlefield tapped' in c.get('oracle_text', '').lower()]
            
            for card in tapped_lands[:3]:
                suggestions.append({
                    'card_name': card['name'],
                    'reason': "ETB tapped lands slow down the deck. Replace with untapped alternatives.",
                    'role_tag': 'mana_base',
                    'cmc': 0,
                    'price': 0,
                    'synergy_tags': [],
                    'confidence': 0.8
                })
        
        # Add generic cuts to reach 10
        if len(suggestions) < 10:
            remaining_cards = [c for c in cards if c['name'] not in [s['card_name'] for s in suggestions]]
            for card in remaining_cards[:(10 - len(suggestions))]:
                suggestions.append({
                    'card_name': card['name'],
                    'reason': "Consider replacing with cards that better support your deck's strategy.",
                    'role_tag': 'optimization',
                    'cmc': card.get('cmc', 0),
                    'price': 0,
                    'synergy_tags': card.get('tags', []),
                    'confidence': 0.5
                })
        
        return suggestions[:10]
    
    def _colors_to_query(self, color_identity: List[str]) -> str:
        """Convert color identity to Scryfall query format"""
        if not color_identity:
            return "c:c"  # Colorless
        return "".join(color_identity).lower()
    
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
    
    def export_to_markdown(self, deck: Dict, analysis: Dict) -> str:
        """Export analysis to Markdown format"""
        lines = []
        
        lines.append(f"# Commander Deck Analysis: {deck.get('name', 'Unnamed Deck')}")
        lines.append("")
        lines.append(f"**Commander:** {deck.get('commander', 'N/A')}")
        lines.append("**Format:** Commander (EDH)")
        lines.append(f"**Color Identity:** {', '.join(deck.get('color_identity', []))}")
        lines.append("")
        
        stats = analysis.get('stats', {})
        lines.append("## Deck Statistics")
        lines.append("")
        lines.append(f"- Total Cards: {stats.get('total_cards', 0)}")
        lines.append(f"- Lands: {stats.get('total_lands', 0)}")
        lines.append(f"- Average CMC: {stats.get('avg_cmc', 0)}")
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
        lines.append("*Generated by LandFall AI*")
        
        return "\n".join(lines)
