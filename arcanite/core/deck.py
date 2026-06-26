"""
Arcanite Deck Implementations

Concrete implementations of the Deck protocol for different card systems.
"""

import json
import random
import secrets
from pathlib import Path
from typing import Any

from arcanite.core.models import DeckConfig, DrawnCard, Orientation


class TarotCard:
    """
    A tarot card loaded from JSON.

    Implements the Card protocol with full access to position interpretations,
    question contexts, and card relationships.
    """

    def __init__(self, data: dict[str, Any], image_filename: str):
        self._data = data
        self._image_filename = image_filename

    @property
    def card_id(self) -> str:
        return self._data.get("card_id") or self._data.get("id", "unknown")

    @property
    def card_name(self) -> str:
        return self._data.get("card_name") or self._data.get("name", "Unknown")

    @property
    def card_number(self) -> int:
        return self._data.get("card_number", 0)

    @property
    def suit(self) -> str:
        return self._data.get("suit", "major_arcana")

    @property
    def archetype(self) -> str:
        return self._data.get("archetype", "")

    @property
    def image_filename(self) -> str:
        return self._image_filename

    def get_interpretation(
        self,
        rag_mapping: str,
        reversed: bool = False,
    ) -> dict[str, Any]:
        """
        Navigate to the interpretation using the RAG mapping path.

        Args:
            rag_mapping: Dot-notation path like 'temporal_positions.past'
            reversed: Whether to get reversed interpretation

        Returns:
            Dict with interpretation data including text, keywords, etc.
        """
        # Navigate the path
        position_interps = self._data.get("position_interpretations", {})
        current = position_interps

        parts = rag_mapping.split(".")
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # Fallback to core meanings if path not found
                return self._get_core_meaning_fallback(reversed)

        # current should now be a dict with 'upright', 'reversed', 'keywords'
        if isinstance(current, dict):
            orientation_key = "reversed" if reversed else "upright"
            return {
                "interpretation": current.get(orientation_key, ""),
                "keywords": current.get("keywords", []),
                "raw": current,
            }

        return self._get_core_meaning_fallback(reversed)

    def _get_core_meaning_fallback(self, reversed: bool) -> dict[str, Any]:
        """Fallback to core meanings if RAG path not found."""
        core = self._data.get("core_meanings", {})
        orientation_key = "reversed" if reversed else "upright"
        meaning = core.get(orientation_key, {})
        return {
            "interpretation": meaning.get("essence", ""),
            "keywords": meaning.get("keywords", []),
            "raw": meaning,
        }

    def get_question_context(
        self,
        question_type: str,
        reversed: bool = False,
    ) -> dict[str, Any]:
        """Get question-specific interpretation."""
        contexts = self._data.get("question_contexts", {})
        context = contexts.get(question_type, {})

        orientation_key = "reversed" if reversed else "upright"
        return {
            "interpretation": context.get(orientation_key, ""),
            "keywords": context.get("keywords", []),
            "raw": context,
        }

    def get_core_meaning(self, reversed: bool = False) -> dict[str, Any]:
        """Get the core meaning (essence, keywords, etc.)."""
        core = self._data.get("core_meanings", {})
        orientation_key = "reversed" if reversed else "upright"
        return core.get(orientation_key, {})

    def get_relationships(self) -> dict[str, dict[str, Any]]:
        """Get card relationship data."""
        return self._data.get("card_relationships", {})

    def get_elemental_correspondences(self) -> dict[str, Any]:
        """Get elemental and astrological correspondences."""
        return self._data.get("elemental_correspondences", {})

    def get_symbols(self) -> dict[str, str]:
        """Get symbol interpretations."""
        return self._data.get("symbols", {})

    def get_affirmations(self) -> list[str]:
        """Get card affirmations."""
        return self._data.get("affirmations", [])

    def get_journaling_prompts(self) -> list[str]:
        """Get journaling prompts."""
        return self._data.get("journaling_prompts", [])

    @property
    def description(self) -> dict[str, str]:
        """Get card descriptions: waite (original), tk_en, tk_zh."""
        return self._data.get("description", {})

    @property
    def reading_aspects(self) -> dict[str, Any]:
        """5 reading aspects: currentSituation, innerState, rootCause, development, advice.
        Each aspect has upright/reversed with en/zh text."""
        return self._data.get("reading_aspects", {})

    @property
    def contextual_meanings(self) -> dict[str, Any]:
        """4 contextual meanings: love, work, interpersonal, others.
        Each has upright/reversed with en/zh text."""
        return self._data.get("contextual_meanings", {})

    def get_tk_meaning(self, orientation: str = "upright", lang: str = "en") -> str:
        """Get TarotKit meaning text.
        Args:
            orientation: 'upright' or 'reversed'
            lang: 'en' or 'zh'
        """
        cm = self._data.get("core_meanings", {}).get(orientation, {})
        return cm.get(f"tk_meaning_{lang}", "")

    def get_waite_meaning(self, orientation: str = "upright") -> str:
        """Get Waite original meaning text."""
        cm = self._data.get("core_meanings", {}).get(orientation, {})
        return cm.get("waite_meaning", "")

    @property
    def raw_data(self) -> dict[str, Any]:
        return self._data

    def __repr__(self) -> str:
        return f"TarotCard({self.card_name!r})"


