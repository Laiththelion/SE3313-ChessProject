#include <iostream>
#include <unistd.h>
#include <string>
#include <cstring>
#include <thread>
#include <mutex>
#include <vector>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <signal.h>
#include <semaphore.h>

#define PORT 8080

std::mutex cout_mutex;

sem_t sem_white, sem_black;

void handle_player(int player_socket, int opponent_socket, std::string color) {
    char buffer[1024];

    // Debug info: process and thread ID
    std::cout << "[Match Thread][" << color << "] PID: " << getpid()
              << " | TID: " << std::this_thread::get_id() << std::endl;

    // Send role to player
    std::string role_msg = "ROLE:" + color;
    send(player_socket, role_msg.c_str(), role_msg.length(), 0);

    while (true) {
        if (color == "WHITE") {
            sem_wait(&sem_white);  // WHITE waits for turn
        } else {
            sem_wait(&sem_black);  // BLACK waits for turn
        }

        memset(buffer, 0, 1024);
        int valread = read(player_socket, buffer, 1024);
        if (valread <= 0) break;

        {
            std::lock_guard<std::mutex> lock(cout_mutex);
            std::cout << "[Match Thread][" << color << "] Received: " << buffer << std::endl;
        }

        send(opponent_socket, buffer, strlen(buffer), 0);

        // Give turn to other player
        if (color == "WHITE") {
            sem_post(&sem_black);
        } else {
            sem_post(&sem_white);
        }
    }

    {
        std::lock_guard<std::mutex> lock(cout_mutex);
        std::cout << "[Match Thread][" << color << "] Player disconnected. Ending match." << std::endl;
    }

    close(player_socket);
    close(opponent_socket);
    exit(0);  // Ends the child process cleanly
}

void sigchld_handler(int signum) {
    while (waitpid(-1, nullptr, WNOHANG) > 0);
}

int main() {
    signal(SIGCHLD, sigchld_handler);

    int server_fd;
    struct sockaddr_in address;
    int addrlen = sizeof(address);

    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd == 0) {
        perror("socket failed");
        return 1;
    }

    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR | SO_REUSEPORT, &opt, sizeof(opt));

    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(PORT);

    if (bind(server_fd, (struct sockaddr*)&address, sizeof(address)) < 0) {
        perror("bind failed");
        return 1;
    }

    listen(server_fd, 10);
    std::cout << "Server ready. Waiting for players..." << std::endl;

    std::vector<int> waiting_players;
    int match_id = 1;

    while (true) {
        int new_socket = accept(server_fd, (struct sockaddr*)&address, (socklen_t*)&addrlen);
        if (new_socket < 0) {
            perror("accept");
            continue;
        }

        {
            std::lock_guard<std::mutex> lock(cout_mutex);
            std::cout << "New player connected: socket " << new_socket << std::endl;
        }

        waiting_players.push_back(new_socket);

        if (waiting_players.size() >= 2) {
            int p1 = waiting_players[0];
            int p2 = waiting_players[1];
            waiting_players.erase(waiting_players.begin(), waiting_players.begin() + 2);

            pid_t pid = fork();
            if (pid == 0) {
                // Child process handles this match
                sem_init(&sem_white, 0, 1); // WHITE starts first
                sem_init(&sem_black, 0, 0); // BLACK waits

                std::thread t1(handle_player, p1, p2, "WHITE");
                std::thread t2(handle_player, p2, p1, "BLACK");

                t1.join();
                t2.join();

                sem_destroy(&sem_white);
                sem_destroy(&sem_black);
                exit(0);
            } else if (pid > 0) {
                // Parent closes unused sockets
                close(p1);
                close(p2);
                match_id++;
            } else {
                perror("fork failed");
            }
        }
    }

    close(server_fd);
    return 0;
}

