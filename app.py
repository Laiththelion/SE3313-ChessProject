from flask import Flask, render_template, request, jsonify
import chess
import chess.engine

app = Flask(__name__)

# initialize game
board = chess.Board()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/move', methods=['POST'])
def make_move():
    data = request.get_json()
    move_uci = data.get('move')

    if move_uci is None:
        return jsonify({'error': 'No move provided'}), 400

    try:
        move = chess.Move.from_uci(move_uci)
        if move in board.legal_moves:
            board.push(move)
            return jsonify({'status': 'ok', 'fen': board.fen()})
        else:
            return jsonify({'error': 'Illegal move'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/reset', methods=['POST'])
def reset_game():
    global board
    board = chess.Board()
    return jsonify({'status': 'reset', 'fen': board.fen()})

@app.route('/status')
def get_status():
    return jsonify({
        'fen': board.fen(),
        'is_game_over': board.is_game_over(),
        'turn': 'white' if board.turn else 'black'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