class TarotDeck:
    """
    A complete tarot deck loaded from JSON files.

    Implements the Deck protocol with shuffling and drawing capabilities.
    """

    def __init__(
        self,
        cards: list[TarotCard],
        image_path: Path,
        image_format: str = "jpg",
    ):
        self._cards = cards
        self._image_path = image_path
        self._image_format = image_format
        self._card_by_id = {card.card_id: card for card in cards}

    @classmethod
    def load(
        cls,
        card_data_path: Path | str | None = None,
        image_path: Path | str | None = None,
        image_format: str = "jpg",
        package_root: Path | str | None = None,
        system: str = "tarot",
    ) -> "TarotDeck":
        """
        Load a tarot deck from JSON files.

        Args:
            card_data_path: Path to directory containing card JSON files
            image_path: Path to directory containing card images
            image_format: Image file extension (default: 'jpg')
            package_root: Root path of the arcanite package (for finding bundled data)
            system: Card system subdirectory (default: 'tarot')

        Returns:
            A loaded TarotDeck instance
        """
        # Determine paths
        if package_root is None:
            # Default to the package's own data
            package_root = Path(__file__).parent.parent

        if card_data_path is None:
            card_data_path = package_root / "cards" / "json" / system
        else:
            card_data_path = Path(card_data_path)

        if image_path is None:
            image_path = package_root / "images" / "cards_github"
        else:
            image_path = Path(image_path)

        # Load all card JSON files
        cards = []
        for json_file in sorted(card_data_path.glob("*.json")):
            with open(json_file) as f:
                data = json.load(f)

            # Derive image filename from JSON filename
            image_filename = f"{json_file.stem}.{image_format}"
            if system == "lenormand":
                cards.append(LenormandCard(data, image_filename))
            else:
                cards.append(TarotCard(data, image_filename))

        return cls(cards, image_path, image_format)

    @classmethod
    def from_config(cls, config: DeckConfig, package_root: Path | str | None = None) -> "TarotDeck":
        """Load a deck from a DeckConfig."""
        return cls.load(
            card_data_path=config.card_data_path,
            image_path=config.image_path,
            image_format=config.image_format,
            package_root=package_root,
        )

    @property
    def cards(self) -> list[TarotCard]:
        return self._cards

    @property
    def image_path(self) -> Path:
        return self._image_path

    def get_card(self, card_id: str) -> TarotCard:
        """Get a card by its ID."""
        if card_id not in self._card_by_id:
            raise KeyError(f"Card not found: {card_id}")
        return self._card_by_id[card_id]

    def get_image_path(self, card: TarotCard) -> Path:
        """Get the full path to a card's image file."""
        return self._image_path / card.image_filename

    def shuffle(self, seed: int | None = None) -> list[TarotCard]:
        """
        Return a shuffled copy of the deck.

        Args:
            seed: Optional seed for reproducible shuffles

        Returns:
            New list with cards in shuffled order
        """
        cards = list(self._cards)
        rng = secrets.SystemRandom() if seed is None else random.Random(seed)
        rng.shuffle(cards)
        return cards

    def draw(
        self,
        count: int,
        seed: int | None = None,
        allow_reversals: bool = True,
    ) -> list[DrawnCard]:
        """
        Draw cards from the deck.

        Args:
            count: Number of cards to draw
            seed: Optional seed for reproducibility
            allow_reversals: Whether cards can be reversed

        Returns:
            List of DrawnCard with card info and orientation
        """
        if not isinstance(count, int) or count <= 0:
            raise ValueError(f"draw count must be a positive integer, got {count}")
        if count > len(self._cards):
            raise ValueError(f"Cannot draw {count} cards from a {len(self._cards)}-card deck")

        rng = secrets.SystemRandom() if seed is None else random.Random(seed)
        shuffled = list(self._cards)
        rng.shuffle(shuffled)

        drawn = []
        for i, card in enumerate(shuffled[:count]):
            # Determine orientation
            if allow_reversals:
                is_reversed = rng.random() < 0.5
                orientation = Orientation.REVERSED if is_reversed else Orientation.UPRIGHT
            else:
                orientation = Orientation.UPRIGHT

            dc = DrawnCard(
                card_id=card.card_id,
                card_name=card.card_name,
                position_index=i,
                position_name="",  # Will be filled when assigned to spread
                orientation=orientation,
                image_path=self.get_image_path(card),
            )
            dc._attach_deck(self)
            drawn.append(dc)

        return drawn

    def __len__(self) -> int:
        return len(self._cards)

    def __repr__(self) -> str:
        return f"TarotDeck({len(self._cards)} cards)"


