from __future__ import annotations

import base64
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from .game import Game, PlayerState


ROOT = Path(__file__).resolve().parent.parent
SGS_HERO_DIR = ROOT / "assets" / "sgs" / "heroes"
SGS_CARD_DIR = ROOT / "assets" / "sgs" / "cards"

BG = "#211b18"
TABLE = "#796b58"
TABLE_DARK = "#4c4037"
TEXT = "#f4e5bd"


class SanguoshaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SanGuoSha - Identity Mode")
        self.geometry("1280x760")
        self.minsize(1160, 690)
        self.configure(bg=BG)

        self.images: dict[str, tk.PhotoImage] = {}
        self.log_lines: list[str] = []
        self.game = Game(self.add_log)
        self.pending_card_index: int | None = None
        self.ai_running = False

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.table = tk.Canvas(self, bg=TABLE_DARK, highlightthickness=0)
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.bind("<Configure>", lambda _event: self._draw_table())

        self.top_info = tk.Label(
            self,
            bg="#1b1714",
            fg=TEXT,
            text="Lord x1   Loyalist x1   Rebel x2   Renegade x1",
            font=("Microsoft YaHei UI", 13, "bold"),
            padx=12,
            pady=6,
        )
        self.table.create_window(22, 18, anchor="nw", window=self.top_info)

        self.round_label = tk.Label(
            self,
            bg="#1b1714",
            fg="#fff1bf",
            font=("Consolas", 14, "bold"),
            padx=12,
            pady=6,
        )
        self.table.create_window(985, 18, anchor="nw", window=self.round_label)

        self.left_panel = tk.Frame(self, bg="#28211e")
        self.table.create_window(10, 415, anchor="nw", window=self.left_panel)

        log_box = tk.Frame(self.left_panel, bg="#1c1715")
        log_box.pack(padx=4, pady=(4, 8))

        self.log_text = tk.Text(
            log_box,
            width=23,
            height=18,
            bg="#1c1715",
            fg="#f1dfbd",
            relief="flat",
            wrap="word",
            font=("Consolas", 9),
            state="disabled",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_scroll = tk.Scrollbar(log_box, command=self.log_text.yview)
        self.log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.config(yscrollcommand=self.log_scroll.set)

        self.enemy_left = HeroCard(self)
        self.enemy_top = HeroCard(self)
        self.enemy_top_right = HeroCard(self)
        self.enemy_right = HeroCard(self)
        self.player_card = HeroCard(self)

        self.table.create_window(18, 155, anchor="nw", window=self.enemy_left)
        self.table.create_window(360, 18, anchor="nw", window=self.enemy_top)
        self.table.create_window(735, 18, anchor="nw", window=self.enemy_top_right)
        self.table.create_window(1105, 156, anchor="nw", window=self.enemy_right)
        self.table.create_window(1100, 480, anchor="nw", window=self.player_card)

        self.action_button = tk.Button(
            self,
            text="End Turn",
            command=self.end_turn,
            bg="#d4aa3c",
            fg="#3a2610",
            activebackground="#b78929",
            activeforeground="#21140b",
            relief="raised",
            bd=3,
            font=("Microsoft YaHei UI", 16, "bold"),
            padx=24,
            pady=7,
        )
        self.table.create_window(970, 610, anchor="nw", window=self.action_button)

        self.target_frame = tk.Frame(self, bg="#1b1714", highlightthickness=1, highlightbackground="#d4aa3c")
        self.table.create_window(420, 430, anchor="nw", window=self.target_frame)

        self.restart_button = tk.Button(
            self,
            text="+",
            command=self.restart,
            bg="#58443a",
            fg="#f5d885",
            activebackground="#6b5143",
            activeforeground="#fff0bf",
            relief="raised",
            bd=4,
            font=("Arial", 30, "bold"),
            width=2,
            height=1,
        )
        self.table.create_window(1208, 26, anchor="nw", window=self.restart_button)

        self.hand_frame = tk.Frame(self, bg="#2b2520")
        self.table.create_window(176, 548, anchor="nw", window=self.hand_frame)

    def add_log(self, message: str) -> None:
        self.log_lines.append(message)

    def restart(self) -> None:
        self.log_lines.clear()
        self.pending_card_index = None
        self.ai_running = False
        self.game = Game(self.add_log)
        self.refresh()

    def end_turn(self) -> None:
        self.pending_card_index = None
        self.game.end_player_turn()
        self.refresh()
        self._show_winner_if_needed()
        self._schedule_ai_turns()

    def play_card(self, index: int) -> None:
        targets = self.game.valid_targets_for_player_card(index)
        if targets and self.game.player.hand[index].name in {"\u6740", "\u6843", "\u8fc7\u6cb3\u62c6\u6865", "\u51b3\u6597"}:
            self.pending_card_index = index
            self._render_targets(targets)
            return
        self.pending_card_index = None
        self.game.play_player_card(index)
        self.refresh()
        self._show_winner_if_needed()

    def play_card_on_target(self, target_seat: int) -> None:
        if self.pending_card_index is not None:
            self.game.play_player_card(self.pending_card_index, target_seat=target_seat)
        self.pending_card_index = None
        self.refresh()
        self._show_winner_if_needed()

    def _schedule_ai_turns(self) -> None:
        if self.ai_running or self.game.winner or self.game.current_player.is_human:
            return
        self.ai_running = True
        self.after(900, self._run_next_ai_turn)

    def _run_next_ai_turn(self) -> None:
        if self.game.winner or self.game.current_player.is_human:
            self.ai_running = False
            self.refresh()
            self._show_winner_if_needed()
            return
        self.game.run_current_ai_turn()
        self.refresh()
        self._show_winner_if_needed()
        if self.game.winner or self.game.current_player.is_human:
            self.ai_running = False
        else:
            self.after(3800, self._run_next_ai_turn)

    def refresh(self) -> None:
        players = self.game.players
        self.enemy_left.render_state(players[1], self.images, active=self.game.current_player is players[1])
        self.enemy_top.render_state(players[2], self.images, active=self.game.current_player is players[2])
        self.enemy_top_right.render_state(players[3], self.images, active=self.game.current_player is players[3])
        self.enemy_right.render_state(players[4], self.images, active=self.game.current_player is players[4])
        self.player_card.render_state(players[0], self.images, active=self.game.current_player is players[0])
        self.round_label.config(text=f"Round {self.game.round}")

        is_human_turn = self.game.current_player is self.game.player and not self.game.winner and not self.ai_running
        self.action_button.config(text=("End Turn" if is_human_turn else "Waiting"), state=("normal" if is_human_turn else "disabled"))
        self._render_hand()
        self._render_targets([])
        self._render_log()
        self._draw_table()

    def _draw_table(self) -> None:
        width = max(self.table.winfo_width(), 1280)
        height = max(self.table.winfo_height(), 760)
        self.table.delete("table_art")

        self.table.create_rectangle(0, 0, width, height, fill=TABLE_DARK, outline="", tags="table_art")
        self.table.create_oval(140, -90, width - 160, height + 210, fill=TABLE, outline="#9b8a70", width=4, tags="table_art")
        self.table.create_oval(300, 72, width - 300, height - 80, outline="#a99a82", width=3, tags="table_art")
        self.table.create_oval(430, 170, width - 430, height - 170, outline="#8d7d68", width=2, tags="table_art")
        self.table.create_text(width // 2, height // 2, text="SanGuoSha", fill="#8b7b65", font=("Georgia", 64, "bold"), tags="table_art")
        self.table.create_text(width // 2, height // 2 + 70, text="IDENTITY MODE", fill="#b8a782", font=("Georgia", 18, "bold"), tags="table_art")
        for x in range(260, width - 260, 90):
            self.table.create_arc(x, 125, x + 120, 245, start=20, extent=100, outline="#887861", width=1, tags="table_art")
            self.table.create_arc(x, 385, x + 120, 505, start=200, extent=100, outline="#887861", width=1, tags="table_art")
        self.table.tag_lower("table_art")

    def _render_hand(self) -> None:
        for child in self.hand_frame.winfo_children():
            child.destroy()

        is_human_turn = self.game.current_player is self.game.player and not self.game.winner
        for index, card in enumerate(self.game.player.hand):
            image = self._load_card_image(card.image)
            if image:
                button = tk.Button(
                    self.hand_frame,
                    image=image,
                    command=lambda i=index: self.play_card(i),
                    bg="#221c18",
                    activebackground="#4a3529",
                    relief="raised",
                    bd=2,
                    state=("normal" if is_human_turn else "disabled"),
                )
            else:
                button = tk.Button(
                    self.hand_frame,
                    text=f"{card.name}\n{card.description}",
                    command=lambda i=index: self.play_card(i),
                    width=9,
                    height=7,
                    wraplength=80,
                    bg=card.color,
                    fg="white",
                    activebackground="#4a3529",
                    activeforeground="white",
                    relief="raised",
                    bd=2,
                    font=("Microsoft YaHei UI", 10, "bold"),
                    state=("normal" if is_human_turn else "disabled"),
                )
            button.grid(row=0, column=index, padx=4, pady=4)

        if not self.game.player.hand:
            tk.Label(
                self.hand_frame,
                text="No Cards",
                bg="#2b2520",
                fg="#f1dfbd",
                font=("Microsoft YaHei UI", 12),
            ).grid(row=0, column=0, padx=20, pady=55)

    def _render_targets(self, targets: list[PlayerState]) -> None:
        for child in self.target_frame.winfo_children():
            child.destroy()
        if not targets:
            return

        card_name = self.game.player.hand[self.pending_card_index].name if self.pending_card_index is not None else "Card"
        tk.Label(
            self.target_frame,
            text=f"Choose target for {card_name}",
            bg="#1b1714",
            fg="#f4dfaf",
            font=("Microsoft YaHei UI", 11, "bold"),
        ).grid(row=0, column=0, columnspan=6, padx=8, pady=(6, 3), sticky="w")

        for index, target in enumerate(targets):
            label = f"{target.name}\n{target.hero.name}"
            tk.Button(
                self.target_frame,
                text=label,
                command=lambda seat=target.seat: self.play_card_on_target(seat),
                bg="#4a3932",
                fg="#fff0bf",
                activebackground="#5a473d",
                activeforeground="#ffffff",
                relief="raised",
                bd=2,
                width=10,
                height=1,
                font=("Microsoft YaHei UI", 9, "bold"),
            ).grid(row=1, column=index, padx=4, pady=(0, 8))

        tk.Button(
            self.target_frame,
            text="Cancel",
            command=lambda: self._cancel_target_choice(),
            bg="#5b2d29",
            fg="#fff0bf",
            activebackground="#6b3832",
            activeforeground="#ffffff",
            relief="raised",
            bd=2,
            width=8,
            height=1,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).grid(row=1, column=len(targets), padx=4, pady=(0, 6))

    def _cancel_target_choice(self) -> None:
        self.pending_card_index = None
        self._render_targets([])

    def _render_log(self) -> None:
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", "\n".join(self.log_lines))
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _load_card_image(self, filename: str) -> tk.PhotoImage | None:
        if not filename:
            return None
        key = f"card:{filename}"
        if key not in self.images:
            path = SGS_CARD_DIR / filename
            if not path.exists():
                return None
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            self.images[key] = tk.PhotoImage(data=data, format="png")
        return self.images[key]

    def _show_winner_if_needed(self) -> None:
        if self.game.winner:
            messagebox.showinfo("Game Over", f"{self.game.winner} wins!")


class HeroCard(tk.Frame):
    def __init__(self, parent: tk.Widget):
        super().__init__(parent, bg="#171311", highlightthickness=2, highlightbackground="#4b3529")
        self.portrait = tk.Label(self, bg="#11100f")
        self.portrait.grid(row=0, column=0, columnspan=2, padx=5, pady=5)
        self.name_label = tk.Label(self, bg="#171311", fg="#f7e9bc", font=("Microsoft YaHei UI", 13, "bold"))
        self.name_label.grid(row=1, column=0, padx=5, sticky="w")
        self.hp_label = tk.Label(self, bg="#171311", fg="#5dff5d", font=("Arial", 13, "bold"))
        self.hp_label.grid(row=1, column=1, padx=5, sticky="e")
        self.skill_label = tk.Label(self, bg="#171311", fg="#d8c38b", font=("Microsoft YaHei UI", 9))
        self.skill_label.grid(row=2, column=0, columnspan=2, padx=5, pady=(0, 5), sticky="ew")

    def render_state(self, state: PlayerState, image_cache: dict[str, tk.PhotoImage], active: bool) -> None:
        hero = state.hero
        image = self._load_hero_image(hero.image, image_cache)
        if image:
            self.portrait.config(image=image, text="")
        else:
            self.portrait.config(image="", text=hero.name, fg="#f7e9bc", width=16, height=10)

        border = "#31ff45" if active else "#4b3529"
        self.config(highlightbackground=border)
        self.name_label.config(text=f"{hero.faction} {hero.name}")
        hp = "●" * hero.hp + "○" * (hero.max_hp - hero.hp)
        self.hp_label.config(text=hp)
        role = state.role if state.is_human or state.role == "Lord" or not state.alive else "Hidden"
        self.skill_label.config(text=f"{state.name} · {role} · Cards {len(state.hand)}")

    @staticmethod
    def _load_hero_image(filename: str, image_cache: dict[str, tk.PhotoImage]) -> tk.PhotoImage | None:
        key = f"hero:{filename}"
        if key not in image_cache:
            path = SGS_HERO_DIR / filename
            if not path.exists():
                return None
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            image_cache[key] = tk.PhotoImage(data=data, format="png")
        return image_cache[key]
