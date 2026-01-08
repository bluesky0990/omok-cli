#!/usr/bin/env python3
"""
CLI Omok Game Server
Handles multiple clients, room management, and game logic
"""

import socket
import threading
import json
import sys
import time
from typing import Dict, List, Optional, Tuple

# Load configuration
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
except FileNotFoundError:
    print("Error: config.json not found")
    sys.exit(1)

BOARD_SIZE = config['game']['board_size']
HOST = config['server']['host']
PORT = config['server']['port']


class Room:
    """Represents a game room with two players and game state"""

    def __init__(self, room_id: str, room_name: str, creator_id: str, creator_nickname: str):
        self.room_id = room_id
        self.name = room_name
        self.players: List[Dict] = []
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.current_turn = 'black'  # black starts first
        self.game_started = False
        self.game_over = False
        self.winner = None

        # Add creator as first player (black)
        self.add_player(creator_id, creator_nickname)

    def add_player(self, client_id: str, nickname: str) -> bool:
        """Add a player to the room. Returns True if successful."""
        if len(self.players) >= 2:
            return False

        color = 'black' if len(self.players) == 0 else 'white'
        self.players.append({
            'client_id': client_id,
            'nickname': nickname,
            'color': color
        })

        # Start game when 2 players joined
        if len(self.players) == 2:
            self.game_started = True

        return True

    def remove_player(self, client_id: str):
        """Remove a player from the room"""
        self.players = [p for p in self.players if p['client_id'] != client_id]
        if len(self.players) < 2:
            self.game_started = False

    def get_player_color(self, client_id: str) -> Optional[str]:
        """Get the color of a player by client_id"""
        for player in self.players:
            if player['client_id'] == client_id:
                return player['color']
        return None

    def get_player_nickname(self, color: str) -> Optional[str]:
        """Get nickname by color"""
        for player in self.players:
            if player['color'] == color:
                return player['nickname']
        return None

    def is_valid_move(self, x: int, y: int) -> bool:
        """Check if a move is valid"""
        if x < 0 or x >= BOARD_SIZE or y < 0 or y >= BOARD_SIZE:
            return False
        return self.board[y][x] == 0

    def make_move(self, x: int, y: int, color: str) -> bool:
        """Make a move. Returns True if successful."""
        if not self.is_valid_move(x, y):
            return False

        if color != self.current_turn:
            return False

        # Place stone (1 for black, 2 for white)
        stone_value = 1 if color == 'black' else 2
        self.board[y][x] = stone_value

        # Check for winner
        if self.check_winner(x, y, stone_value):
            self.game_over = True
            self.winner = color
        else:
            # Switch turn
            self.current_turn = 'white' if self.current_turn == 'black' else 'black'

        return True

    def check_winner(self, x: int, y: int, stone: int) -> bool:
        """Check if the last move resulted in a win (exactly 5 in a row)"""
        directions = [
            (1, 0),   # horizontal
            (0, 1),   # vertical
            (1, 1),   # diagonal \
            (1, -1)   # diagonal /
        ]

        for dx, dy in directions:
            count = 1  # count the stone we just placed

            # Count in positive direction
            count += self._count_direction(x, y, dx, dy, stone)

            # Count in negative direction
            count += self._count_direction(x, y, -dx, -dy, stone)

            # Win if exactly 5 (not more, to handle 6-stone rule later if needed)
            if count == 5:
                return True

        return False

    def _count_direction(self, x: int, y: int, dx: int, dy: int, stone: int) -> int:
        """Count consecutive stones in a direction"""
        count = 0
        nx, ny = x + dx, y + dy

        while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
            if self.board[ny][nx] == stone:
                count += 1
                nx += dx
                ny += dy
            else:
                break

        return count

    def get_status(self) -> str:
        """Get room status"""
        if self.game_over:
            return 'finished'
        elif self.game_started:
            return 'playing'
        else:
            return 'waiting'

    def to_dict(self) -> Dict:
        """Convert room info to dictionary"""
        return {
            'id': self.room_id,
            'name': self.name,
            'players': len(self.players),
            'status': self.get_status()
        }