# Convenience function
def load_tarot_deck(
    card_data_path: Path | str | None = None,
    image_path: Path | str | None = None,
    image_format: str = "jpg",
    system: str = "tarot",
) -> TarotDeck:
    """
    Convenience function to load a tarot deck.

    Args:
        card_data_path: Path to card JSON files
        image_path: Path to card images
        image_format: Image file extension
        system: Card system subdirectory (default: 'tarot')

    Returns:
        Loaded TarotDeck
    """
    return TarotDeck.load(card_data_path, image_path, image_format, system=system)


# ── Lenormand support (CI patch) ──────────────────────────────────────────────

class LenormandCard:
    """A Lenormand card with semantic getters for all 10 data layers.

    Compatible with TarotDeck internals — provides card_id, card_name,
    image_filename, and raw_data exactly as TarotCard does, so TarotDeck's
    shuffle/draw/_card_by_id machinery works unchanged.
    """

    def __init__(self, data: dict[str, Any], image_filename: str):
        self._data = data
        self._image_filename = image_filename

    @property
    def card_id(self) -> str:
        # Handles both "card_id" and "id" keys (patch_arcanite_lenormand ensures this)
        return self._data.get("card_id") or self._data.get("id", "unknown")

    @property
    def card_name(self) -> str:
        # Handles both "card_name" and "name" keys
        return self._data.get("card_name") or self._data.get("name", "Unknown")

    @property
    def image_filename(self) -> str:
        return self._image_filename

    @property
    def raw_data(self) -> dict[str, Any]:
        """Full raw card data (same interface as TarotCard)."""
        return self._data

    # ── 10 semantic getters for Lenormand data layers ──────────────────────

    def get_core(self) -> dict[str, Any]:
        """Core: keywords, charge (neutral/positive/negative), category, topics."""
        return self._data.get("core", {})

    def get_timing(self) -> dict[str, Any]:
        """Timing: thematic, duration, season, speed, direction."""
        return self._data.get("timing", {})

    def get_as_person(self) -> str:
        """Person description when card represents a person."""
        return self._data.get("as_person", "")

    def get_modifier_behavior(self) -> dict[str, Any]:
        """Modifier behavior: type (descriptor/amplifier/negator/connector/timing/obstacle/outcome),
        as_modifier, as_modified."""
        return self._data.get("modifier_behavior", {})

    def get_playing_card(self) -> str:
        """Corresponding standard playing card (e.g. '9 of Hearts')."""
        return self._data.get("playing_card", "")

    def get_topic_contexts(self) -> dict[str, str]:
        """Topic-specific interpretations: love, career, health, finances, spiritual."""
        return self._data.get("topic_contexts", {})

    def get_line_reading(self) -> dict[str, str]:
        """Line reading positions: as_first, as_middle, as_last."""
        return self._data.get("line_reading", {})

    def get_combination_grammar(self) -> dict[str, Any]:
        """Combination grammar: description, as_card_a, as_card_b (7 grammar types)."""
        return self._data.get("combination_grammar", {})

    def get_combinations(self) -> list[dict[str, Any]]:
        """Fixed card combinations (557 entries across 36 cards) with interpretations."""
        return self._data.get("combinations", [])

    def get_grand_tableau(self) -> dict[str, Any]:
        """Grand Tableau positions: as_house, near_significator, far_from_significator,
        diagonal_or_corner."""
        return self._data.get("grand_tableau", {})

    def get_combination_with(self, card_id: str, position: str | None = None) -> dict[str, Any]:
        """Find combination with another card by ID.

        Args:
            card_id: Target card ID (e.g. 'the_clover')
            position: 'left' (this card is Card A, left of target),
                      'right' (this card is Card B, right of target),
                      None (return raw entry with as_first/as_second)

        Returns:
            dict with interpretation or empty dict. Auto-falls back to
            combination_grammar when no preset combination exists.

        Raises:
            ValueError: if card_id is empty or whitespace-only
        """
        if not card_id or not card_id.strip():
            raise ValueError("card_id cannot be empty")
        for combo in self.get_combinations():
            if combo.get('with') == card_id:
                if position == 'left':
                    return {'interpretation': combo.get('as_first', ''),
                            'direction': 'A→B', 'source': 'preset'}
                elif position == 'right':
                    return {'interpretation': combo.get('as_second', ''),
                            'direction': 'B→A', 'source': 'preset'}
                return combo
        # Fallback to combination_grammar
        result = self._grammar_fallback(card_id, position)
        result['warning'] = f"No preset combination found for '{card_id}', using grammar fallback"
        return result

    def _grammar_fallback(self, card_id: str, position: str | None = None) -> dict[str, Any]:
        """Fallback to combination_grammar when no preset combination exists.

        Uses grammar rules (as_card_a, as_card_b, with_positive_card, etc.)
        to generate a structured interpretation.
        """
        grammar = self.get_combination_grammar()
        if not grammar:
            return {}
        if position == 'left':
            return {'interpretation': grammar.get('as_card_a', ''),
                    'direction': 'A→B', 'source': 'grammar'}
        elif position == 'right':
            return {'interpretation': grammar.get('as_card_b', ''),
                    'direction': 'B→A', 'source': 'grammar'}
        # No position specified — return the full grammar structure
        return {'interpretation': grammar.get('description', ''),
                'as_card_a': grammar.get('as_card_a', ''),
                'as_card_b': grammar.get('as_card_b', ''),
                'with_positive': grammar.get('with_positive_card', ''),
                'with_negative': grammar.get('with_negative_card', ''),
                'with_person': grammar.get('with_person_card', ''),
                'with_object': grammar.get('with_object_card', ''),
                'direction': 'unspecified', 'source': 'grammar'}

    def __repr__(self) -> str:
        return f"LenormandCard({self.card_name!r})"


