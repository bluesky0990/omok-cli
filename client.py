#!/usr/bin/env python3
"""
CLI Omok Game Client
Connects to server, displays UI, and handles user input
"""

import socket
import threading
import json
import sys
import time
import os
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich import box
import keyboard

# Load configuration
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
except FileNotFoundError:
    print("Error: config.json not found")
    sys.exit(1)

BOARD_SIZE = config['game']['board_size']
SERVER_ADDRESS = config['client']['server_address']
SERVER_PORT = config['client']['server_port']

# UI symbols
BLACK_STONE = config['ui']['black_stone']
WHITE_STONE = config['ui']['white_stone']
EMPTY = config['ui']['empty']
CURSOR_COLOR = config['ui']['cursor_color']
BLACK_COLOR = config['ui']['black_color']
WHITE_COLOR = config['ui']['white_color']

console = Console()


class GameClient:
    """Game client handling connection, state, and UI"""

    def __init__(self):
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.running = True

        # Client state
        self.nickname: Optional[str] = None
        self.current_screen = 'connect'  # connect, nickname, lobby, room, game
        self.room_id: Optional[str] = None
        self.room_name: Optional[str] = None
        self.my_color: Optional[str] = None

        # Game state
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.current_turn: Optional[str] = None
        self.black_player: Optional[str] = None
        self.white_player: Optional[str] = None
        self.cursor_x = BOARD_SIZE // 2
        self.cursor_y = BOARD_SIZE // 2

        # Room list
        self.rooms: List[Dict] = []
        self.selected_room_index = 0

        # Messages
        self.status_message = ""
        self.error_message = ""

        # Threading
        self.receive_thread: Optional[threading.Thread] = None
        self.ui_lock = threading.Lock()

        # Message buffer for handling multiple messages
        self.message_buffer = ""

    def connect_to_server(self) -> bool:
        """Connect to game server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((SERVER_ADDRESS, SERVER_PORT))
            self.connected = True

            # Start receive thread
            self.receive_thread = threading.Thread(target=self.receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            return True
        except Exception as e:
            console.print(f"[red]Failed to connect to server: {e}[/red]")
            return False

    def receive_messages(self):
        """Receive messages from server (runs in separate thread)"""
        try:
            while self.connected and self.running:
                data = self.socket.recv(4096)
                if not data:
                    break

                # Append received data to buffer
                self.message_buffer += data.decode('utf-8')

                # Process all complete messages (separated by newlines)
                while '\n' in self.message_buffer:
                    # Split on first newline
                    line, self.message_buffer = self.message_buffer.split('\n', 1)

                    # Skip empty lines
                    if not line.strip():
                        continue

                    try:
                        message = json.loads(line)
                        self.handle_message(message)
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {e} | Data: {line[:100]}")
                    except Exception as e:
                        print(f"Error handling message: {e}")

        except Exception as e:
            if self.running:
                console.print(f"[red]Connection lost: {e}[/red]")
        finally:
            self.connected = False

    def handle_message(self, message: Dict):
        """Handle incoming messages from server"""
        msg_type = message.get('type')
        msg_data = message.get('data', {})

        with self.ui_lock:
            if msg_type == 'nickname_set':
                self.status_message = f"Nickname set to: {msg_data.get('nickname')}"
                self.current_screen = 'lobby'

            elif msg_type == 'room_created':
                self.room_id = msg_data.get('room_id')
                self.status_message = "Room created! Waiting for opponent..."

            elif msg_type == 'room_list':
                self.rooms = msg_data.get('rooms', [])
                self.selected_room_index = 0

            elif msg_type == 'room_joined':
                self.room_id = msg_data.get('room_id')
                self.room_name = msg_data.get('room_name')
                self.my_color = msg_data.get('your_color')
                self.current_screen = 'room'
                self.status_message = f"Joined room '{self.room_name}' as {self.my_color}"

            elif msg_type == 'game_started':
                self.black_player = msg_data.get('black_player')
                self.white_player = msg_data.get('white_player')
                self.current_screen = 'game'
                self.status_message = "Game started!"

            elif msg_type == 'game_state':
                self.board = msg_data.get('board', self.board)
                self.current_turn = msg_data.get('current_turn')
                self.black_player = msg_data.get('black_player', self.black_player)
                self.white_player = msg_data.get('white_player', self.white_player)

            elif msg_type == 'move_result':
                if msg_data.get('success'):
                    self.status_message = f"Move made at ({msg_data.get('x')}, {msg_data.get('y')})"
                else:
                    self.error_message = "Invalid move"

            elif msg_type == 'game_over':
                winner = msg_data.get('winner')
                winner_nick = msg_data.get('winner_nickname')
                reason = msg_data.get('reason')

                if reason == 'surrender':
                    self.status_message = f"Game Over! {winner_nick} wins by surrender"
                else:
                    self.status_message = f"Game Over! {winner_nick} wins with 5 in a row!"

                # Transition to result screen
                self.current_screen = 'result'

            elif msg_type == 'player_left':
                self.status_message = msg_data.get('message', 'Player left')
                # Transition to result screen
                self.current_screen = 'result'

            elif msg_type == 'error':
                self.error_message = msg_data.get('message', 'Unknown error')

    def send_message(self, message: Dict):
        """Send message to server"""
        try:
            if self.socket and self.connected:
                data = json.dumps(message).encode('utf-8')
                self.socket.sendall(data)
        except Exception as e:
            console.print(f"[red]Failed to send message: {e}[/red]")

    def set_nickname(self, nickname: str):
        """Set player nickname"""
        self.nickname = nickname
        self.send_message({
            'type': 'set_nickname',
            'data': {'nickname': nickname}
        })

    def create_room(self, room_name: str):
        """Create a new room"""
        self.send_message({
            'type': 'create_room',
            'data': {'room_name': room_name}
        })

    def request_room_list(self):
        """Request list of available rooms"""
        self.send_message({'type': 'list_rooms'})

    def join_room(self, room_id: str):
        """Join an existing room"""
        self.send_message({
            'type': 'join_room',
            'data': {'room_id': room_id}
        })

    def make_move(self, x: int, y: int):
        """Make a move at position (x, y)"""
        self.send_message({
            'type': 'move',
            'data': {'x': x, 'y': y}
        })

    def surrender(self):
        """Surrender the game"""
        self.send_message({'type': 'surrender'})

    def render_board(self) -> Panel:
        """Render the game board"""
        lines = []

        # Column headers (A-O)
        header = "   " + " ".join([chr(65 + i) for i in range(BOARD_SIZE)])
        lines.append(header)

        # Board rows
        for y in range(BOARD_SIZE):
            row = f"{y + 1:2d} "
            for x in range(BOARD_SIZE):
                stone = self.board[y][x]

                # Check if cursor is here (use background color instead of brackets)
                if x == self.cursor_x and y == self.cursor_y:
                    if stone == 0:
                        row += f"[black on {CURSOR_COLOR}]{EMPTY}[/black on {CURSOR_COLOR}] "
                    elif stone == 1:
                        row += f"[{BLACK_COLOR} on {CURSOR_COLOR}]{BLACK_STONE}[/{BLACK_COLOR} on {CURSOR_COLOR}] "
                    else:
                        row += f"[{WHITE_COLOR} on {CURSOR_COLOR}]{WHITE_STONE}[/{WHITE_COLOR} on {CURSOR_COLOR}] "
                else:
                    if stone == 0:
                        row += f"{EMPTY} "
                    elif stone == 1:
                        row += f"[{BLACK_COLOR}]{BLACK_STONE}[/{BLACK_COLOR}] "
                    else:
                        row += f"[{WHITE_COLOR}]{WHITE_STONE}[/{WHITE_COLOR}] "

            lines.append(row)

        board_text = "\n".join(lines)
        return Panel(board_text, title="Game Board", border_style="blue")

    def render_game_info(self) -> Panel:
        """Render game information"""
        info_lines = []
        info_lines.append(f"Room: {self.room_name or 'N/A'}")
        info_lines.append(f"")
        info_lines.append(f"[{BLACK_COLOR}]{BLACK_STONE}[/{BLACK_COLOR}] Black: {self.black_player or 'N/A'}")
        info_lines.append(f"[{WHITE_COLOR}]{WHITE_STONE}[/{WHITE_COLOR}] White: {self.white_player or 'N/A'}")
        info_lines.append(f"")

        if self.current_turn:
            if self.current_turn == self.my_color:
                info_lines.append(f"[green]Your turn ({self.my_color})[/green]")
            else:
                info_lines.append(f"[yellow]Opponent's turn ({self.current_turn})[/yellow]")

        if self.status_message:
            info_lines.append(f"")
            info_lines.append(f"[cyan]{self.status_message}[/cyan]")

        if self.error_message:
            info_lines.append(f"")
            info_lines.append(f"[red]{self.error_message}[/red]")

        info_lines.append(f"")
        info_lines.append(f"[dim]Arrow keys: Move cursor[/dim]")
        info_lines.append(f"[dim]Enter: Place stone[/dim]")
        info_lines.append(f"[dim]ESC: Surrender[/dim]")

        info_text = "\n".join(info_lines)
        return Panel(info_text, title="Game Info", border_style="green")

    def render_game_screen(self):
        """Render the full game screen"""
        console.clear()

        with self.ui_lock:
            console.print(self.render_game_info())
            console.print(self.render_board())

            # Clear old messages after display
            if self.error_message:
                self.error_message = ""

    def render_lobby_screen(self):
        """Render the lobby screen"""
        console.clear()

        console.print(Panel(f"Welcome, [cyan]{self.nickname}[/cyan]!", title="Lobby", border_style="blue"))
        console.print("\n[bold]1.[/bold] Create Room")
        console.print("[bold]2.[/bold] Join Room")
        console.print("[bold]3.[/bold] Refresh Room List")
        console.print("[bold]Q.[/bold] Quit\n")

        # Show room list
        if self.rooms:
            table = Table(title="Available Rooms", box=box.ROUNDED)
            table.add_column("#", style="cyan", width=6)
            table.add_column("Room Name", style="green")
            table.add_column("Players", style="yellow", width=10)
            table.add_column("Status", style="magenta", width=12)

            for i, room in enumerate(self.rooms):
                status_style = "green" if room['status'] == 'waiting' else "red"
                table.add_row(
                    str(i + 1),
                    room['name'],
                    f"{room['players']}/2",
                    f"[{status_style}]{room['status']}[/{status_style}]"
                )

            console.print(table)
        else:
            console.print("[dim]No rooms available. Create one![/dim]")

        if self.status_message:
            console.print(f"\n[cyan]{self.status_message}[/cyan]")
            self.status_message = ""

        if self.error_message:
            console.print(f"\n[red]{self.error_message}[/red]")
            self.error_message = ""

    def run_lobby(self):
        """Handle lobby input"""
        while self.current_screen == 'lobby' and self.running:
            self.render_lobby_screen()

            choice = console.input("\n[bold cyan]Enter choice:[/bold cyan] ").strip().lower()

            # Check if screen changed during input (e.g., game ended)
            if self.current_screen != 'lobby':
                console.clear()  # Clear any remaining prompts
                break

            if choice == '1':
                room_name = console.input("Enter room name: ").strip()

                # Check if screen changed during input
                if self.current_screen != 'lobby':
                    console.clear()  # Clear any remaining prompts
                    break

                if room_name:
                    self.create_room(room_name)
                    time.sleep(0.5)  # Wait for response
                else:
                    self.error_message = "Room name cannot be empty"

            elif choice == '2':
                if not self.rooms:
                    self.error_message = "No rooms available"
                else:
                    try:
                        room_num = int(console.input("Enter room number: ").strip())

                        # Check if screen changed during input
                        if self.current_screen != 'lobby':
                            console.clear()  # Clear any remaining prompts
                            break

                        if 1 <= room_num <= len(self.rooms):
                            selected_room = self.rooms[room_num - 1]
                            if selected_room['status'] == 'waiting':
                                self.join_room(selected_room['id'])
                                time.sleep(0.5)  # Wait for response
                            else:
                                self.error_message = "Room is not available"
                        else:
                            self.error_message = "Invalid room number"
                    except ValueError:
                        self.error_message = "Please enter a valid number"

            elif choice == '3':
                self.request_room_list()
                time.sleep(0.3)  # Wait for response

            elif choice == 'q':
                self.running = False
                break

    def run_room_waiting(self):
        """Wait in room for opponent"""
        while self.current_screen == 'room' and self.running:
            console.clear()
            console.print(Panel(
                f"[cyan]Waiting for opponent in '{self.room_name}'...[/cyan]\n\n"
                f"You are: [bold]{self.my_color}[/bold]\n\n"
                f"[dim]Press ESC to leave room[/dim]",
                title="Room",
                border_style="yellow"
            ))

            # Check for ESC key
            if keyboard.is_pressed('esc'):
                # Notify server that we're leaving the room
                self.send_message({'type': 'leave_room'})

                self.current_screen = 'lobby'
                self.room_id = None
                self.room_name = None
                self.my_color = None
                time.sleep(0.3)  # Debounce
                break

            time.sleep(0.5)

    def run_result(self):
        """Show game result and wait for user to return to lobby"""
        console.clear()

        # Display result message
        result_text = self.status_message or "Game Over"

        console.print(Panel(
            f"[bold yellow]{result_text}[/bold yellow]\n\n"
            f"[dim]Press Enter to return to lobby...[/dim]",
            title="Game Result",
            border_style="green"
        ))

        # Wait for Enter key
        input()

        # Clean up and return to lobby
        console.clear()
        self.current_screen = 'lobby'
        self.room_id = None
        self.room_name = None
        self.my_color = None
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.status_message = ""

    def handle_game_input(self):
        """Handle input during game (runs in separate thread)"""
        while self.running:
            if self.current_screen != 'game':
                time.sleep(0.1)
                continue

            try:
                # Arrow keys for cursor movement
                if keyboard.is_pressed('up'):
                    with self.ui_lock:
                        self.cursor_y = max(0, self.cursor_y - 1)
                    time.sleep(0.15)  # Debounce

                elif keyboard.is_pressed('down'):
                    with self.ui_lock:
                        self.cursor_y = min(BOARD_SIZE - 1, self.cursor_y + 1)
                    time.sleep(0.15)

                elif keyboard.is_pressed('left'):
                    with self.ui_lock:
                        self.cursor_x = max(0, self.cursor_x - 1)
                    time.sleep(0.15)

                elif keyboard.is_pressed('right'):
                    with self.ui_lock:
                        self.cursor_x = min(BOARD_SIZE - 1, self.cursor_x + 1)
                    time.sleep(0.15)

                elif keyboard.is_pressed('enter'):
                    with self.ui_lock:
                        if self.current_turn == self.my_color:
                            self.make_move(self.cursor_x, self.cursor_y)
                    time.sleep(0.3)  # Debounce

                elif keyboard.is_pressed('esc'):
                    with self.ui_lock:
                        # Confirm surrender
                        console.print("\n[red]Are you sure you want to surrender? (y/n)[/red]")
                        confirm = console.input().strip().lower()
                        if confirm == 'y':
                            self.surrender()
                    time.sleep(0.3)

            except Exception as e:
                # Ignore keyboard errors
                pass

            time.sleep(0.05)

    def run_game(self):
        """Run game loop"""
        # Start input handler thread
        input_thread = threading.Thread(target=self.handle_game_input)
        input_thread.daemon = True
        input_thread.start()

        while self.current_screen == 'game' and self.running:
            self.render_game_screen()
            time.sleep(0.1)  # Refresh rate

    def run(self):
        """Main client loop"""
        console.clear()
        console.print(Panel("[bold cyan]CLI Omok Game[/bold cyan]", border_style="blue"))

        # Connect to server
        console.print(f"\nConnecting to {SERVER_ADDRESS}:{SERVER_PORT}...")
        if not self.connect_to_server():
            return

        console.print("[green]Connected to server![/green]\n")

        # Get nickname
        while not self.nickname and self.running:
            nickname = console.input("Enter your nickname: ").strip()
            if nickname:
                self.set_nickname(nickname)
                time.sleep(0.3)  # Wait for response

        # Main loop
        try:
            while self.running and self.connected:
                if self.current_screen == 'lobby':
                    self.run_lobby()
                elif self.current_screen == 'room':
                    self.run_room_waiting()
                elif self.current_screen == 'game':
                    self.run_game()
                elif self.current_screen == 'result':
                    self.run_result()
                else:
                    time.sleep(0.1)

        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting...[/yellow]")
        finally:
            if self.socket:
                self.socket.close()
            console.print("[green]Disconnected from server. Goodbye![/green]")


def main():
    """Main entry point"""
    client = GameClient()
    client.run()


if __name__ == '__main__':
    main()