class GameServer:
    """Main game server handling connections and rooms"""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.rooms: Dict[str, Room] = {}
        self.clients: Dict[str, Dict] = {}  # client_id -> {socket, nickname, room_id}
        self.next_room_id = 1
        self.next_client_id = 1
        self.lock = threading.Lock()
        self.server_socket = None

    def start(self):
        """Start the server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"Server started on {self.host}:{self.port}")
            print("Waiting for connections...")

            while True:
                client_socket, address = self.server_socket.accept()
                print(f"New connection from {address}")

                # Assign client ID
                with self.lock:
                    client_id = f"client_{self.next_client_id}"
                    self.next_client_id += 1
                    self.clients[client_id] = {
                        'socket': client_socket,
                        'nickname': None,
                        'room_id': None,
                        'address': address
                    }

                # Handle client in separate thread
                thread = threading.Thread(target=self.handle_client, args=(client_id,))
                thread.daemon = True
                thread.start()

        except KeyboardInterrupt:
            print("\nShutting down server...")
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def handle_client(self, client_id: str):
        """Handle messages from a client"""
        client_socket = self.clients[client_id]['socket']

        try:
            while True:
                # Receive message
                data = client_socket.recv(4096)
                if not data:
                    break

                try:
                    message = json.loads(data.decode('utf-8'))
                    msg_type = message.get('type')
                    msg_data = message.get('data', {})

                    # Handle different message types
                    if msg_type == 'set_nickname':
                        self.handle_set_nickname(client_id, msg_data)
                    elif msg_type == 'create_room':
                        self.handle_create_room(client_id, msg_data)
                    elif msg_type == 'list_rooms':
                        self.handle_list_rooms(client_id)
                    elif msg_type == 'join_room':
                        self.handle_join_room(client_id, msg_data)
                    elif msg_type == 'move':
                        self.handle_move(client_id, msg_data)
                    elif msg_type == 'surrender':
                        self.handle_surrender(client_id)
                    elif msg_type == 'leave_room':
                        self.handle_leave_room(client_id)
                    else:
                        self.send_error(client_id, f"Unknown message type: {msg_type}")

                except json.JSONDecodeError:
                    self.send_error(client_id, "Invalid JSON format")
                except Exception as e:
                    print(f"Error handling message from {client_id}: {e}")
                    self.send_error(client_id, str(e))

        except Exception as e:
            print(f"Client {client_id} connection error: {e}")
        finally:
            self.disconnect_client(client_id)

    def handle_set_nickname(self, client_id: str, data: Dict):
        """Handle nickname setting"""
        nickname = data.get('nickname', '').strip()
        if not nickname:
            self.send_error(client_id, "Nickname cannot be empty")
            return

        with self.lock:
            self.clients[client_id]['nickname'] = nickname

        self.send_message(client_id, {
            'type': 'nickname_set',
            'data': {'success': True, 'nickname': nickname}
        })

    def handle_create_room(self, client_id: str, data: Dict):
        """Handle room creation"""
        room_name = data.get('room_name', '').strip()
        if not room_name:
            self.send_error(client_id, "Room name cannot be empty")
            return

        nickname = self.clients[client_id].get('nickname')
        if not nickname:
            self.send_error(client_id, "Please set nickname first")
            return

        with self.lock:
            room_id = f"room_{self.next_room_id}"
            self.next_room_id += 1

            # Create room
            room = Room(room_id, room_name, client_id, nickname)
            self.rooms[room_id] = room
            self.clients[client_id]['room_id'] = room_id

        # Send confirmation
        self.send_message(client_id, {
            'type': 'room_created',
            'data': {'room_id': room_id}
        })

        # Send room joined message
        self.send_message(client_id, {
            'type': 'room_joined',
            'data': {
                'room_id': room_id,
                'room_name': room_name,
                'your_color': 'black'
            }
        })

        print(f"Room '{room_name}' created by {nickname}")

    def handle_list_rooms(self, client_id: str):
        """Handle room list request"""
        with self.lock:
            room_list = [room.to_dict() for room in self.rooms.values()]

        self.send_message(client_id, {
            'type': 'room_list',
            'data': {'rooms': room_list}
        })

    def handle_join_room(self, client_id: str, data: Dict):
        """Handle room join request"""
        room_id = data.get('room_id')
        if not room_id:
            self.send_error(client_id, "Room ID is required")
            return

        nickname = self.clients[client_id].get('nickname')
        if not nickname:
            self.send_error(client_id, "Please set nickname first")
            return

        with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                self.send_error(client_id, "Room not found")
                return

            if len(room.players) >= 2:
                self.send_error(client_id, "Room is full")
                return

            # Add player to room
            if room.add_player(client_id, nickname):
                self.clients[client_id]['room_id'] = room_id
                player_color = room.get_player_color(client_id)

                # Send join confirmation
                self.send_message(client_id, {
                    'type': 'room_joined',
                    'data': {
                        'room_id': room_id,
                        'room_name': room.name,
                        'your_color': player_color
                    }
                })

                # If game started (2 players), notify both
                if room.game_started:
                    black_nick = room.get_player_nickname('black')
                    white_nick = room.get_player_nickname('white')

                    self.broadcast_to_room(room_id, {
                        'type': 'game_started',
                        'data': {
                            'black_player': black_nick,
                            'white_player': white_nick
                        }
                    })

                    # Send initial game state
                    self.broadcast_game_state(room_id)

                print(f"{nickname} joined room '{room.name}'")
            else:
                self.send_error(client_id, "Failed to join room")

    def handle_move(self, client_id: str, data: Dict):
        """Handle move request"""
        room_id = self.clients[client_id].get('room_id')
        if not room_id:
            self.send_error(client_id, "You are not in a room")
            return

        room = self.rooms.get(room_id)
        if not room or not room.game_started:
            self.send_error(client_id, "Game has not started")
            return

        if room.game_over:
            self.send_error(client_id, "Game is already over")
            return

        x = data.get('x')
        y = data.get('y')
        if x is None or y is None:
            self.send_error(client_id, "Invalid move coordinates")
            return

        player_color = room.get_player_color(client_id)
        if player_color != room.current_turn:
            self.send_error(client_id, "It's not your turn")
            return

        # Attempt move
        if room.make_move(x, y, player_color):
            # Broadcast move result
            self.broadcast_to_room(room_id, {
                'type': 'move_result',
                'data': {
                    'success': True,
                    'x': x,
                    'y': y,
                    'color': player_color
                }
            })

            # Send updated game state
            self.broadcast_game_state(room_id)

            # Check if game over
            if room.game_over:
                winner_nick = room.get_player_nickname(room.winner)
                self.broadcast_to_room(room_id, {
                    'type': 'game_over',
                    'data': {
                        'winner': room.winner,
                        'winner_nickname': winner_nick,
                        'reason': 'five_in_row'
                    }
                })
                print(f"Game over in room '{room.name}': {winner_nick} wins!")

                # Schedule room deletion after 10 seconds
                self.schedule_room_deletion(room_id, 10)
        else:
            self.send_error(client_id, "Invalid move")

    def handle_surrender(self, client_id: str):
        """Handle surrender request"""
        room_id = self.clients[client_id].get('room_id')
        if not room_id:
            return

        room = self.rooms.get(room_id)
        if not room or not room.game_started:
            return

        player_color = room.get_player_color(client_id)
        winner_color = 'white' if player_color == 'black' else 'black'
        winner_nick = room.get_player_nickname(winner_color)

        room.game_over = True
        room.winner = winner_color

        self.broadcast_to_room(room_id, {
            'type': 'game_over',
            'data': {
                'winner': winner_color,
                'winner_nickname': winner_nick,
                'reason': 'surrender'
            }
        })

        print(f"Player {self.clients[client_id]['nickname']} surrendered in room '{room.name}'")

        # Schedule room deletion after 10 seconds
        self.schedule_room_deletion(room_id, 10)

    def handle_leave_room(self, client_id: str):
        """Handle player leaving a room"""
        with self.lock:
            client = self.clients.get(client_id)
            if not client:
                return

            room_id = client.get('room_id')
            if not room_id:
                return

            room = self.rooms.get(room_id)
            if not room:
                return

            # Remove player from room
            room.remove_player(client_id)
            client['room_id'] = None

            # Notify other players
            if len(room.players) > 0:
                self.broadcast_to_room(room_id, {
                    'type': 'player_left',
                    'data': {'message': f"{client['nickname']} has left the room"}
                })
            else:
                # Remove empty room
                del self.rooms[room_id]
                print(f"Room '{room.name}' removed (player left)")

    def broadcast_game_state(self, room_id: str):
        """Broadcast current game state to all players in room"""
        room = self.rooms.get(room_id)
        if not room:
            return

        self.broadcast_to_room(room_id, {
            'type': 'game_state',
            'data': {
                'board': room.board,
                'current_turn': room.current_turn,
                'black_player': room.get_player_nickname('black'),
                'white_player': room.get_player_nickname('white')
            }
        })

    def broadcast_to_room(self, room_id: str, message: Dict):
        """Send message to all clients in a room"""
        room = self.rooms.get(room_id)
        if not room:
            return

        for player in room.players:
            self.send_message(player['client_id'], message)

    def send_message(self, client_id: str, message: Dict):
        """Send JSON message to a client"""
        try:
            client = self.clients.get(client_id)
            if client and client['socket']:
                # Add newline delimiter to separate multiple messages
                data = (json.dumps(message) + '\n').encode('utf-8')
                client['socket'].sendall(data)
        except Exception as e:
            print(f"Error sending message to {client_id}: {e}")

    def send_error(self, client_id: str, error_message: str):
        """Send error message to client"""
        self.send_message(client_id, {
            'type': 'error',
            'data': {'message': error_message}
        })

    def schedule_room_deletion(self, room_id: str, delay: int):
        """Schedule a room to be deleted after a delay (in seconds)"""
        def delete_room():
            time.sleep(delay)
            with self.lock:
                if room_id in self.rooms:
                    room = self.rooms[room_id]
                    del self.rooms[room_id]
                    print(f"Room '{room.name}' automatically deleted after game ended")

        # Run deletion in separate thread
        deletion_thread = threading.Thread(target=delete_room)
        deletion_thread.daemon = True
        deletion_thread.start()

    def disconnect_client(self, client_id: str):
        """Handle client disconnection"""
        with self.lock:
            client = self.clients.get(client_id)
            if not client:
                return

            # Remove from room if in one
            room_id = client.get('room_id')
            if room_id:
                room = self.rooms.get(room_id)
                if room:
                    room.remove_player(client_id)

                    # Notify other players
                    if len(room.players) > 0:
                        self.broadcast_to_room(room_id, {
                            'type': 'player_left',
                            'data': {'message': f"{client['nickname']} has left the room"}
                        })
                    else:
                        # Remove empty room
                        del self.rooms[room_id]
                        print(f"Room '{room.name}' removed (empty)")

            # Close socket
            try:
                client['socket'].close()
            except:
                pass

            # Remove client
            nickname = client.get('nickname', 'Unknown')
            del self.clients[client_id]
            print(f"Client {client_id} ({nickname}) disconnected")


def main():
    """Main entry point"""
    server = GameServer(HOST, PORT)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer stopped")
        sys.exit(0)


if __name__ == '__main__':
    main()