class LenormandDrawnCard:
    """A drawn card that transparently proxies both DrawnCard fields and LenormandCard methods.

    Eliminates the two-step draw() -> get_card() dance. Access DrawnCard
    fields (card_id, card_name, orientation) and LenormandCard semantic
    methods (get_core(), get_combination_with(), etc.) from the SAME object.
    """

    def __init__(self, drawn: Any, card: Any):
        self._drawn = drawn
        self._card = card

    # ── DrawnCard fields (passthrough) ────────────────────────────────────
    @property
    def card_id(self) -> str:
        return self._drawn.card_id

    @property
    def card_name(self) -> str:
        return self._drawn.card_name

    @property
    def orientation(self):
        return self._drawn.orientation

    @property
    def position_index(self) -> int:
        return self._drawn.position_index

    @property
    def position_name(self) -> str:
        return self._drawn.position_name

    @property
    def image_path(self):
        return self._drawn.image_path

    # ── LenormandCard methods (proxy) ─────────────────────────────────────
    def get_core(self) -> dict[str, Any]:
        return self._card.get_core()

    def get_timing(self) -> dict[str, Any]:
        return self._card.get_timing()

    def get_as_person(self) -> str:
        return self._card.get_as_person()

    def get_modifier_behavior(self) -> dict[str, Any]:
        return self._card.get_modifier_behavior()

    def get_playing_card(self) -> str:
        return self._card.get_playing_card()

    def get_topic_contexts(self) -> dict[str, str]:
        return self._card.get_topic_contexts()

    def get_line_reading(self) -> dict[str, str]:
        return self._card.get_line_reading()

    def get_combination_grammar(self) -> dict[str, Any]:
        return self._card.get_combination_grammar()

    def get_combinations(self) -> list[dict[str, Any]]:
        return self._card.get_combinations()

    def get_grand_tableau(self) -> dict[str, Any]:
        return self._card.get_grand_tableau()

    def get_combination_with(self, card_id: str, position: str | None = None) -> dict[str, Any]:
        return self._card.get_combination_with(card_id, position)

    def __repr__(self) -> str:
        return f"LenormandDrawnCard({self.card_name!r}, {self.orientation.value})"


