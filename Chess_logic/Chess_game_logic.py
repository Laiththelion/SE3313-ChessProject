import pygame
import chess
import os
import time
import socket
import threading
import queue  # For processing incoming moves from opponent


incoming_moves = queue.Queue()  #Create a queue to store incoming opponent moves

# Network Setup
HOST = '127.0.0.1'
PORT = 8080
client_socket = None
player_color = None

pygame.init()
WIDTH, HEIGHT = 600, 600
SQUARE_SIZE = WIDTH // 8
WHITE_RGB, BLACK_RGB = (238, 238, 210), (118, 150, 86)
HIGHLIGHT_RGB = (255, 255, 0)  # Yellow highlight color for hover or selected
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Chess Game")  

# For end-game & in-game UI
BUTTON_WIDTH = 150
BUTTON_HEIGHT = 50

IMAGES = {}
PIECE_IMAGE_MAP = {
    'p': 'p.png',  'r': 'r.png',  'n': 'n.png',  'b': 'b.png',  'q': 'q.png',  'k': 'k.png',
    'P': 'P1.png', 'R': 'R1.png', 'N': 'N1.png', 'B': 'B1.png', 'Q': 'Q1.png', 'K': 'K1.png'
}


# New code: Load images from the 'Sprites' folder
script_dir = os.path.dirname(os.path.abspath(__file__))
for piece, filename in PIECE_IMAGE_MAP.items():
    path = os.path.join(script_dir, filename)
    if os.path.exists(path):
        img = pygame.image.load(path)
        IMAGES[piece] = pygame.transform.smoothscale(img, (SQUARE_SIZE, SQUARE_SIZE))
    else:
        print(f"[ERROR] Missing image: {path}")

PIECE_VALUES = {
    'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9, 'k': 1000,
    'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 1000
}

def evaluate_board(board):
    """
    Basic board evaluation:
    Positive if White is better, negative if Black is better.
    """
    value = 0
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            # Add if white, subtract if black
            value += PIECE_VALUES.get(piece.symbol(), 0) * (1 if piece.color == chess.WHITE else -1)
    return value

def minimax(board, depth, alpha, beta, maximizing_player):
    """
    Simple minimax implementation for AI moves.
    Depth-limited; does not use advanced heuristics.
    """
    if depth == 0 or board.is_game_over():
        return evaluate_board(board)
   
    legal_moves = list(board.legal_moves)
    if maximizing_player:
        max_eval = -float("inf")
        for move in legal_moves:
            board.push(move)
            eval_val = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            max_eval = max(max_eval, eval_val)
            alpha = max(alpha, eval_val)
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = float("inf")
        for move in legal_moves:
            board.push(move)
            eval_val = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            min_eval = min(min_eval, eval_val)
            beta = min(beta, eval_val)
            if beta <= alpha:
                break
        return min_eval

def get_best_move(board, depth=2):
    """
    Returns the best move for the current player by searching
    the minimax tree up to the given depth.
    """
    best_move = None
    max_eval = -float("inf")
    alpha = -float("inf")
    beta = float("inf")

    for move in board.legal_moves:
        board.push(move)
        eval_val = minimax(board, depth - 1, alpha, beta, False)
        board.pop()
        if eval_val > max_eval:
            max_eval = eval_val
            best_move = move
    return best_move

def get_square_under_mouse():
    """
    Returns the chess.py square index (0..63) for the current mouse coordinates.
    """
    x, y = pygame.mouse.get_pos()
    row = y // SQUARE_SIZE
    col = x // SQUARE_SIZE
    return chess.square(col, 7 - row)

def draw_board(selected_square=None, hover_square=None):
    """
    Draws an 8x8 board with an optional highlight for selected and hover squares.
    """
    for row in range(8):
        for col in range(8):
            color = WHITE_RGB if (row + col) % 2 == 0 else BLACK_RGB
            rect = pygame.Rect(col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE)
            pygame.draw.rect(screen, color, rect)

    # If there's a selected square, highlight it
    if selected_square is not None:
        col = chess.square_file(selected_square)
        row = 7 - chess.square_rank(selected_square)
        rect = pygame.Rect(col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE)
        pygame.draw.rect(screen, HIGHLIGHT_RGB, rect, 4)  # 4px border

    # If there's a hover square, highlight it
    if hover_square is not None:
        col = chess.square_file(hover_square)
        row = 7 - chess.square_rank(hover_square)
        rect = pygame.Rect(col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE)
        pygame.draw.rect(screen, HIGHLIGHT_RGB, rect, 2)  # 2px border

