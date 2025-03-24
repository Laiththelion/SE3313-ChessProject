import os
import time
import chess  # type: ignore
import multiprocessing

# --- Non-Pygame functions (safe to run in child processes) ---

# Evaluate board without any Pygame dependency.
def evaluate_board(board):
    PIECE_VALUES = {
        'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9, 'k': 1000,
        'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 1000
    }
    value = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            value += PIECE_VALUES.get(piece.symbol(), 0) * (1 if piece.color == chess.WHITE else -1)
    return value

def minimax(board, depth, alpha, beta, maximizing_player):
    if depth == 0 or board.is_game_over():
        return evaluate_board(board)
    legal_moves = list(board.legal_moves)
    if maximizing_player:
        max_eval = -float("inf")
        for move in legal_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval)
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = float("inf")
        for move in legal_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            if beta <= alpha:
                break
        return min_eval

# This function is used in a child process.
def ai_move_process(board_fen, result_queue, depth=3):
    board = chess.Board(board_fen)
    best_move = None
    max_eval = -float("inf")
    for move in board.legal_moves:
        board.push(move)
        eval = minimax(board, depth - 1, -float("inf"), float("inf"), False)
        board.pop()
        if eval > max_eval:
            max_eval = eval
            best_move = move
    result_queue.put(best_move)

# --- Pygame and Game Functions (only used in main process) ---
if __name__ == "__main__":
    import pygame  # type: ignore

    pygame.init()

    # Constants and initialization
    WIDTH, HEIGHT = 600, 600
    SQUARE_SIZE = WIDTH // 8
    WHITE, BLACK = (238, 238, 210), (118, 150, 86)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Chess Game")

    # Load Images
    IMAGES = {}
    PIECE_IMAGE_MAP = {
        'p': 'p.png', 'r': 'r.png', 'n': 'n.png', 'b': 'b.png',
        'q': 'q.png', 'k': 'k.png', 'P': 'P1.png', 'R': 'R1.png',
        'N': 'N1.png', 'B': 'B1.png', 'Q': 'Q1.png', 'K': 'K1.png'
    }
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for piece, filename in PIECE_IMAGE_MAP.items():
        image_path = os.path.join(script_dir, filename)
        if os.path.exists(image_path):
            image = pygame.image.load(image_path)
            IMAGES[piece] = pygame.transform.smoothscale(image, (SQUARE_SIZE, SQUARE_SIZE))
        else:
            print(f"Warning: Missing image file {image_path}")

    # Pygame-dependent drawing functions:
    def draw_board():
        for row in range(8):
            for col in range(8):
                color = WHITE if (row + col) % 2 == 0 else BLACK
                pygame.draw.rect(screen, color, (col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))

    def draw_pieces(board):
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.symbol() in IMAGES:
                col = chess.square_file(square)
                row = 7 - chess.square_rank(square)
                screen.blit(IMAGES[piece.symbol()], (col * SQUARE_SIZE, row * SQUARE_SIZE))

    def draw_menu():
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
        font = pygame.font.Font(None, 50)
        text_surface = font.render(text, True, (255, 0, 0))
        text_rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        screen.fill((0, 0, 0))
        screen.blit(text_surface, text_rect)
        pygame.display.flip()
        time.sleep(3)

    def get_square_under_mouse():
        x, y = pygame.mouse.get_pos()
        row = y // SQUARE_SIZE
        col = x // SQUARE_SIZE
        return chess.square(col, 7 - row)

    # Main game loop:
    def main():
        global player_vs_ai  # For mode selection
        board = chess.Board()
        running = True
        selected_square = None
        ai_turn = False
        menu = True

        # Menu loop
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

        ai_turn = board.turn and player_vs_ai

        # Game loop
        while running:
            draw_board()
            draw_pieces(board)
            pygame.display.flip()

            if board.is_checkmate():
                winner = "White" if board.turn == chess.BLACK else "Black"
                display_message(f"Checkmate! {winner} Wins.")
                break
            elif board.is_stalemate():
                display_message("Stalemate! Game Over.")
                break

            if ai_turn and not board.is_game_over():
                ctx = multiprocessing.get_context("spawn")
                result_queue = ctx.Queue()
                ai_process = ctx.Process(target=ai_move_process, args=(board.fen(), result_queue))
                ai_process.start()
                ai_process.join()
                ai_move = result_queue.get()
                if ai_move:
                    board.push(ai_move)
                ai_turn = board.turn and player_vs_ai

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if board.is_game_over():
                        continue
                    square = get_square_under_mouse()
                    if selected_square is None and board.piece_at(square) and board.color_at(square) == board.turn:
                        selected_square = square
                    else:
                        if selected_square is not None and square is not None:
                            move = chess.Move(selected_square, square)
                            if move in board.legal_moves:
                                board.push(move)
                                ai_turn = board.turn and player_vs_ai
                        selected_square = None

        pygame.quit()

    multiprocessing.freeze_support()  # Required for Windows
    main()