class LenormandDeck(TarotDeck):
    """Lenormand deck — reuses ALL TarotDeck shuffle/draw logic unchanged.

    The only difference from TarotDeck is the default system="lenormand".
    shuffle() → secrets.SystemRandom().shuffle() (hardware entropy)
    draw()    → same shuffling + 50% reversal chance
    """

    @classmethod
    def load(
        cls,
        card_data_path: Path | str | None = None,
        image_path: Path | str | None = None,
        image_format: str = "jpg",
        package_root: Path | str | None = None,
        system: str = "lenormand",
    ) -> "LenormandDeck":
        """Load a Lenormand deck (36 cards, 10 data layers)."""
        return super().load(
            card_data_path, image_path, image_format, package_root, system=system
        )

    def draw_with_data(
        self,
        count: int,
        seed: int | None = None,
        allow_reversals: bool = True,
    ) -> list[Any]:
        """Draw cards AND return LenormandDrawnCard objects in one call.

        Each returned object transparently proxies BOTH DrawnCard fields
        (card_id, card_name, orientation) AND LenormandCard semantic methods
        (get_core(), get_combination_with(), etc.). Zero two-step boilerplate.

        Raises:
            ValueError: if count <= 0
        """
        if not isinstance(count, int) or count <= 0:
            raise ValueError(f"draw count must be a positive integer, got {count}")
        drawn = self.draw(count, seed=seed, allow_reversals=allow_reversals)
        return [LenormandDrawnCard(d, self.get_card(d.card_id)) for d in drawn]

    def analyze_draw(self, drawn_cards: list[Any]) -> dict[str, Any]:
        """Analyze drawn cards for orientation patterns and statistics.

        Returns orientation distribution, all-upright/all-reversed detection,
        and card summary list.
        """
        if not drawn_cards:
            return {
                "count": 0,
                "upright_count": 0,
                "reversed_count": 0,
                "all_upright": False,
                "all_reversed": False,
                "pattern": "空抽牌",
                "cards": []
            }
        orientations = [c.orientation.value for c in drawn_cards]
        upright_count = orientations.count('upright')
        reversed_count = orientations.count('reversed')
        all_upright = upright_count == len(drawn_cards)
        all_reversed = reversed_count == len(drawn_cards)
        return {
            "count": len(drawn_cards),
            "upright_count": upright_count,
            "reversed_count": reversed_count,
            "all_upright": all_upright,
            "all_reversed": all_reversed,
            "pattern": "全正位" if all_upright else ("全逆位" if all_reversed else "混合"),
            "cards": [
                {"id": c.card_id, "name": c.card_name, "orientation": c.orientation.value}
                for c in drawn_cards
            ]
        }

    def __repr__(self) -> str:
        return f"LenormandDeck({len(self._cards)} cards)"


def load_lenormand_deck(
    card_data_path: Path | str | None = None,
    image_path: Path | str | None = None,
    image_format: str = "jpg",
) -> LenormandDeck:
    """Convenience function to load a Lenormand deck (36 cards).

    Returns a LenormandDeck with full shuffle/draw/spread support.
    """
    return LenormandDeck.load(card_data_path, image_path, image_format)