def draw_pieces(board):
    """
    Draws the pieces onto the board based on the current board state.
    """
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            col = chess.square_file(sq)
            row = 7 - chess.square_rank(sq)
            if piece.symbol() in IMAGES:
                screen.blit(IMAGES[piece.symbol()], (col * SQUARE_SIZE, row * SQUARE_SIZE))

def draw_menu():
    """
    Displays a simple menu with 'Player vs Player' and 'Player vs Computer' options.
    """
    screen.fill((50, 50, 50))
    font = pygame.font.Font(None, 36)
    pvp_text = font.render("Player vs Player", True, (255, 255, 255))
    pvc_text = font.render("Player vs Computer", True, (255, 255, 255))
    pvp_rect = pvp_text.get_rect(center=(WIDTH // 2, HEIGHT // 3))
    pvc_rect = pvc_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    screen.blit(pvp_text, pvp_rect)
    screen.blit(pvc_text, pvc_rect)
    pygame.display.flip()
    return pvp_rect, pvc_rect

def display_message(text):
    """
    Displays a large center message for 3 seconds.
    """
    font = pygame.font.Font(None, 50)
    text_surface = font.render(text, True, (255, 0, 0))
    text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    screen.fill((0, 0, 0))
    screen.blit(text_surface, text_rect)
    pygame.display.flip()
    time.sleep(3)

def draw_buttons(buttons):
    """
    Draws a list of (rect, text_surface) on the screen.
    """
    for rect, text_surface in buttons:
        pygame.draw.rect(screen, (150, 150, 150), rect)
        text_rect = text_surface.get_rect(center=rect.center)
        screen.blit(text_surface, text_rect)

# --- Networking ---
def setup_socket():
    """
    Creates a TCP socket and connects to the server at (HOST, PORT).
    """
    global client_socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))

def send_move_to_server(move_uci):
    """
    Sends a move (in UCI format) to the server.
    """
    if client_socket:
        client_socket.sendall(move_uci.encode())

def receive_move_from_server():
    """
    Blocks until a move is received, or returns None if disconnected.
    """
    try:
        return client_socket.recv(1024).decode()
    except:
        return None

def listen_for_opponent_moves(board):
    """
    Runs in a background thread.
    Receives the role (White or Black), then continuously listens for moves.
    Each move is enqueued in incoming_moves.
    """
    global player_color, opponent_disconnected
    role_msg = receive_move_from_server()
    if role_msg == "ROLE:WHITE":
        player_color = 'white'
    elif role_msg == "ROLE:BLACK":
        player_color = 'black'

    while True:
        move_uci = receive_move_from_server()
        if not move_uci:
            opponent_disconnected = True
            break
        if move_uci == "DISCONNECT":
            opponent_disconnected = True
            break
        """
        # Old code: Directly push move onto board
        # move = chess.Move.from_uci(move_uci)
        # if move in board.legal_moves:
        #     board.push(move)
        """
        # New code: Enqueue the move to be processed by the main loop
        incoming_moves.put(move_uci)

