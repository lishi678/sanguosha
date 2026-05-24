from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Callable


CARD_SHA = "\u6740"
CARD_SHAN = "\u95ea"
CARD_TAO = "\u6843"
CARD_WUZHONG = "\u65e0\u4e2d\u751f\u6709"
CARD_GUOHE = "\u8fc7\u6cb3\u62c6\u6865"
CARD_JUEDOU = "\u51b3\u6597"

ROLE_LORD = "Lord"
ROLE_LOYALIST = "Loyalist"
ROLE_REBEL = "Rebel"
ROLE_RENEGADE = "Renegade"


@dataclass(frozen=True)
class Card:
    name: str
    description: str
    color: str
    image: str = ""


@dataclass
class Hero:
    name: str
    title: str
    max_hp: int
    hp: int
    attack_bonus: int = 0
    color: str = "#d85c39"
    image: str = ""
    faction: str = "Qun"


@dataclass
class PlayerState:
    name: str
    hero: Hero
    role: str
    seat: int
    is_human: bool = False
    hand: list[Card] = field(default_factory=list)
    used_sha_this_turn: bool = False

    @property
    def alive(self) -> bool:
        return self.hero.hp > 0


class Game:
    def __init__(self, log: Callable[[str], None] | None = None):
        self.log = log or (lambda _message: None)
        self.rng = random.Random()
        self.deck: list[Card] = []
        self.discard: list[Card] = []
        self.players: list[PlayerState] = []
        self.current_index = 0
        self.winner: str | None = None
        self.round = 1
        self._build_deck()
        self._build_players()
        self.start()

    @property
    def player(self) -> PlayerState:
        return self.players[0]

    @property
    def current_player(self) -> PlayerState:
        return self.players[self.current_index]

    def start(self) -> None:
        self.log("Game started. Five-player identity mode is active.")
        self.log("Roles: Lord + Loyalist fight Rebels and Renegade. Rebels win by killing the Lord.")
        for player in self.players:
            self.draw(player, 4)
        self._start_turn(self.current_player)

    def _build_players(self) -> None:
        heroes = self._hero_pool()
        self.rng.shuffle(heroes)
        roles = [ROLE_LORD, ROLE_LOYALIST, ROLE_REBEL, ROLE_REBEL, ROLE_RENEGADE]
        names = ["You", "AI 1", "AI 2", "AI 3", "AI 4"]
        self.players = [
            PlayerState(names[i], heroes[i], roles[i], i + 1, is_human=(i == 0))
            for i in range(5)
        ]
        lord = self.players[0].hero
        lord.max_hp += 1
        lord.hp += 1

    @staticmethod
    def _hero_pool() -> list[Hero]:
        return [
            Hero("\u5218\u5907", "\u4ec1\u5fb7", 4, 4, color="#4f9a44", image="liu_bei.png", faction="\u8700"),
            Hero("\u5173\u7fbd", "\u6b66\u5723", 4, 4, attack_bonus=1, color="#4f9a44", image="guan_yu.png", faction="\u8700"),
            Hero("\u5f20\u98de", "\u5486\u54ee", 4, 4, color="#4f9a44", image="zhang_fei.png", faction="\u8700"),
            Hero("\u8d75\u4e91", "\u9f99\u80c6", 4, 4, color="#4f9a44", image="zhao_yun.png", faction="\u8700"),
            Hero("\u66f9\u64cd", "\u5978\u96c4", 4, 4, color="#4d72b8", image="cao_cao.png", faction="\u9b4f"),
            Hero("\u5b59\u6743", "\u5236\u8861", 4, 4, color="#2b9c73", image="sun_quan.png", faction="\u5434"),
        ]

    def _build_deck(self) -> None:
        cards = [
            (CARD_SHA, "Deal 1 damage. Target may play Dodge.", "#b74436", "sha.png", 22),
            (CARD_SHAN, "Automatically cancels one Strike.", "#4f9560", "shan.png", 18),
            (CARD_TAO, "Recover 1 HP.", "#d28a3d", "tao.png", 12),
            (CARD_WUZHONG, "Draw 2 cards.", "#7662a8", "wuzhong.png", 7),
            (CARD_GUOHE, "Discard one target hand card.", "#667487", "guohe.png", 7),
            (CARD_JUEDOU, "Duel until one side cannot play Strike.", "#a63c5b", "juedou.png", 5),
        ]
        self.deck = [
            Card(name, description, color, image)
            for name, description, color, image, amount in cards
            for _ in range(amount)
        ]
        self.rng.shuffle(self.deck)

    def draw(self, target: PlayerState, amount: int) -> None:
        drawn = 0
        for _ in range(amount):
            if not self.deck:
                self.deck = self.discard
                self.discard = []
                self.rng.shuffle(self.deck)
                self.log("Discard pile was shuffled back into the deck.")
            if self.deck:
                target.hand.append(self.deck.pop())
                drawn += 1
        self.log(f"{target.name} draws {drawn} card{'s' if drawn != 1 else ''}.")

    def play_player_card(self, index: int, target_seat: int | None = None) -> bool:
        user = self.player
        if self.current_player is not user or self.winner or not user.alive:
            return False
        if index < 0 or index >= len(user.hand):
            return False

        card = user.hand[index]
        if card.name == CARD_SHAN:
            self.log("Dodge is a reaction card and is used automatically.")
            return False
        if card.name == CARD_SHA and user.used_sha_this_turn:
            self.log("You can actively play only one Strike each turn.")
            return False

        target = self._target_by_seat(target_seat) if target_seat is not None else self._choose_target(user, card)
        if self._needs_target(card) and target is None:
            self.log("No valid target is available.")
            return False
        if target and not self.is_valid_target(user, card, target):
            self.log("That target is not valid for this card.")
            return False

        user.hand.pop(index)
        self._resolve_card(user, target, card)
        self.discard.append(card)
        self._check_game_over()
        return True

    def valid_targets_for_player_card(self, index: int) -> list[PlayerState]:
        if index < 0 or index >= len(self.player.hand):
            return []
        card = self.player.hand[index]
        if card.name == CARD_SHAN:
            return []
        if card.name == CARD_SHA and self.player.used_sha_this_turn:
            return []
        return [p for p in self.players if self.is_valid_target(self.player, card, p)]

    def is_valid_target(self, user: PlayerState, card: Card, target: PlayerState) -> bool:
        if not target.alive:
            return False
        if card.name == CARD_TAO:
            return target is user or target.hero.hp < target.hero.max_hp
        if card.name in {CARD_SHA, CARD_GUOHE, CARD_JUEDOU}:
            if target is user:
                return False
            if card.name == CARD_GUOHE:
                return bool(target.hand)
            return True
        return target is user

    def end_player_turn(self) -> None:
        if self.winner:
            return
        self.log("You end your turn.")
        self._advance_to_next_turn()

    def run_current_ai_turn(self) -> None:
        if self.winner or self.current_player.is_human:
            return
        actor = self.current_player
        self._computer_play_turn(actor)
        if not self._check_game_over():
            self._advance_to_next_turn()

    def _advance_to_next_turn(self) -> None:
        self._advance_index()
        if self._check_game_over():
            return
        self._start_turn(self.current_player)

    def _advance_index(self) -> None:
        while True:
            self.current_index = (self.current_index + 1) % len(self.players)
            if self.current_index == 0:
                self.round += 1
            if self.current_player.alive:
                return

    def _start_turn(self, actor: PlayerState) -> None:
        actor.used_sha_this_turn = False
        self.log(f"{actor.name}'s turn begins.")
        self.draw(actor, 2)

    def _computer_play_turn(self, actor: PlayerState) -> None:
        self.log(f"{actor.name} starts acting.")
        for _ in range(3):
            if self._check_game_over() or not actor.alive:
                return
            card_index = self._choose_computer_card(actor)
            if card_index is None:
                break
            card = actor.hand[card_index]
            target = self._choose_target(actor, card)
            if self._needs_target(card) and target is None:
                break
            actor.hand.pop(card_index)
            self._resolve_card(actor, target, card)
            self.discard.append(card)
        self.log(f"{actor.name} ends the turn.")

    def _choose_computer_card(self, actor: PlayerState) -> int | None:
        hand = actor.hand
        if actor.hero.hp < actor.hero.max_hp:
            index = self._find_index(hand, CARD_TAO)
            if index is not None:
                return index
        index = self._find_index(hand, CARD_WUZHONG)
        if index is not None:
            return index
        if self._choose_target(actor, Card(CARD_GUOHE, "", "", "")):
            index = self._find_index(hand, CARD_GUOHE)
            if index is not None:
                return index
        if self._choose_target(actor, Card(CARD_JUEDOU, "", "", "")):
            index = self._find_index(hand, CARD_JUEDOU)
            if index is not None:
                return index
        if not actor.used_sha_this_turn and self._choose_target(actor, Card(CARD_SHA, "", "", "")):
            index = self._find_index(hand, CARD_SHA)
            if index is not None:
                return index
        return None

    def _resolve_card(self, user: PlayerState, target: PlayerState | None, card: Card) -> None:
        if target and target is not user:
            self.log(f"{user.name} plays [{self._card_label(card.name)}] on {target.name}.")
        else:
            self.log(f"{user.name} plays [{self._card_label(card.name)}].")
        if card.name == CARD_SHA and target:
            user.used_sha_this_turn = True
            if self._remove_card_by_name(target, CARD_SHAN):
                self.log(f"{target.name} responds with [Dodge].")
                self.discard.append(Card(CARD_SHAN, "Automatically cancels one Strike.", "#4f9560", "shan.png"))
            else:
                self._damage(target, 1 + user.hero.attack_bonus, user)
        elif card.name == CARD_TAO:
            heal_target = target or user
            if heal_target.hero.hp < heal_target.hero.max_hp:
                heal_target.hero.hp += 1
                self.log(f"{heal_target.name} recovers 1 HP.")
            else:
                self.log(f"{heal_target.name} is already at full HP.")
        elif card.name == CARD_WUZHONG:
            self.draw(user, 2)
        elif card.name == CARD_GUOHE and target:
            if target.hand:
                removed = target.hand.pop(self.rng.randrange(len(target.hand)))
                self.discard.append(removed)
                self.log(f"{target.name} loses 1 random hand card to Dismantle.")
            else:
                self.log(f"{target.name} has no hand cards.")
        elif card.name == CARD_JUEDOU and target:
            self._duel(user, target)

    def _duel(self, first: PlayerState, second: PlayerState) -> None:
        actor, opponent = second, first
        while True:
            if self._remove_card_by_name(actor, CARD_SHA):
                self.discard.append(Card(CARD_SHA, "Deal 1 damage.", "#b74436", "sha.png"))
                self.log(f"{actor.name} answers the Duel with [Strike].")
                actor, opponent = opponent, actor
            else:
                self.log(f"{actor.name} fails the Duel.")
                self._damage(actor, 1, opponent)
                break

    def _damage(self, target: PlayerState, amount: int, source: PlayerState | None) -> None:
        target.hero.hp = max(0, target.hero.hp - amount)
        self.log(f"{target.name} takes {amount} damage.")
        if target.hero.hp <= 0:
            self.log(f"{target.name} is defeated. Role revealed: {target.role}.")
            if target.role == ROLE_REBEL and source and source.alive:
                self.draw(source, 3)
                self.log(f"{source.name} draws 3 reward cards for defeating a Rebel.")
            self._check_game_over()

    def _choose_target(self, actor: PlayerState, card: Card) -> PlayerState | None:
        if not self._needs_target(card):
            return actor
        candidates = [p for p in self.players if p.alive and p is not actor]
        if not candidates:
            return None
        enemies = [p for p in candidates if self._is_enemy(actor, p)]
        pool = enemies or candidates
        if card.name == CARD_GUOHE:
            with_cards = [p for p in pool if p.hand]
            if with_cards:
                pool = with_cards
        return min(pool, key=lambda p: (p.hero.hp, -len(p.hand)))

    def _target_by_seat(self, seat: int | None) -> PlayerState | None:
        if seat is None:
            return None
        for player in self.players:
            if player.seat == seat:
                return player
        return None

    def _is_enemy(self, actor: PlayerState, target: PlayerState) -> bool:
        if actor.role in (ROLE_LORD, ROLE_LOYALIST):
            return target.role in (ROLE_REBEL, ROLE_RENEGADE)
        if actor.role == ROLE_REBEL:
            return target.role == ROLE_LORD or target.role == ROLE_LOYALIST
        if actor.role == ROLE_RENEGADE:
            non_lords = [p for p in self.players if p.alive and p.role != ROLE_LORD and p is not actor]
            if non_lords:
                return target.role != ROLE_LORD
            return target.role == ROLE_LORD
        return False

    @staticmethod
    def _needs_target(card: Card) -> bool:
        return card.name in {CARD_SHA, CARD_TAO, CARD_GUOHE, CARD_JUEDOU}

    @staticmethod
    def _card_label(name: str) -> str:
        labels = {
            CARD_SHA: "Strike",
            CARD_SHAN: "Dodge",
            CARD_TAO: "Peach",
            CARD_WUZHONG: "Insight",
            CARD_GUOHE: "Dismantle",
            CARD_JUEDOU: "Duel",
        }
        return labels.get(name, name)

    @staticmethod
    def _find_index(cards: list[Card], name: str) -> int | None:
        for index, card in enumerate(cards):
            if card.name == name:
                return index
        return None

    def _remove_card_by_name(self, target: PlayerState, name: str) -> bool:
        for index, card in enumerate(target.hand):
            if card.name == name:
                target.hand.pop(index)
                return True
        return False

    def _check_game_over(self) -> bool:
        if self.winner:
            return True
        lord = next(p for p in self.players if p.role == ROLE_LORD)
        alive = [p for p in self.players if p.alive]
        if not lord.alive:
            renegade_alive = any(p.alive and p.role == ROLE_RENEGADE for p in self.players)
            others_alive = [p for p in alive if p.role != ROLE_LORD]
            self.winner = "Renegade" if renegade_alive and len(others_alive) == 1 else "Rebels"
        elif not any(p.alive and p.role == ROLE_REBEL for p in self.players) and not any(
            p.alive and p.role == ROLE_RENEGADE for p in self.players
        ):
            self.winner = "Lord Team"
        if self.winner:
            self.log(f"{self.winner} wins!")
        return self.winner is not None