def show_endgame_screen(text):
    """
    Displays a message and two buttons:
    - 'New Game': Returns to menu
    - 'Quit': Exits the app
    """
    font = pygame.font.Font(None, 40)
    end_text = font.render(text, True, (255, 255, 255))
    text_rect = end_text.get_rect(center=(WIDTH // 2, HEIGHT // 3))

    new_game_text = font.render("New Game", True, (0, 0, 0))
    quit_text = font.render("Quit", True, (0, 0, 0))

    new_game_rect = pygame.Rect(WIDTH // 2 - 160, HEIGHT // 2, BUTTON_WIDTH, BUTTON_HEIGHT)
    quit_rect = pygame.Rect(WIDTH // 2 + 10, HEIGHT // 2, BUTTON_WIDTH, BUTTON_HEIGHT)

    buttons = [
        (new_game_rect, new_game_text),
        (quit_rect,     quit_text)
    ]

    while True:
        screen.fill((50, 50, 50))
        screen.blit(end_text, text_rect)
        draw_buttons(buttons)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit(0)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                if new_game_rect.collidepoint(mouse_pos):
                    return "new_game"
                elif quit_rect.collidepoint(mouse_pos):
                    pygame.quit()
                    exit(0)

def wait_for_opponent():
    """
    Displays a "Waiting for opponent" screen and processes events
    until the player's color is assigned (indicating an opponent has joined).
    """
    waiting_font = pygame.font.Font(None, 40)
    message_text = waiting_font.render("Waiting for opponent to join...", True, (255, 255, 255))
    text_rect = message_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit(0)
        if player_color is not None:
            waiting = False
            break
        screen.fill((30, 30, 30))
        screen.blit(message_text, text_rect)
        pygame.display.flip()
        time.sleep(0.1)

def main():
    """
    Main entry point for the Chess Game.
    Provides Player vs Player (via socket) or Player vs Computer (local AI).
    """
    global player_color, opponent_disconnected
    player_color = None
    opponent_disconnected = False

    board = chess.Board()
    running = True
    selected_square = None
    ai_turn = False
    player_vs_ai = None

    # Show initial menu
    menu = True
    while menu:
        pvp_button, pvc_button = draw_menu()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if pvp_button.collidepoint(event.pos):
                    player_vs_ai = False
                    menu = False
                elif pvc_button.collidepoint(event.pos):
                    player_vs_ai = True
                    menu = False

    """
    # Old code: Setup network without waiting
    # if not player_vs_ai:
    #     setup_socket()
    #     threading.Thread(target=listen_for_opponent_moves, args=(board,), daemon=True).start()
    # ai_turn = board.turn and player_vs_ai
    """
    # New code: If PvP, setup network and wait for role assignment
    if not player_vs_ai:
        setup_socket()
        threading.Thread(target=listen_for_opponent_moves, args=(board,), daemon=True).start()
        wait_for_opponent()  # Wait for player_color to be assigned
        print(f"You are playing as: {player_color}")
        pygame.display.set_caption(f"Chess Game - {player_color.title()}")
    else:
        # Player vs Computer mode
        print("Player vs Computer mode selected. Starting game...")
        pygame.display.set_caption("Chess Game - vs Computer")

    ai_turn = board.turn and player_vs_ai

    # For hover effect
    hover_square = None

    while running:
        # Check if opponent disconnected
        if opponent_disconnected:
            result = show_endgame_screen("Opponent disconnected. You win!")
            if result == "new_game":
                main()  # Restart
            return

        # Update AI turn if in PvC mode
        if ai_turn and not board.is_game_over():
            time.sleep(1)
            ai_move = get_best_move(board, depth=3)
            if ai_move:
                board.push(ai_move)
            ai_turn = board.turn and player_vs_ai

        # Process incoming moves from the queue
        while not incoming_moves.empty():
            move_uci = incoming_moves.get()
            move = chess.Move.from_uci(move_uci)
            if move in board.legal_moves:
                board.push(move)

        # Check for game over conditions
        if board.is_game_over():
            if board.is_checkmate():
                winner = "White" if board.turn == chess.BLACK else "Black"
                result = show_endgame_screen(f"Checkmate! {winner} Wins.")
            elif board.is_stalemate():
                result = show_endgame_screen("Stalemate! Game Over.")
            else:
                result = show_endgame_screen("Game Over.")

            if result == "new_game":
                main()
            return

        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEMOTION:
                hover_square = get_square_under_mouse()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if board.is_game_over():
                    continue
                square = get_square_under_mouse()
                if selected_square is None:
                    if board.piece_at(square) and board.color_at(square) == board.turn:
                        selected_square = square
                else:
                    move = chess.Move(selected_square, square)
                    if move in board.legal_moves:
                        if player_vs_ai or \
                           (player_color == 'white' and board.turn == chess.WHITE) or \
                           (player_color == 'black' and board.turn == chess.BLACK):
                            board.push(move)
                            if not player_vs_ai:
                                send_move_to_server(move.uci())
                            ai_turn = board.turn and player_vs_ai
                    selected_square = None

        # Draw board and pieces with highlights
        screen.fill((30, 30, 30))
        draw_board(selected_square, hover_square)
        draw_pieces(board)
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()


